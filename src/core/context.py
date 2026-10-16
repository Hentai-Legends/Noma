import os
import re
from typing import List, Dict, Tuple, Optional, Any
from src.parsers.base import ElementType, CHAPTER_PATTERN

def detect_chapters_from_chunks(chunks: List[Any]) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    """
    Mengelompokkan daftar DocumentChunk menjadi bab-bab terstruktur.
    Mengembalikan (chapters_list, chapter_start_map)
    di mana chapter_start_map = {start_chunk_id: chapter_info}
    """
    if not chunks:
        return [], {}
        
    chapters = []
    current_title = "Bagian Awal"
    current_start_chunk_id = chunks[0].chunk_id
    current_chunks = []
    current_texts = []
    
    for chunk in chunks:
        heading_el = None
        for el in chunk.elements:
            if el.element_type == ElementType.HEADING:
                heading_el = el
                break
            elif el.is_text() and len(el.text.strip()) < 120 and CHAPTER_PATTERN.match(el.text.strip()):
                heading_el = el
                break
                
        chunk_text = "\n".join([el.text for el in chunk.elements if el.is_text() and el.text.strip()])
        
        if heading_el and current_texts:
            # Tutup bab sebelumnya
            chap_info = {
                "chapter_index": len(chapters),
                "title": current_title,
                "start_chunk_id": current_start_chunk_id,
                "chunk_ids": list(current_chunks),
                "text": "\n\n".join(current_texts)
            }
            chapters.append(chap_info)
            
            # Mulai bab baru
            current_title = heading_el.text.strip()
            current_start_chunk_id = chunk.chunk_id
            current_chunks = [chunk.chunk_id]
            current_texts = [chunk_text] if chunk_text else []
        else:
            if heading_el and not current_texts:
                current_title = heading_el.text.strip()
            current_chunks.append(chunk.chunk_id)
            if chunk_text:
                current_texts.append(chunk_text)
                
    if current_texts or current_chunks:
        chap_info = {
            "chapter_index": len(chapters),
            "title": current_title,
            "start_chunk_id": current_start_chunk_id,
            "chunk_ids": list(current_chunks),
            "text": "\n\n".join(current_texts)
        }
        chapters.append(chap_info)
        
    # Jika seluruh buku tidak memiliki heading dan terdiri dari banyak chunk (>5),
    # bagi menjadi bagian-bagian setiap 5 chunk agar tetap bisa dipindai bertahap
    if len(chapters) == 1 and len(chunks) > 5:
        chapters = []
        step = 5
        for i in range(0, len(chunks), step):
            sub_chunks = chunks[i:i+step]
            sub_texts = []
            for c in sub_chunks:
                t = "\n".join([el.text for el in c.elements if el.is_text() and el.text.strip()])
                if t:
                    sub_texts.append(t)
            chap_info = {
                "chapter_index": len(chapters),
                "title": f"Bagian {len(chapters) + 1}",
                "start_chunk_id": sub_chunks[0].chunk_id,
                "chunk_ids": [c.chunk_id for c in sub_chunks],
                "text": "\n\n".join(sub_texts)
            }
            chapters.append(chap_info)
            
    chapter_start_map = {c["start_chunk_id"]: c for c in chapters}
    return chapters, chapter_start_map

def extract_series_and_volume(filename: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Ekstrak nama seri dasar dan nomor volume dari nama file.
    Mengembalikan (series_name, volume_number) atau (None, None).
    
    Contoh:
    - "Too Many Losing Heroines! - 05" -> ("Too Many Losing Heroines!", 5)
    - "The Eminence in Shadow - 06" -> ("The Eminence in Shadow", 6)
    - "Heir to a Monstermancer_ Volume 1" -> ("Heir to a Monstermancer", 1)
    - "[白石定規]魔女の旅々 第01巻" -> ("[白石定規]魔女の旅々", 1)
    - "Classroom of the Elite Vol. 2" -> ("Classroom of the Elite", 2)
    """
    if not filename:
        return None, None

    # Bersihkan ekstensi dan suffix _auto_context jika ada
    name = re.sub(r'_auto_context(\.json)?$', '', filename, flags=re.IGNORECASE)
    valid_exts = ('.epub', '.pdf', '.docx', '.txt', '.json')
    for ext in valid_exts:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    name = name.strip()

    # 1. Pola Jepang: 第01巻 / 第 1 巻
    m = re.search(r'^(.*?)(?:[\[(]?第\s*(\d+)\s*巻[\])]?)(.*?)$', name)
    if m:
        series = m.group(1).strip(" -_:\t\r\n").strip() or (m.group(3) or "").strip(" -_:\t\r\n").strip()
        series = re.sub(r'\s+', ' ', series)
        try:
            vol = int(m.group(2))
            return series, vol
        except ValueError:
            pass

    # 2. Pola Volume/Vol/V/Buku/Jilid: (Volume|Vol|V|Buku|Jilid)[\s_.-]*(\d+)
    m = re.search(r'^(.*?)(?:[\s_.-]+(?:volume|vol|v|buku|jilid)\.?[\s_.-]*(\d+))(.*?)$', name, flags=re.IGNORECASE)
    if m:
        series = m.group(1).strip(" -_:\t\r\n").strip() or (m.group(3) or "").strip(" -_:\t\r\n").strip()
        series = re.sub(r'\s+', ' ', series)
        try:
            vol = int(m.group(2))
            return series, vol
        except ValueError:
            pass

    # 3. Pola nomor di akhir: Title - 05 atau Title 05
    m = re.search(r'^(.*?)(?:[\s_.-]+(\d+))$', name)
    if m:
        series = m.group(1).strip(" -_:\t\r\n").strip()
        series = re.sub(r'\s+', ' ', series)
        try:
            vol = int(m.group(2))
            return series, vol
        except ValueError:
            pass

    return None, None

def find_previous_volume_context(current_base_name: str, context_dir: str = "data/context") -> Optional[str]:
    """
    Mencari file context dari volume sebelumnya dari seri yang sama di folder context_dir.
    Jika ditemukan beberapa volume sebelumnya (misal Vol 1..5 untuk Vol 6),
    pilih volume terbesar yang lebih kecil dari volume saat ini (Vol 5).
    """
    if not os.path.isdir(context_dir):
        return None

    current_series, current_vol = extract_series_and_volume(current_base_name)
    if not current_series or current_vol is None:
        return None

    def normalize_str(s: str) -> str:
        return re.sub(r'[^a-zA-Z0-9\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+', '', s).lower()

    norm_current = normalize_str(current_series)
    if not norm_current:
        return None

    candidates = []

    for fname in os.listdir(context_dir):
        if not fname.lower().endswith("_auto_context.json"):
            continue

        cand_series, cand_vol = extract_series_and_volume(fname)
        if not cand_series or cand_vol is None:
            continue

        norm_cand = normalize_str(cand_series)
        # Cocokkan nama seri dan pastikan nomor volume lebih kecil
        if norm_cand == norm_current and cand_vol < current_vol:
            fpath = os.path.join(context_dir, fname)
            candidates.append((cand_vol, fpath))

    if not candidates:
        return None

    # Urutkan berdasarkan nomor volume secara menurun (ambil yang terdekat / tertinggi)
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]
