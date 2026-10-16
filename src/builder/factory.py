import os
from .base import BaseBuilder
from .docx_builder import DocxBuilder
from .epub_builder import EpubBuilder
from .txt_builder import TxtBuilder
from .pdf_builder import PdfBuilder

def get_builder_for_file(output_file_path: str) -> BaseBuilder:
    ext = os.path.splitext(output_file_path)[1].lower()
    if ext == ".docx":
        return DocxBuilder()
    elif ext == ".epub":
        return EpubBuilder()
    elif ext == ".txt":
        return TxtBuilder()
    elif ext == ".pdf":
        return PdfBuilder()
    else:
        return DocxBuilder()
