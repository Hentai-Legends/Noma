import os
from typing import List, Dict

from src.parsers.base import DocumentChunk, ElementType
from .base import BaseBuilder, align_chunk_translations


class TxtBuilder(BaseBuilder):
    def build(
        self,
        chunks: List[DocumentChunk],
        translations: Dict[int, Dict[int, str]],
        output_file_path: str,
        bilingual: bool = False
    ):
        out_dir = os.path.dirname(os.path.abspath(output_file_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(output_file_path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                chunk_trans = align_chunk_translations(chunk, translations.get(chunk.chunk_id, {}))
                for i, el in enumerate(chunk.elements):
                    if el.is_image():
                        f.write(f"\n[Gambar: {el.image_filename}]\n\n")
                    elif el.element_type == ElementType.PAGE_BREAK:
                        f.write("\n\n---\n\n")
                    elif el.is_text():
                        translated_text = chunk_trans.get(i, el.text)

                        if el.element_type == ElementType.HEADING:
                            line_len = max(len(translated_text), 40)
                            line_sep = "=" * min(line_len, 80)
                            f.write(f"\n\n{line_sep}\n")
                            f.write(f"{translated_text}\n")
                            f.write(f"{line_sep}\n\n")
                            continue

                        if bilingual and el.text.strip() and el.text.strip() != translated_text.strip():
                            f.write(f"{el.text}\n")

                        f.write(f"{translated_text}\n\n")
