import os
import re
from typing import List, Dict, Any
from rich.console import Console
from rich.panel import Panel

from src.parsers.base import ElementType, DocumentElement
from src.builder.factory import get_builder_for_file
from src.builder.base import clean_heading_title, align_chunk_translations

console = Console()

def build_partial_document(
    input_path: str,
    chunks: List[Any],
    all_translations: Dict[int, Dict[int, str]],
    mode_choice: int,
    out_format: str,
    bilingual: bool = False,
    target_language: str = "Bahasa Indonesia"
) -> str:
    """
    Menyusun file dokumen terjemahan parsial dari checkpoint/cache yang sudah selesai.
    Mode 1: Potong bersih (hanya chunk yang selesai).
    Mode 2: Dokumen hybrid (chunk selesai diterjemahkan, sisanya teks asli).
    """
    input_filename = os.path.basename(input_path)
    base_name, _ = os.path.splitext(input_filename)
    
    base_output_name = os.path.join("output", f"{base_name}_partial")
    output_path = f"{base_output_name}.{out_format}"
    counter = 1
    while os.path.exists(output_path):
        output_path = f"{base_output_name}_{counter}.{out_format}"
        counter += 1

    translations_copy = {cid: dict(mapping) for cid, mapping in all_translations.items()}
    processed_chunk_ids = set(translations_copy.keys())

    if mode_choice == 1:
        # Mode 1: Potong Bersih (Hanya chunk yang ada di cache)
        chunks_to_build = [c for c in chunks if c.chunk_id in processed_chunk_ids]
        if not chunks_to_build:
            chunks_to_build = chunks[:len(processed_chunk_ids)]

        if chunks_to_build:
            last_chunk = chunks_to_build[-1]
            notice_text = "--- [BATAS TERJEMAHAN PARSIAL: Cerita terhenti di sini karena proses belum selesai] ---"
            if not last_chunk.elements or last_chunk.elements[-1].text != notice_text:
                notice_elem = DocumentElement(
                    element_type=ElementType.PARAGRAPH,
                    text=notice_text
                )
                last_chunk.elements.append(notice_elem)
                new_idx = len(last_chunk.elements) - 1
                if last_chunk.chunk_id not in translations_copy:
                    translations_copy[last_chunk.chunk_id] = {}
                translations_copy[last_chunk.chunk_id][new_idx] = notice_text
    else:
        # Mode 2: Dokumen Lengkap / Hybrid
        chunks_to_build = chunks
        first_untranslated = next((c for c in chunks_to_build if c.chunk_id not in processed_chunk_ids), None)
        if first_untranslated and first_untranslated.elements:
            notice_text = "--- [PERHATIAN: Bagian di bawah ini belum diterjemahkan (masih bahasa asli)] ---"
            if first_untranslated.elements[0].text != notice_text:
                notice_elem = DocumentElement(
                    element_type=ElementType.PARAGRAPH,
                    text=notice_text
                )
                first_untranslated.elements.insert(0, notice_elem)
                if first_untranslated.chunk_id in translations_copy:
                    shifted = {idx + 1: val for idx, val in translations_copy[first_untranslated.chunk_id].items()}
                    shifted[0] = notice_text
                    translations_copy[first_untranslated.chunk_id] = shifted

    # Pembersihan format heading markdown '#' dan karakter markdown
    for chunk in chunks_to_build:
        chunk_trans = align_chunk_translations(chunk, translations_copy.get(chunk.chunk_id, {}))
        translations_copy[chunk.chunk_id] = chunk_trans
        for i, el in enumerate(chunk.elements):
            if el.is_text():
                translated_text = chunk_trans.get(i, el.text)
                if isinstance(translated_text, str):
                    text_stripped = translated_text.strip()
                    if text_stripped.startswith('#'):
                        match = re.match(r'^(#+)\s*(.*)', text_stripped)
                        if match:
                            el.element_type = ElementType.HEADING
                            el.heading_level = len(match.group(1))
                            chunk_trans[i] = clean_heading_title(match.group(2))
                    elif el.element_type == ElementType.HEADING:
                        chunk_trans[i] = clean_heading_title(translated_text)

    console.print(f"[bold cyan]Menyusun dokumen output ({len(chunks_to_build)} chunk)...[/]")
    builder = get_builder_for_file(output_path)
    builder.build(chunks_to_build, translations_copy, output_path, bilingual=bilingual)

    mode_label = "Potong Bersih (Selesai Saja)" if mode_choice == 1 else "Hybrid (Seluruh Buku)"
    console.print(Panel.fit(
        f"[bold green]OK BERHASIL MENGEKSTRAK DOKUMEN PARSIAL![/]\n\n"
        f"File Output   : [bold green]{output_path}[/]\n"
        f"Chunk Termasuk: [yellow]{len(chunks_to_build)} dari {len(chunks)} chunk[/]\n"
        f"Mode          : [white]{mode_label}[/]",
        border_style="green"
    ))

    return output_path
