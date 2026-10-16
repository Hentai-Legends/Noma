import os
from typing import List, Dict
from urllib.parse import unquote
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from .base import BaseParser, DocumentChunk, DocumentElement, ElementType

class EpubParser(BaseParser):
    def __init__(self, max_words_per_chunk: int = 2000, filter_by_toc: bool = True):
        super().__init__(max_words_per_chunk)
        self.filter_by_toc = filter_by_toc

    def _extract_toc_hrefs(self, toc) -> set:
        hrefs = set()
        for item in toc:
            if isinstance(item, epub.Link):
                base = os.path.basename(unquote(item.href.split('#')[0]))
                hrefs.add(base)
            elif isinstance(item, tuple) and len(item) == 2:
                if isinstance(item[0], epub.Section) and item[0].href:
                    base = os.path.basename(unquote(item[0].href.split('#')[0]))
                    hrefs.add(base)
                hrefs.update(self._extract_toc_hrefs(item[1]))
            elif isinstance(item, epub.Section) and item.href:
                base = os.path.basename(unquote(item.href.split('#')[0]))
                hrefs.add(base)
        return hrefs

    def _extract_toc_map(self, toc) -> Dict[str, List[str]]:
        toc_map = {}
        def add_to_map(href, title):
            if not href or not title:
                return
            base = os.path.basename(unquote(href.split('#')[0]))
            if base not in toc_map:
                toc_map[base] = []
            toc_map[base].append(title.strip())

        for item in toc:
            if isinstance(item, epub.Link):
                add_to_map(item.href, item.title)
            elif isinstance(item, tuple) and len(item) == 2:
                if isinstance(item[0], epub.Section):
                    add_to_map(item[0].href, item[0].title)
                # Recurse
                sub_map = self._extract_toc_map(item[1])
                for k, v in sub_map.items():
                    if k not in toc_map:
                        toc_map[k] = []
                    toc_map[k].extend(v)
            elif isinstance(item, epub.Section):
                add_to_map(item.href, item.title)
        return toc_map

    def _normalize_title(self, title: str) -> str:
        import re
        return re.sub(r'[^a-zA-Z0-9\u4e00-\u9faf\u3040-\u309f\u30a0-\u30ff]', '', title).lower()

    def parse(self, file_path: str) -> List[DocumentChunk]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File EPUB tidak ditemukan: {file_path}")

        book = epub.read_epub(file_path)
        
        toc_files = self._extract_toc_hrefs(book.toc) if self.filter_by_toc else set()
        toc_map = self._extract_toc_map(book.toc) if self.filter_by_toc else {}
        
        # Peta gambar dalam EPUB (filename -> bytes & content_type)
        images_map: Dict[str, tuple] = {}
        cover_candidates = []

        for item in book.get_items():
            media_type = getattr(item, 'media_type', '') or ''
            is_image = item.get_type() in (ebooklib.ITEM_IMAGE, ebooklib.ITEM_COVER) or media_type.startswith('image/')
            if is_image:
                ext = media_type.split('/')[-1] if '/' in media_type else "jpg"
                if ext in ("jpeg", "jpg"):
                    ext = "jpg"
                content = item.get_content()
                raw_name = item.get_name()
                clean_name = unquote(raw_name)
                images_map[raw_name] = (content, ext)
                images_map[clean_name] = (content, ext)
                images_map[os.path.basename(raw_name)] = (content, ext)
                images_map[os.path.basename(clean_name)] = (content, ext)

                # Deteksi kandidat cover
                is_cover = (
                    item.get_type() == ebooklib.ITEM_COVER
                    or 'cover' in raw_name.lower()
                    or 'cover' in str(item.get_id()).lower()
                    or 'cover-image' in getattr(item, 'properties', [])
                )
                if is_cover:
                    cover_candidates.append(item)

        elements: List[DocumentElement] = []

        # Pindai item dokumen HTML berdasarkan urutan baca (spine) agar bab tidak berantakan
        for item_id, linear in book.spine:
            item = book.get_item_with_id(item_id)
            if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            filename = unquote(item.get_name())
            file_basename = os.path.basename(filename)
            
            # Sertakan semua file dalam spine tanpa filter TOC.
            # Banyak EPUB memecah bab menjadi beberapa file (misal: chapter2.xhtml + chapter2_1.xhtml)
            # di mana hanya file pertama yang tercatat di TOC. Filter TOC lama menyebabkan
            # file lanjutan terbuang sehingga isi cerita terpotong dan terasa berantakan.

            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            # Pindai tag paragraf, heading, div, li, dan img secara berurutan dalam body
            body = soup.body if soup.body else soup
            block_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'li']
            
            # Ambil judul bab referensi untuk file ini
            ref_titles = toc_map.get(file_basename, [])
            norm_ref_titles = [self._normalize_title(t) for t in ref_titles]
            
            file_elements: List[DocumentElement] = []

            for tag in body.find_all(block_tags + ['img', 'image']):
                if tag.name in ['img', 'image']:
                    src = tag.get('src') or tag.get('xlink:href') or tag.get('href') or ''
                    if not src:
                        continue
                    img_filename = os.path.basename(unquote(src).split('#')[0].split('?')[0])
                    if img_filename in images_map:
                        img_bytes, ext = images_map[img_filename]

                        # Mencegah duplikasi gambar cover berturut-turut tanpa teks di antaranya
                        # (misal: cover.xhtml + Section0001.xhtml yang sama-sama memuat cover.jpg)
                        all_so_far = elements + file_elements
                        is_duplicate_consecutive = False
                        if any(el.is_image() for el in all_so_far):
                            last_img_pos = max(i for i, el in enumerate(all_so_far) if el.is_image())
                            if not any(el.is_text() for el in all_so_far[last_img_pos + 1:]):
                                last_img = all_so_far[last_img_pos]
                                if last_img.image_filename == img_filename or (last_img.image_bytes and last_img.image_bytes == img_bytes):
                                    is_duplicate_consecutive = True

                        if is_duplicate_consecutive:
                            continue

                        file_elements.append(DocumentElement(
                            element_type=ElementType.IMAGE,
                            image_bytes=img_bytes,
                            image_ext=ext,
                            image_filename=img_filename
                        ))
                else:
                    # Mencegah duplikasi teks: jika elemen ini memiliki child yang JUGA merupakan elemen blok,
                    # kita lewati ekstrak teks pada elemen parent ini (anaknya akan ditangkap nanti oleh find_all).
                    has_block_child = tag.find(block_tags) is not None
                    if has_block_child:
                        continue
                        
                    text = tag.get_text().strip()
                    if text:
                        is_heading = False
                        level = 1
                        
                        if tag.name.startswith('h'):
                            is_heading = True
                            level = int(tag.name[1]) if tag.name.startswith('h') else 1
                        else:
                            # Cek apakah teks ini cocok dengan salah satu judul TOC asli untuk file ini
                            norm_text = self._normalize_title(text)
                            if norm_text in norm_ref_titles:
                                is_heading = True
                                level = 1
                                norm_ref_titles.remove(norm_text)
                        
                        if is_heading:
                            file_elements.append(DocumentElement(
                                element_type=ElementType.HEADING,
                                text=text,
                                heading_level=level
                            ))
                        else:
                            file_elements.append(DocumentElement(
                                element_type=ElementType.PARAGRAPH,
                                text=text
                            ))

            if file_elements:
                if elements:
                    elements.append(DocumentElement(element_type=ElementType.PAGE_BREAK))
                elements.extend(file_elements)

        # Pastikan cover image selalu ada di awal dokumen jika EPUB memilikinya
        # tetapi tidak disertakan di dalam file XHTML spine
        first_images = [el.image_filename for el in elements[:10] if el.is_image()]
        has_cover = False
        for cand in cover_candidates:
            cand_base = os.path.basename(unquote(cand.get_name()))
            if cand_base in first_images:
                has_cover = True
                break

        if not has_cover and cover_candidates:
            best_cand = cover_candidates[0]
            for cand in cover_candidates:
                if cand.get_type() == ebooklib.ITEM_COVER or 'cover-image' in getattr(cand, 'properties', []):
                    best_cand = cand
                    break
            media_type = getattr(best_cand, 'media_type', '') or ''
            ext = media_type.split('/')[-1] if '/' in media_type else "jpg"
            if ext in ("jpeg", "jpg"):
                ext = "jpg"
            cand_base = os.path.basename(unquote(best_cand.get_name()))
            elements.insert(0, DocumentElement(
                element_type=ElementType.IMAGE,
                image_bytes=best_cand.get_content(),
                image_ext=ext,
                image_filename=cand_base
            ))

        elements = self._remove_toc_page(elements)
        elements = self._inject_smart_page_breaks(elements)
        return self._chunk_elements(elements)
