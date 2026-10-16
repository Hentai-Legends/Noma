import os
import io
from typing import List, Dict

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

from src.parsers.base import DocumentChunk, ElementType
from .base import BaseBuilder, align_chunk_translations


class PdfBuilder(BaseBuilder):
    def build(
        self,
        chunks: List[DocumentChunk],
        translations: Dict[int, Dict[int, str]],
        output_file_path: str,
        bilingual: bool = False
    ):
        if FPDF is None:
            raise ImportError("Package 'fpdf2' is required for PDF output. Silakan install dengan 'pip install fpdf2'.")

        out_dir = os.path.dirname(os.path.abspath(output_file_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        pdf = FPDF(unit="pt", format="A4")
        pdf.set_margins(72, 72, 72)
        pdf.set_auto_page_break(auto=True, margin=72)

        font_path = "C:\\Windows\\Fonts\\times.ttf"
        font_bold_path = "C:\\Windows\\Fonts\\timesbd.ttf"
        font_italic_path = "C:\\Windows\\Fonts\\timesi.ttf"

        has_ttf = False
        if os.path.exists(font_path) and os.path.exists(font_bold_path):
            pdf.add_font("TimesNewRoman", style="", fname=font_path)
            pdf.add_font("TimesNewRoman", style="B", fname=font_bold_path)
            if os.path.exists(font_italic_path):
                pdf.add_font("TimesNewRoman", style="I", fname=font_italic_path)
            has_ttf = True
            pdf.set_font("TimesNewRoman", size=12)
        else:
            pdf.set_font("Times", size=12)

        in_image_page = False

        for chunk in chunks:
            chunk_trans = align_chunk_translations(chunk, translations.get(chunk.chunk_id, {}))

            for i, el in enumerate(chunk.elements):
                if el.element_type == ElementType.PAGE_BREAK:
                    if in_image_page:
                        pass
                    else:
                        pdf.add_page(format="A4")
                        pdf.set_auto_page_break(True, margin=72)
                        pdf.set_margins(72, 72, 72)
                    continue

                if el.is_image() and el.image_bytes:
                    try:
                        from PIL import Image
                        img_stream = io.BytesIO(el.image_bytes)
                        pil_img = Image.open(img_stream).convert("RGB")
                        img_w, img_h = pil_img.size

                        if img_w >= 200 and img_h >= 200:
                            # Halaman presisi menyesuaikan gambar (Full Page)
                            a4_h = 841.89
                            if img_w > img_h:
                                # Gambar Landscape (spread horizontal)
                                img_page_w = a4_h
                                img_page_h = a4_h * (img_h / img_w)
                            else:
                                # Gambar Portrait (vertikal / cover)
                                img_page_h = a4_h
                                img_page_w = a4_h * (img_w / img_h)

                            pdf.add_page(format=(img_page_w, img_page_h))
                            pdf.set_auto_page_break(False)
                            pdf.image(pil_img, x=0, y=0, w=img_page_w, h=img_page_h)
                            in_image_page = True
                        else:
                            # Gambar kecil (inline / ornament)
                            if in_image_page or pdf.page_no() == 0:
                                pdf.add_page(format="A4")
                                pdf.set_auto_page_break(True, margin=72)
                                pdf.set_margins(72, 72, 72)
                                in_image_page = False
                            pdf.ln(12)
                            pdf.image(pil_img, w=min(pdf.epw, img_w * 72.0 / 96.0), keep_aspect_ratio=True)
                            pdf.ln(12)
                    except Exception:
                        if in_image_page or pdf.page_no() == 0:
                            pdf.add_page(format="A4")
                            pdf.set_auto_page_break(True, margin=72)
                            pdf.set_margins(72, 72, 72)
                            in_image_page = False
                        if has_ttf:
                            pdf.set_font("TimesNewRoman", style="B", size=12)
                        else:
                            pdf.set_font("Times", style="B", size=12)
                        pdf.multi_cell(0, 16, text=f"[Gambar: {el.image_filename}]", align="C")
                        if has_ttf:
                            pdf.set_font("TimesNewRoman", style="", size=12)
                        else:
                            pdf.set_font("Times", style="", size=12)

                elif el.is_text():
                    if in_image_page or pdf.page_no() == 0:
                        pdf.add_page(format="A4")
                        pdf.set_auto_page_break(True, margin=72)
                        pdf.set_margins(72, 72, 72)
                        in_image_page = False
                    translated_text = chunk_trans.get(i, el.text)

                    if el.element_type == ElementType.HEADING:
                        level = min(max(el.heading_level or 1, 1), 4)
                        title_size = 18 if level == 1 else (15 if level == 2 else 13)
                        if has_ttf:
                            pdf.set_font("TimesNewRoman", style="B", size=title_size)
                        else:
                            pdf.set_font("Times", style="B", size=title_size)

                        pdf.ln(18)
                        pdf.multi_cell(0, title_size + 4, text=translated_text, align="C")
                        pdf.ln(10)

                        if has_ttf:
                            pdf.set_font("TimesNewRoman", style="", size=12)
                        else:
                            pdf.set_font("Times", style="", size=12)

                    else:
                        if bilingual and el.text.strip() and el.text.strip() != translated_text.strip():
                            if has_ttf:
                                pdf.set_font("TimesNewRoman", style="I", size=12)
                            else:
                                pdf.set_font("Times", style="I", size=12)
                            pdf.multi_cell(0, 16, text=f"     {el.text}", align="J")
                            pdf.ln(2)
                            if has_ttf:
                                pdf.set_font("TimesNewRoman", style="", size=12)
                            else:
                                pdf.set_font("Times", style="", size=12)

                        has_alnum = any(c.isalnum() for c in translated_text)
                        if not has_alnum and 0 < len(translated_text.strip()) < 20:
                            pdf.ln(12)
                            pdf.multi_cell(0, 16, text=translated_text, align="C")
                            pdf.ln(12)
                        else:
                            # Indentasi 5 spasi di awal paragraf
                            pdf.multi_cell(0, 16, text=f"     {translated_text}", align="J")
                            pdf.ln(6)

        pdf.output(output_file_path)
