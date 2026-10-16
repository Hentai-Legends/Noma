import os
from typing import List
import docx
from docx.oxml.ns import qn

from .base import BaseParser, DocumentChunk, DocumentElement, ElementType, CHAPTER_PATTERN


class DocxParser(BaseParser):
    def parse(self, file_path: str) -> List[DocumentChunk]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File DOCX tidak ditemukan: {file_path}")

        doc = docx.Document(file_path)
        elements: List[DocumentElement] = []

        for p in doc.paragraphs:
            # Periksa apakah paragraf memiliki gambar (drawing / blip)
            images_in_p = self._extract_images_from_paragraph(p, doc)

            # Jika ada gambar sebelum atau di dalam paragraf
            for img_bytes, img_ext, img_name in images_in_p:
                elements.append(DocumentElement(
                    element_type=ElementType.IMAGE,
                    image_bytes=img_bytes,
                    image_ext=img_ext,
                    image_filename=img_name
                ))

            # Olah teks jika tidak kosong
            text = p.text.strip()
            if text:
                is_heading = False
                heading_level = 0

                style_name = (p.style.name if p.style else "").strip()

                if style_name.startswith("Heading"):
                    is_heading = True
                    try:
                        heading_level = int(style_name.replace("Heading", "").strip())
                    except ValueError:
                        heading_level = 1
                elif style_name.lower() in ("title", "judul"):
                    is_heading = True
                    heading_level = 1
                elif len(text) < 120 and CHAPTER_PATTERN.match(text):
                    is_heading = True
                    heading_level = 1

                elem_type = ElementType.HEADING if is_heading else ElementType.PARAGRAPH
                elements.append(DocumentElement(
                    element_type=elem_type,
                    text=text,
                    heading_level=heading_level,
                    metadata={"style": style_name if style_name else "Normal"}
                ))

        elements = self._remove_toc_page(elements)
        return self._chunk_elements(elements)

    def _extract_images_from_paragraph(self, paragraph, doc) -> List[tuple]:
        """
        Mengekstrak binary gambar dari paragraf Word.
        Mengembalikan list dari tuple (image_bytes, image_ext, image_name)
        """
        extracted_images = []
        # Cari elemen blip di XML paragraf
        blips = paragraph._element.xpath('.//a:blip')
        for idx, blip in enumerate(blips):
            embed_id = blip.get(qn('r:embed'))
            if embed_id and embed_id in doc.part.related_parts:
                target_part = doc.part.related_parts[embed_id]
                # Pastikan part adalah image
                if 'image' in target_part.content_type:
                    image_bytes = target_part.blob
                    ext = target_part.content_type.split('/')[-1]
                    if ext == 'jpeg':
                        ext = 'jpg'
                    filename = os.path.basename(target_part.partname)
                    extracted_images.append((image_bytes, ext, filename))
        return extracted_images
