import json
import os
import re
from typing import Any
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

from src.utils.logger import logger
from src.utils.config import load_config
from src.core.context import detect_chapters_from_chunks, find_previous_volume_context
from src.parsers import get_parser_for_file
from src.translator import GeminiTranslator

console = Console()

def execute_scan_glossary_only(args_or_path: Any) -> None:
    """
    Memindai dokumen bab per bab hanya untuk mengekstrak dan memperbarui
    daftar glosarium serta basis data karakter, tanpa menerjemahkan teks novel.
    """
    cfg = load_config()
    if isinstance(args_or_path, str):
        input_path = args_or_path
        class DummyScanArgs:
            def __init__(self, p: str):
                self.input = p
                self.lang = cfg.get('target_language', 'Bahasa Indonesia')
                self.model = cfg.get('model_name', 'gemini-2.5-flash')
                self.words_per_chunk = cfg.get('words_per_chunk', 2000)
                self.delay = cfg.get('delay_seconds', 1.0)
                self.key = None
        args = DummyScanArgs(input_path)
    else:
        args = args_or_path
        input_path = args.input

    if not os.path.isfile(input_path):
        console.print(f"[bold red]Error:[/] File input '{input_path}' tidak ditemukan.")
        return

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    auto_context_path = os.path.join("data", "context", f"{base_name}_auto_context.json")

    api_key_env = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY")
    api_key = getattr(args, 'key', None) or api_key_env
    if not api_key:
        console.print("[bold red]Error:[/] GEMINI_API_KEY atau GEMINI_API_KEYS belum dikonfigurasi. Buat file `.env` atau berikan argumen `--key`.")
        return

    keys_list = [k.strip() for k in api_key.split(",") if k.strip()]
    console.print(Panel.fit(
        f"[bold magenta]PEMINDAIAN GLOSARIUM & BASIS DATA KARAKTER[/]\n"
        f"File Input    : [yellow]{input_path}[/]\n"
        f"Bahasa Target : [bold white]{args.lang}[/]\n"
        f"Model Gemini  : [bold magenta]{args.model}[/]\n"
        f"API Keys      : [cyan]{len(keys_list)} Key Aktif[/]\n"
        f"Output Context: [green]{auto_context_path}[/]",
        title="[bold blue]Konfigurasi Scan Only[/]",
        border_style="magenta"
    ))

    full_context_data = {}
    if os.path.exists(auto_context_path):
        try:
            with open(auto_context_path, 'r', encoding='utf-8') as f:
                full_context_data = json.load(f)
            console.print(f"[bold green]OK Auto-Context yang sudah ada dimuat dari:[/] {auto_context_path}")
        except Exception:
            pass
    else:
        # Cek apakah ada konteks volume sebelumnya
        prev_ctx_path = find_previous_volume_context(base_name)
        if prev_ctx_path and os.path.exists(prev_ctx_path):
            prev_name = os.path.basename(prev_ctx_path)
            console.print(f"\n[bold cyan][*] Deteksi Seri Novel:[/] Ditemukan file konteks dari volume sebelumnya:")
            console.print(f"    [yellow]{prev_name}[/]")
            if Confirm.ask(f"[bold green]Gunakan glosarium & karakter dari {prev_name} sebagai modal awal?[/]", default=True):
                try:
                    with open(prev_ctx_path, 'r', encoding='utf-8') as f:
                        inherited_data = json.load(f)
                    full_context_data = inherited_data
                    for lang_k, lang_val in full_context_data.items():
                        if isinstance(lang_val, dict) and "_scanned_chapters" in lang_val:
                            lang_val["_scanned_chapters"] = []
                    if "_scanned_chapters" in full_context_data:
                        full_context_data["_scanned_chapters"] = []
                    os.makedirs(os.path.dirname(auto_context_path), exist_ok=True)
                    with open(auto_context_path, 'w', encoding='utf-8') as f:
                        json.dump(full_context_data, f, ensure_ascii=False, indent=4)
                    console.print(f"[bold green]OK Berhasil mewarisi konteks! File baru disimpan di:[/] {auto_context_path}")
                except Exception as e:
                    console.print(f"[bold yellow]Peringatan:[/] Gagal membaca konteks sebelumnya: {e}")

    target_lang_key = args.lang.lower()
    actual_target_key = target_lang_key
    if actual_target_key not in full_context_data and "indonesia" in actual_target_key and "indonesia" in full_context_data:
        actual_target_key = "indonesia"
    if actual_target_key not in full_context_data or not isinstance(full_context_data[actual_target_key], dict):
        full_context_data[actual_target_key] = {}

    auto_context_data = full_context_data.get(actual_target_key, {})
    glossary_data = auto_context_data.get("glossary", {})
    character_db = auto_context_data.get("characters", {})

    translator = GeminiTranslator(
        api_key=api_key,
        model_name=args.model,
        target_language=args.lang,
        delay_seconds=args.delay,
        glossary=glossary_data,
        character_db=character_db
    )

    console.print("\n[bold cyan][1/2] Membaca & Memetakan Struktur Bab Dokumen...[/]")
    try:
        doc_parser = get_parser_for_file(input_path, max_words_per_chunk=args.words_per_chunk)
        chunks = doc_parser.parse(input_path)
    except Exception as e:
        logger.error(f"Gagal membaca dokumen untuk scan '{input_path}': {e}", exc_info=True)
        console.print(f"[bold red]Gagal membaca dokumen:[/] {e}")
        console.print("[yellow]Detail error selengkapnya telah dicatat di [bold cyan]logs/translator.log[/bold cyan].[/yellow]")
        return

    chapters, chapter_start_map = detect_chapters_from_chunks(chunks)
    total_words = sum(c.word_count for c in chunks)
    console.print(f"OK Dokumen terpetakan menjadi [bold cyan]{len(chapters)} bab/bagian[/] (~{total_words} kata).")

    scanned_list = full_context_data[actual_target_key].setdefault("_scanned_chapters", [])
    unscanned_chapters = [c for c in chapters if c["chapter_index"] not in scanned_list]

    if not unscanned_chapters:
        console.print(f"\n[bold green]OK Semua bab ({len(chapters)} bab) sudah selesai dipindai sebelumnya![/]")
    else:
        if len(scanned_list) > 0:
            if Confirm.ask(f"\n[yellow]Ditemukan {len(scanned_list)} bab yang sudah pernah dipindai. Ingin memindai ulang dari Bab 1?[/]", default=False):
                scanned_list.clear()
                full_context_data[actual_target_key]["_scanned_chapters"] = []
                unscanned_chapters = chapters

        console.print(f"\n[bold cyan][2/2] Memulai Pemindaian {len(unscanned_chapters)} Bab...[/]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[magenta]Memindai glosarium...", total=len(unscanned_chapters))

            for chap_info in unscanned_chapters:
                chap_idx = chap_info["chapter_index"]
                chap_title = chap_info.get("title", f"Bab {chap_idx + 1}")
                chap_text = chap_info.get("text", "")
                progress.update(task, description=f"[magenta]Memindai Bab {chap_idx+1}/{len(chapters)}: '{chap_title}'...")

                if len(chap_text.strip()) >= 50:
                    current_context = {
                        "characters": translator.character_db or {},
                        "glossary": translator.glossary or {}
                    }
                    current_state_json = json.dumps(current_context, ensure_ascii=False)
                    try:
                        updated_json_str = translator.update_novel_context(chap_text, current_state_json)
                        updated_json_str = re.sub(r'```json', '', updated_json_str)
                        updated_json_str = re.sub(r'```', '', updated_json_str).strip()
                        updated_ctx = json.loads(updated_json_str)

                        if isinstance(updated_ctx, dict):
                            new_chars = updated_ctx.get("characters")
                            if isinstance(new_chars, dict):
                                translator.character_db = new_chars
                            new_gloss = updated_ctx.get("glossary")
                            if isinstance(new_gloss, dict):
                                translator.glossary = new_gloss

                            if chap_idx not in scanned_list:
                                scanned_list.append(chap_idx)

                            full_context_data[actual_target_key]["characters"] = translator.character_db
                            full_context_data[actual_target_key]["glossary"] = translator.glossary
                            full_context_data[actual_target_key]["_scanned_chapters"] = scanned_list

                            with open(auto_context_path, 'w', encoding='utf-8') as f:
                                json.dump(full_context_data, f, ensure_ascii=False, indent=4)
                    except Exception as e:
                        logger.warning(f"Gagal memindai bab '{chap_title}': {e}", exc_info=True)
                        progress.console.print(f"[bold yellow]Peringatan: Gagal memindai bab '{chap_title}': {e}. Melanjutkan...[/]")

                progress.advance(task)

    num_chars = len(translator.character_db or {})
    num_gloss = len(translator.glossary or {})
    console.print("\n")
    console.print(Panel.fit(
        f"[bold green]OK PEMINDAIAN GLOSARIUM & BASIS DATA KARAKTER SELESAI![/]\n\n"
        f"Novel               : [yellow]{os.path.basename(input_path)}[/]\n"
        f"Total Bab Dipindai  : [bold cyan]{len(scanned_list)} dari {len(chapters)} bab[/]\n"
        f"Total Karakter      : [bold white]{num_chars} karakter[/]\n"
        f"Total Istilah Glos. : [bold white]{num_gloss} istilah[/]\n"
        f"File Hasil Disimpan : [green]{auto_context_path}[/]",
        title="[bold blue]Hasil Pemindaian Konteks[/]",
        border_style="green"
    ))

    # Tampilkan tabel pratinjau jika pengguna berminat
    if num_gloss > 0 or num_chars > 0:
        if Confirm.ask("\n[bold cyan]Tampilkan pratinjau daftar karakter & glosarium di terminal?[/]", default=False):
            if num_chars > 0:
                char_table = Table(title="[bold cyan]Basis Data Karakter Terdeteksi[/]", border_style="cyan")
                char_table.add_column("Nama Karakter", style="bold white", width=25)
                char_table.add_column("Deskripsi & Peran", style="yellow")
                char_table.add_column("Gaya Bicara / Pronoun", style="green", width=30)
                for c_name, c_data in translator.character_db.items():
                    if isinstance(c_data, dict):
                        desc = c_data.get("description", "-")
                        style_p = []
                        if c_data.get("speech_style"): style_p.append(f"Gaya: {c_data.get('speech_style')}")
                        if c_data.get("pronouns"): style_p.append(f"Kata ganti: {c_data.get('pronouns')}")
                        char_table.add_row(c_name, desc, "\n".join(style_p) if style_p else "-")
                    else:
                        char_table.add_row(c_name, str(c_data), "-")
                console.print(char_table)

            if num_gloss > 0:
                gloss_table = Table(title="[bold magenta]Daftar Istilah Glosarium Terdeteksi[/]", border_style="magenta")
                gloss_table.add_column("Istilah Asli", style="bold white", width=25)
                gloss_table.add_column("Terjemahan Sasaran", style="bold green", width=25)
                gloss_table.add_column("Tipe / Kategori", style="cyan", width=15)
                gloss_table.add_column("Penjelasan / Konteks", style="yellow")
                for g_term, g_val in translator.glossary.items():
                    if isinstance(g_val, dict):
                        trans = g_val.get("translation") or g_val.get("terjemahan") or "-"
                        g_type = g_val.get("type") or g_val.get("tipe") or "-"
                        desc = g_val.get("description") or g_val.get("deskripsi") or "-"
                        gloss_table.add_row(g_term, trans, g_type, desc)
                    else:
                        gloss_table.add_row(g_term, str(g_val), "-", "-")
                console.print(gloss_table)

    Prompt.ask("\nTekan Enter untuk kembali ke Menu Utama", default="")
