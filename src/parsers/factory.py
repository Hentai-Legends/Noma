import os
from .base import BaseParser
from .docx_parser import DocxParser
from .epub_parser import EpubParser
from .pdf_parser import PdfParser
from .txt_parser import TxtParser

def get_parser_for_file(file_path: str, max_words_per_chunk: int = 2000) -> BaseParser:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return DocxParser(max_words_per_chunk=max_words_per_chunk)
    elif ext == ".epub":
        return EpubParser(max_words_per_chunk=max_words_per_chunk)
    elif ext == ".pdf":
        return PdfParser(max_words_per_chunk=max_words_per_chunk)
    elif ext in (".txt", ".md"):
        return TxtParser(max_words_per_chunk=max_words_per_chunk)
    else:
        raise ValueError(f"Format file '{ext}' belum didukung. Format yang didukung: .docx, .epub, .pdf, .txt")
