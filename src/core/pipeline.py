import json
import os
import re
import sys
from typing import Any, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

from src.utils.logger import logger
from src.utils.config import load_config
from src.core.context import detect_chapters_from_chunks, find_previous_volume_context
from src.core.scanner import execute_scan_glossary_only
from src.parsers import get_parser_for_file
from src.parsers.base import ElementType
from src.translator import GeminiTranslator, CheckpointManager
from src.builder import get_builder_for_file
from src.builder.base import clean_heading_title
from src.builder.partial import build_partial_document

console = Console()

def clean_and_sync_headings(chunks: List[Any], all_translations: Dict[int, Dict[int, str]]) -> None:
    """
    Ekstrak Markdown heading secara global agar bersih dari simbol `#` di semua builder
    dan memperbarui ElementType ke HEADING.
    """
    for chunk in chunks:
        chunk_trans = all_translations.get(chunk.chunk_id, {})
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
                            # Ubah teks terjemahan agar simbol `#` dan markdown dibersihkan
                            chunk_trans[i] = clean_heading_title(match.group(2))
                    elif el.element_type == ElementType.HEADING:
                        chunk_trans[i] = clean_heading_title(translated_text)

def execute_translation(args: Any) -> None:
    """
    Menjalankan alur lengkap penerjemahan novel dari membaca dokumen,
    pemindaian konteks per bab, translasi chunk demi chunk, penanganan error,
    hingga kompilasi dokumen hasil akhir.
    """
    input_path = args.input
    if not os.path.exists(input_path):
        console.print(f"[bold red]Error:[/] File input '{input_path}' tidak ditemukan.")
        sys.exit(1)

    input_filename = os.path.basename(input_path)
    base_name, _ = os.path.splitext(input_filename)

    cfg = load_config()
    out_format = cfg.get("output_format", "docx").lower().replace(".", "")
    output_path = args.output
    if not output_path:
        base_output_name = os.path.join("output", f"{base_name}_translated")
        output_path = f"{base_output_name}.{out_format}"
        counter = 1
        while os.path.exists(output_path):
            output_path = f"{base_output_name}_{counter}.{out_format}"
            counter += 1

    if getattr(args, 'export_partial', False):
        console.print(f"\n[bold cyan]Mode Ekstraksi Parsial CLI Aktif...[/]")
        doc_parser = get_parser_for_file(input_path, max_words_per_chunk=args.words_per_chunk)
        chunks = doc_parser.parse(input_path)
        checkpoint_mgr = CheckpointManager(input_path)
        all_translations = checkpoint_mgr.get_all_translations()
        if not all_translations:
            console.print("[bold red]Tidak ada data terjemahan di cache untuk file ini.[/]")
            sys.exit(1)
        build_partial_document(
            input_path=input_path,
            chunks=chunks,
            all_translations=all_translations,
            mode_choice=1,
            out_format=out_format,
            bilingual=getattr(args, 'bilingual', False),
            target_language=args.lang
        )
        sys.exit(0)

    if getattr(args, 'scan_only', False):
        execute_scan_glossary_only(args)
        sys.exit(0)

    auto_context_path = os.path.join("data", "context", f"{base_name}_auto_context.json")

    full_context_data = {}
    if os.path.exists(auto_context_path):
        try:
            with open(auto_context_path, 'r', encoding='utf-8') as f:
                full_context_data = json.load(f)
            console.print(f"[bold green]OK Auto-Context dimuat dari:[/] {auto_context_path}")
        except Exception:
            pass
    else:
        # File auto_context untuk novel/volume ini belum ada di disk!
        # Cek apakah ada file context dari volume sebelumnya dari seri yang sama
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
                    
                    # Reset _scanned_chapters agar bab-bab di volume baru tetap dipindai secara utuh
                    for lang_k, lang_val in full_context_data.items():
                        if isinstance(lang_val, dict) and "_scanned_chapters" in lang_val:
                            lang_val["_scanned_chapters"] = []
                    if "_scanned_chapters" in full_context_data:
                        full_context_data["_scanned_chapters"] = []
                    
                    # Simpan langsung ke file context volume baru
                    os.makedirs(os.path.dirname(auto_context_path), exist_ok=True)
                    with open(auto_context_path, 'w', encoding='utf-8') as f:
                        json.dump(full_context_data, f, ensure_ascii=False, indent=4)
                    
                    console.print(f"[bold green]OK Berhasil mewarisi konteks! File baru disimpan di:[/] {auto_context_path}")
                except Exception as e:
                    console.print(f"[bold yellow]Peringatan:[/] Gagal membaca konteks sebelumnya: {e}")

    target_lang_key = args.lang.lower()

    # Backward compatibility: jika "characters" atau "glossary" ada di root,
    # masukkan mereka ke "bahasa indonesia" sebagai default agar tidak hilang.
    if "characters" in full_context_data or "glossary" in full_context_data:
        migrated_data = {
            "bahasa indonesia": {
                "characters": full_context_data.get("characters", {}),
                "glossary": full_context_data.get("glossary", {})
            }
        }
        for k, v in full_context_data.items():
            if k not in ["characters", "glossary"]:
                migrated_data[k] = v
        full_context_data = migrated_data

    actual_target_key = target_lang_key
    if actual_target_key not in full_context_data and "indonesia" in actual_target_key and "indonesia" in full_context_data:
        actual_target_key = "indonesia"

    auto_context_data = full_context_data.get(actual_target_key, {})
    glossary_data = auto_context_data.get("glossary", {})
    glossary_path = args.glossary or os.path.join("data", "context", f"{base_name}_glossary.json")
    if os.path.exists(glossary_path):
        try:
            with open(glossary_path, 'r', encoding='utf-8') as f:
                glossary_data.update(json.load(f))
            console.print(f"[bold green]OK Glosarium kustom dimuat dari:[/] {glossary_path}")
        except Exception as e:
            console.print(f"[bold yellow]Peringatan:[/] Gagal memuat glosarium dari {glossary_path}: {e}")

    character_db = auto_context_data.get("characters", {})
    character_path = args.characters or os.path.join("data", "context", f"{base_name}_characters.json")
    if os.path.exists(character_path):
        try:
            with open(character_path, 'r', encoding='utf-8') as f:
                character_db.update(json.load(f))
            console.print(f"[bold green]OK Character Database kustom dimuat dari:[/] {character_path}")
        except Exception as e:
            console.print(f"[bold yellow]Peringatan:[/] Gagal memuat basis data karakter dari {character_path}: {e}")

    system_prompt_path = "data/system_prompt.txt"
    system_prompt_text = None
    if os.path.exists(system_prompt_path):
        try:
            with open(system_prompt_path, 'r', encoding='utf-8') as f:
                system_prompt_text = f.read().strip()
        except Exception:
            pass

    api_key_env = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY")
    api_key = args.key or api_key_env
    if not api_key:
        console.print("[bold red]Error:[/] GEMINI_API_KEY atau GEMINI_API_KEYS belum dikonfigurasi. Buat file `.env` atau berikan argumen `--key`.")
        sys.exit(1)
        
    keys_list = [k.strip() for k in api_key.split(",") if k.strip()]
    console.print(f"[bold cyan]> Menggunakan {len(keys_list)} API Key (Mode Round-Robin Auto-Switch)[/]")

    console.print(Panel.fit(
        f"[bold cyan]GEMINI NOVEL TRANSLATOR[/]\n"
        f"File Input    : [yellow]{input_path}[/]\n"
        f"File Output   : [green]{output_path}[/]\n"
        f"Bahasa Target : [bold white]{args.lang}[/]\n"
        f"Model Gemini  : [bold magenta]{args.model}[/]",
        title="[bold blue]Konfigurasi Tugas[/]",
        border_style="cyan"
    ))

    checkpoint_mgr = CheckpointManager(input_path)
    if args.clear_cache:
        checkpoint_mgr.clear()
        console.print("[yellow]Cache lama berhasil dibersihkan.[/]")

    words_per_chunk = args.words_per_chunk
    cached_wpc = checkpoint_mgr.state.get("words_per_chunk")
    if cached_wpc and cached_wpc != words_per_chunk and not args.clear_cache:
        console.print(f"[yellow]Peringatan: words_per_chunk pada cache ({cached_wpc}) "
                      f"berbeda dengan argumen CLI ({words_per_chunk}). Menggunakan nilai cache ({cached_wpc}) "
                      f"agar chunk ID cocok.[/]")
        words_per_chunk = cached_wpc

    console.print("\n[bold cyan][1/3] Membaca & Memecah Dokumen...[/]")
    try:
        doc_parser = get_parser_for_file(input_path, max_words_per_chunk=words_per_chunk)
        chunks = doc_parser.parse(input_path)
    except Exception as e:
        logger.error(f"Gagal membaca dokumen '{input_path}': {e}", exc_info=True)
        console.print(f"[bold red]Gagal membaca dokumen:[/] {e}")
        console.print("[yellow]Detail error selengkapnya telah dicatat di [bold cyan]logs/translator.log[/bold cyan].[/yellow]")
        sys.exit(1)

    checkpoint_mgr.set_metadata(total_chunks=len(chunks), target_language=args.lang, words_per_chunk=words_per_chunk)

    total_words = sum(c.word_count for c in chunks)
    total_images = sum(sum(1 for el in c.elements if el.is_image()) for c in chunks)
    chapters, chapter_start_map = detect_chapters_from_chunks(chunks)
    console.print(f"OK Dokumen terpetakan menjadi [bold yellow]{len(chunks)} chunk[/] (~{total_words} kata, {total_images} gambar) dalam [bold cyan]{len(chapters)} bab/bagian[/].")

    if args.auto_scan:
        console.print("[dim]> Mode Auto-Scan Real-Time aktif: glosarium & karakter diperbarui otomatis tiap pergantian bab.[/dim]")

    console.print("\n[bold cyan][2/3] Menerjemahkan via Gemini API...[/]")
    translator = GeminiTranslator(
        api_key=api_key,
        model_name=args.model,
        target_language=args.lang,
        delay_seconds=args.delay,
        glossary=glossary_data,
        character_db=character_db,
        system_prompt=system_prompt_text
    )

    all_translations = checkpoint_mgr.get_all_translations()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[green]Translating novel...", total=len(chunks))
        progress.update(task, completed=len(all_translations))

        for chunk_id, chunk in enumerate(chunks):
            # Cek apakah chunk_id ini adalah awal dari suatu bab
            if chunk_id in chapter_start_map:
                chap_info = chapter_start_map[chunk_id]
                chap_idx = chap_info["chapter_index"]
                progress.console.print(f"\n[bold magenta]>> Memasuki Bab {chap_idx+1}: '{chap_info['title']}' (Mulai di Chunk {chunk_id+1})[/]")

                if args.auto_scan:
                    scanned_chapters = full_context_data.setdefault(actual_target_key, {}).setdefault("_scanned_chapters", [])
                    if chap_idx not in scanned_chapters and len(chap_info.get("text", "").strip()) >= 50:
                        progress.console.print(f"  [cyan]> Auto-scan bab '{chap_info['title']}' untuk glosarium & karakter baru...[/]")
                        current_context = {
                            "characters": translator.character_db or {},
                            "glossary": translator.glossary or {}
                        }
                        current_state_json = json.dumps(current_context, ensure_ascii=False)
                        try:
                            updated_json_str = translator.update_novel_context(chap_info["text"], current_state_json)
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

                                scanned_chapters.append(chap_idx)
                                full_context_data[actual_target_key]["characters"] = translator.character_db
                                full_context_data[actual_target_key]["glossary"] = translator.glossary
                                full_context_data[actual_target_key]["_scanned_chapters"] = scanned_chapters

                                with open(auto_context_path, 'w', encoding='utf-8') as f:
                                    json.dump(full_context_data, f, ensure_ascii=False, indent=4)

                                new_chars_count = len(translator.character_db or {})
                                new_gloss_count = len(translator.glossary or {})
                                progress.console.print(f"[bold green]OK Glosarium & karakter diperbarui ({new_chars_count} karakter, {new_gloss_count} entri glosarium). Tersimpan ke `{auto_context_path}`.[/]")
                        except Exception as e:
                            logger.warning(f"Gagal memperbarui konteks bab '{chap_info['title']}': {e}", exc_info=True)
                            progress.console.print(f"[bold yellow]Peringatan: Gagal memperbarui konteks bab '{chap_info['title']}': {e}. Melanjutkan terjemahan...[/]")

            if checkpoint_mgr.is_chunk_translated(chunk_id):
                translated_map = checkpoint_mgr.get_chunk_translation(chunk_id)
                progress.console.print(f"  [dim]Chunk {chunk_id+1}/{len(chunks)}: Menggunakan hasil terjemahan dari cache.[/dim]")
            else:
                progress.update(task, description=f"[cyan]Translating Chunk {chunk_id+1}/{len(chunks)} ({chunk.word_count} kata)...")
                text_to_translate = chunk.get_text_for_translation()

                if text_to_translate.strip():
                    try:
                        expected_indices = {i for i, el in enumerate(chunk.elements) if el.is_text() and el.text.strip()}
                        translated_map = translator.translate_chunk_text(
                            text_to_translate,
                            expected_indices=expected_indices
                        )
                    except Exception as e:
                        logger.error(f"Error pada chunk {chunk_id+1}: {e}", exc_info=True)
                        progress.console.print(f"[bold red]Error pada chunk {chunk_id+1}:[/] {e}")
                        err_str = str(e).lower()
                        if "404" in err_str or "not found" in err_str:
                            progress.console.print(
                                "\n[bold yellow]💡 Petunjuk Pemecahan Masalah (Model 404 Not Found):[/]\n"
                                f"   Model AI saat ini: '[bold red]{args.model}[/]'.\n"
                                "   Model ini tampaknya tidak ditemukan / tidak valid di Google Gemini API.\n"
                                "   Gunakan model yang resmi tersedia, misalnya: [bold green]gemini-2.5-flash[/] atau [bold green]gemini-2.0-flash[/].\n"
                                "   Anda dapat mengubahnya di Menu 5 (Pengaturan Global) atau di file [cyan]data/config.json[/cyan]."
                            )
                        progress.console.print("[yellow]Detail error selengkapnya telah dicatat di file log [bold cyan]logs/translator.log[/bold cyan] (Menu 7).[/yellow]")
                        progress.console.print("[yellow]Proses dihentikan sementara. Anda dapat menjalankan ulang perintah yang sama nanti untuk melanjutkan (resume) dari titik ini.[/yellow]")
                        saved_translations = checkpoint_mgr.get_all_translations()
                        if saved_translations:
                            if Confirm.ask("\n[bold yellow]Ingin langsung mengekstrak dokumen hasil terjemahan sementara (parsial) sekarang?[/]", default=True):
                                try:
                                    build_partial_document(
                                        input_path=input_path,
                                        chunks=chunks,
                                        all_translations=saved_translations,
                                        mode_choice=1,
                                        out_format=out_format,
                                        bilingual=getattr(args, 'bilingual', False),
                                        target_language=args.lang
                                    )
                                except Exception as err:
                                    console.print(f"[bold red]Gagal mengekstrak dokumen sementara:[/] {err}")
                        sys.exit(1)
                else:
                    translated_map = {}

                checkpoint_mgr.save_chunk(chunk_id, translated_map)

            all_translations[chunk_id] = translated_map
            progress.advance(task)

    console.print("\n[bold cyan][3/3] Menyusun Dokumen Output...[/]")
    try:
        clean_and_sync_headings(chunks, all_translations)
                                
        builder = get_builder_for_file(output_path)
        builder.build(chunks, all_translations, output_path, bilingual=getattr(args, 'bilingual', False))
        logger.info(f"Penerjemahan berhasil diselesaikan! File disimpan di: {output_path}")
        console.print(f"[bold green]OK BERHASIL![/] File terjemahan disimpan ke: [bold green]{output_path}[/]")
    except Exception as e:
        logger.error(f"Gagal menyusun file output: {e}", exc_info=True)
        console.print(f"[bold red]Gagal menyusun file output:[/] {e}")
        console.print("[yellow]Detail error selengkapnya telah dicatat di file log [bold cyan]logs/translator.log[/bold cyan] (Menu 7).[/yellow]")
        sys.exit(1)
