import re
from typing import List, Dict, Any
from src.parsers.base import DocumentChunk


def clean_heading_title(text: str) -> str:
    """
    Membersihkan judul heading dari simbol markdown (#, **, __)
    yang mungkin muncul dari hasil terjemahan AI.
    """
    if not text:
        return ""
    t = text.strip()
    # Hapus simbol markdown hash (#, ##, dst)
    t = re.sub(r'^(#+)\s*', '', t)
    # Hapus markdown bold/italic di sekeliling teks
    t = re.sub(r'^\*{1,3}(.*?)\*{1,3}$', r'\1', t)
    t = re.sub(r'^_{1,3}(.*?)_{1,3}$', r'\1', t)
    # Hapus sisa tanda ** atau __ di dalam judul
    t = t.replace('**', '').replace('__', '')
    # Ganti newline dan whitespace berulang menjadi satu spasi
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def clean_translated_text(text: str, orig_text: str = "") -> str:
    """
    Membersihkan teks terjemahan dari penanda indeks AI yang bocor (seperti '[0] ', '(1) ', '0. ')
    jika teks aslinya memang tidak diawali oleh format penanda tersebut.
    """
    if not text:
        return ""
    orig_clean = orig_text.strip() if orig_text else ""
    while True:
        m = re.match(r"^(\[\d+\]|\(\d+\)|\b\d+[\.:\-])\s*", text)
        if not m:
            break
        tag = m.group(1)
        if orig_clean and orig_clean.startswith(tag):
            break
        text = text[m.end():].strip()
    return text


def align_chunk_translations(chunk: DocumentChunk, raw_trans: Dict[Any, str]) -> Dict[int, str]:
    """
    Menyelaraskan kamus terjemahan (dari cache / checkpoint) dengan elemen teks chunk saat ini,
    serta membersihkan kemungkinan artefak nomor indeks AI yang bocor ke dalam teks.
    Mencegah pergeseran indeks jika ada penambahan/pengurangan elemen non-teks
    (seperti cover image, ilustrasi, atau page break) akibat pembaruan parser.
    """
    if not raw_trans or not getattr(chunk, 'elements', None):
        return {}

    clean_trans = {int(k): v for k, v in raw_trans.items() if str(k).isdigit()}
    text_indices = [i for i, el in enumerate(chunk.elements) if el.is_text() and el.text.strip()]

    if not clean_trans or not text_indices:
        return clean_trans

    trans_keys = set(clean_trans.keys())
    text_set = set(text_indices)

    aligned: Dict[int, str] = {}

    # 1. Jika indeks sudah cocok sempurna atau subset (misal ada baris terlewat di akhir chunk)
    if trans_keys.issubset(text_set):
        aligned = clean_trans
    else:
        sorted_keys = sorted(clean_trans.keys())

        # 2. Cek apakah terjadi pergeseran seragam (uniform offset)
        # Contoh: cover + page break menambah N elemen non-teks di awal chunk
        shift = text_indices[0] - sorted_keys[0]
        if shift != 0 and sum(1 for k in sorted_keys if (k + shift) in text_set) >= len(sorted_keys) * 0.75:
            aligned = {k + shift: clean_trans[k] for k in sorted_keys if (k + shift) in text_set}
        # 3. Jika jumlah elemen teks sama persis dengan jumlah terjemahan di cache (1-to-1 sequential)
        elif len(text_indices) == len(sorted_keys):
            aligned = {t_idx: clean_trans[k] for t_idx, k in zip(text_indices, sorted_keys)}
        # 4. Fallback: pemetaan sekuensial parsial jika jumlah sedikit berbeda (misal dropped lines)
        elif len(trans_keys - text_set) > 0:
            aligned = {text_indices[idx]: clean_trans[sorted_keys[idx]] for idx in range(min(len(text_indices), len(sorted_keys)))}
        else:
            aligned = clean_trans

    # 5. Bersihkan artefak nomor indeks AI yang bocor ke dalam teks
    for i, el in enumerate(chunk.elements):
        if i in aligned and el.is_text() and isinstance(aligned[i], str):
            aligned[i] = clean_translated_text(aligned[i], el.text)

    return aligned


class BaseBuilder:
    def build(
        self,
        chunks: List[DocumentChunk],
        translations: Dict[int, Dict[int, str]],
        output_file_path: str,
        bilingual: bool = False
    ):
        """
        :param chunks: List dari DocumentChunk asli yang di-parse
        :param translations: Map {chunk_id: {element_idx: translated_text}}
        :param output_file_path: Jalur simpan file hasil
        """
        raise NotImplementedError("Subclasses must implement build()")
