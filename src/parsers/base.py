import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

CHAPTER_PATTERN = re.compile(
    r'^(Bab|Chapter|Bagian|Volume|Vol|Episode|Prologue|Epilogue|Prolog|Epilog|Interlude|Side Story|Ekstra|Extra|Act|第[0-9一二三四五六七八九十百]+[章巻話部])\b',
    re.IGNORECASE
)

class ElementType(Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    IMAGE = "image"
    PAGE_BREAK = "page_break"

@dataclass
class DocumentElement:
    element_type: ElementType
    text: str = ""
    heading_level: int = 0
    image_bytes: Optional[bytes] = None
    image_ext: str = "png"
    image_filename: str = ""
    metadata: dict = field(default_factory=dict)

    def is_image(self) -> bool:
        return self.element_type == ElementType.IMAGE

    def is_text(self) -> bool:
        return self.element_type in (ElementType.PARAGRAPH, ElementType.HEADING)

@dataclass
class DocumentChunk:
    chunk_id: int
    elements: List[DocumentElement]
    word_count: int = 0

    def get_text_for_translation(self) -> str:
        """
        Menggabungkan teks dari elemen-elemen teks dalam chunk ini
        dengan delimiter khusus agar urutan paragraf tetap terjaga saat diterjemahkan.
        """
        text_lines = []
        for i, el in enumerate(self.elements):
            if el.is_text() and el.text.strip():
                text_lines.append(f"[{i}] {el.text}")
        return "\n\n".join(text_lines)


class BaseParser:
    def __init__(self, max_words_per_chunk: int = 2000):
        self.max_words_per_chunk = max_words_per_chunk

    def parse(self, file_path: str) -> List[DocumentChunk]:
        raise NotImplementedError("Subclasses must implement parse()")

    def _remove_toc_page(self, elements: List[DocumentElement]) -> List[DocumentElement]:
        """
        Mendeteksi halaman Daftar Isi (TOC) di bagian awal dokumen dan menghapusnya
        untuk menghindari duplikasi dengan TOC dinamis yang akan dibuat di Word.
        """
        toc_start_idx = None
        
        # Cari judul "Daftar Isi" di 100 elemen pertama
        for i in range(min(100, len(elements))):
            el = elements[i]
            if el.is_text():
                clean_text = "".join(el.text.split()).lower()
                if clean_text in ("daftarisi", "tableofcontents", "contents", "目次", "index"):
                    toc_start_idx = i
                    break
        
        if toc_start_idx is None:
            return elements
            
        # Cari di mana TOC berakhir (batasi maksimal 3000 elemen agar novel web masif tetap ter-cover)
        toc_end_idx = None
        max_search = min(toc_start_idx + 3000, len(elements))
        for j in range(toc_start_idx + 1, max_search):
            el = elements[j]
            
            # Jika menemukan Page Break, itu adalah pembatas halaman TOC yang paling jelas
            if el.element_type == ElementType.PAGE_BREAK:
                toc_end_idx = j
                break

            # Jika menemukan Heading (misalnya Bab 1 / Prolog) setelah TOC, TOC pasti sudah selesai
            if el.element_type == ElementType.HEADING:
                toc_end_idx = j - 1
                break
                
            if el.is_text():
                # Jika ada paragraf panjang atau berisi dialog, berarti kita sudah masuk isi buku
                text_len = len(el.text.strip())
                if text_len > 150 or any(q in el.text for q in ('「', '『', '“', '"', '（', '(')):
                    # Kita potong sampai sebelum elemen narasi ini
                    toc_end_idx = j - 1
                    break
                    
        if toc_end_idx is not None and toc_end_idx >= toc_start_idx:
            # Hapus semua elemen dari judul TOC sampai batas akhir TOC
            return elements[:toc_start_idx] + elements[toc_end_idx + 1:]
            
        return elements

    def _inject_smart_page_breaks(self, elements: List[DocumentElement]) -> List[DocumentElement]:
        # Logika ini telah dihapus karena deteksi bab sekarang ditangani oleh AI
        # melalui Markdown heading yang otomatis dikonversi ke Heading 1 dengan Page Break Before
        return elements

    def _chunk_elements(self, elements: List[DocumentElement]) -> List[DocumentChunk]:
        """
        Membagi daftar DocumentElement menjadi potongan chunk dengan batasan kata <= max_words_per_chunk.
        Gambar akan ditempatkan di chunk yang sesuai tanpa merusak struktur.
        """
        chunks: List[DocumentChunk] = []
        current_elements: List[DocumentElement] = []
        current_word_count = 0
        chunk_counter = 0

        for el in elements:
            el_words = len(el.text.split()) if el.is_text() else 0

            # Jika menambahkan elemen ini melebihi max_words dan sudah ada teks di chunk sekarang
            if current_word_count + el_words > self.max_words_per_chunk and current_word_count > 0:
                is_hanging = False
                unclosed_brackets = 0
                
                if current_elements:
                    last_el = current_elements[-1]
                    if last_el.is_text() and last_el.text.strip():
                        last_char = last_el.text.strip()[-1]
                        if last_char not in ('.', '!', '?', '。', '！', '？', '」', '』', '"', "'", '”', '’', '—', '-', '…'):
                            is_hanging = True

                for cel in current_elements:
                    if cel.is_text():
                        for ch in cel.text:
                            if ch in ('「', '『', '“', '(', '（', '['):
                                unclosed_brackets += 1
                            elif ch in ('」', '』', '”', ')', '）', ']'):
                                unclosed_brackets -= 1

                is_mid_dialogue = (unclosed_brackets > 0)
                
                # Jangan memotong jika sedang di tengah dialog atau kalimat menggantung
                # Kecuali jika chunk sudah terlalu besar (fail-safe +500 kata)
                if (not is_hanging and not is_mid_dialogue) or (current_word_count > self.max_words_per_chunk + 500):
                    chunks.append(DocumentChunk(
                        chunk_id=chunk_counter,
                        elements=current_elements,
                        word_count=current_word_count
                    ))
                    chunk_counter += 1
                    current_elements = []
                    current_word_count = 0

            current_elements.append(el)
            current_word_count += el_words

        if current_elements:
            chunks.append(DocumentChunk(
                chunk_id=chunk_counter,
                elements=current_elements,
                word_count=current_word_count
            ))

        return chunks
