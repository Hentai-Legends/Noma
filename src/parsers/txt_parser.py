import os
import re
from typing import List

from .base import BaseParser, DocumentChunk, DocumentElement, ElementType, CHAPTER_PATTERN


class TxtParser(BaseParser):
    def parse(self, file_path: str) -> List[DocumentChunk]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File TXT tidak ditemukan: {file_path}")

        elements: List[DocumentElement] = []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            is_heading = False
            heading_level = 1

            # Cek 1: Format Markdown heading (#, ##, ###)
            md_match = re.match(r'^(#+)\s*(.*)', line_str)
            if md_match:
                is_heading = True
                heading_level = len(md_match.group(1))
                line_str = md_match.group(2).strip()
            # Cek 2: Pola penamaan bab novel
            elif len(line_str) < 120 and CHAPTER_PATTERN.match(line_str):
                is_heading = True
                heading_level = 1

            if is_heading:
                elements.append(DocumentElement(
                    element_type=ElementType.HEADING,
                    text=line_str,
                    heading_level=heading_level
                ))
            else:
                elements.append(DocumentElement(
                    element_type=ElementType.PARAGRAPH,
                    text=line_str
                ))

        elements = self._remove_toc_page(elements)
        elements = self._inject_smart_page_breaks(elements)
        return self._chunk_elements(elements)
