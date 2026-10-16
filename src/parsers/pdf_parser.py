import os
import re
from typing import List
import pymupdf

from .base import BaseParser, DocumentChunk, DocumentElement, ElementType, CHAPTER_PATTERN


class PdfParser(BaseParser):
    def parse(self, file_path: str) -> List[DocumentChunk]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File PDF tidak ditemukan: {file_path}")

        doc = pymupdf.open(file_path)
        elements: List[DocumentElement] = []

        # Ambil daftar judul dari TOC bawaan file PDF jika ada
        toc_titles = set()
        try:
            pdf_toc = doc.get_toc()
            for item in pdf_toc:
                if len(item) > 1 and item[1]:
                    norm_t = re.sub(r'\s+', ' ', item[1]).strip().lower()
                    if norm_t:
                        toc_titles.add(norm_t)
        except Exception:
            pass

        for page_num in range(len(doc)):
            page = doc[page_num]

            # 1. Ekstrak gambar di halaman ini
            image_list = page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                if image_ext == "jpeg":
                    image_ext = "jpg"

                elements.append(DocumentElement(
                    element_type=ElementType.IMAGE,
                    image_bytes=image_bytes,
                    image_ext=image_ext,
                    image_filename=f"pdf_page_{page_num+1}_img_{xref}.{image_ext}"
                ))

            # 2. Ekstrak blok teks di halaman ini
            blocks = page.get_text("blocks")
            for b in blocks:
                # b = (x0, y0, x1, y1, "text", block_no, block_type)
                text = b[4].strip()
                if text:
                    lines = text.split("\n")
                    clean_text = " ".join(lines).strip()
                    norm_text = clean_text.lower()

                    is_heading = False
                    heading_level = 1

                    # Cek 1: Cocok dengan judul di TOC asli PDF
                    if norm_text in toc_titles:
                        is_heading = True
                        heading_level = 1
                    # Cek 2: Cocok dengan pola penamaan bab novel
                    elif len(clean_text) < 120 and CHAPTER_PATTERN.match(clean_text):
                        is_heading = True
                        heading_level = 1

                    elem_type = ElementType.HEADING if is_heading else ElementType.PARAGRAPH

                    elements.append(DocumentElement(
                        element_type=elem_type,
                        text=clean_text,
                        heading_level=heading_level if is_heading else 0
                    ))

        doc.close()
        elements = self._remove_toc_page(elements)
        return self._chunk_elements(elements)
