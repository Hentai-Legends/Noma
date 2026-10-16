import os
import json
import datetime
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm

from src.utils.config import load_config
from src.parsers import get_parser_for_file
from src.translator import CheckpointManager, DEFAULT_CACHE_DIR
from src.builder.partial import build_partial_document

console = Console()

def _export_raw_cache_txt(selected_job: dict) -> None:
    """
    Mengekstrak seluruh teks terjemahan yang tersimpan di cache langsung ke file .txt,
    berguna jika file novel aslinya sudah terhapus atau hilang permanen.
    """
    job_id = selected_job.get("job_id", "")
    cache_path = os.path.join(DEFAULT_CACHE_DIR, f"job_{job_id}.json")
    if not os.path.exists(cache_path):
        legacy_path = os.path.join(".cache", f"job_{job_id}.json")
        if os.path.exists(legacy_path):
            cache_path = legacy_path
        else:
            console.print("[bold red]File cache tidak ditemukan di folder data/cache/![/]")
            return
        
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        console.print(f"[bold red]Gagal membaca cache:[/] {e}")
        return

    translated_chunks = data.get("translated_chunks", {})
    if not translated_chunks:
        console.print("[bold red]Tidak ada data terjemahan tersimpan di dalam cache ini.[/]")
        return

    sorted_chunk_ids = sorted(translated_chunks.keys(), key=lambda x: int(x) if x.isdigit() else 999999)
    
    base_title = selected_job.get("file_name", f"Novel_Job_{job_id}")
    base_name = os.path.splitext(base_title)[0]
    
    lines = [
        "=== HASIL EKSTRAKSI TEKS TERJEMAHAN (DARI CACHE) ===",
        f"Novel / Sumber : {base_title}",
        f"Bahasa Sasaran : {data.get('target_language', 'Bahasa Indonesia')}",
        f"Total Chunk    : {len(sorted_chunk_ids)} chunk tersimpan",
        f"Waktu Ekstraksi: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 55,
        ""
    ]
    
    for cid in sorted_chunk_ids:
        chunk_data = translated_chunks[cid]
        lines.append(f"\n--- [BAGIAN / CHUNK {int(cid) + 1}] ---")
        sorted_elem_keys = sorted(chunk_data.keys(), key=lambda x: int(x) if x.isdigit() else 999999)
        for ek in sorted_elem_keys:
            txt = chunk_data[ek].strip()
            if txt:
                lines.append(txt)
                
    os.makedirs("output", exist_ok=True)
    base_out = os.path.join("output", f"{base_name}_extracted_from_cache")
    out_file = f"{base_out}.txt"
    counter = 1
    while os.path.exists(out_file):
        out_file = f"{base_out}_{counter}.txt"
        counter += 1
        
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(lines))
        
    console.print(f"\n[bold green]OK Sukses! Seluruh teks terjemahan ({len(sorted_chunk_ids)} chunk) berhasil diekstrak ke:[/]")
    console.print(f"   [bold cyan]{os.path.abspath(out_file)}[/]")

def _sync_cache_to_new_path(old_job_id: str, new_path: str) -> None:
    """
    Menyinkronkan data checkpoint cache dari job_id lama ke job_id file baru
    agar progres terjemahan tetap terbaca saat novel dipindahkan lokasinya.
    """
    old_cache_path = os.path.join(DEFAULT_CACHE_DIR, f"job_{old_job_id}.json")
    if not os.path.exists(old_cache_path):
        legacy_path = os.path.join(".cache", f"job_{old_job_id}.json")
        if os.path.exists(legacy_path):
            old_cache_path = legacy_path
        else:
            return

    try:
        with open(old_cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        data["file_path"] = os.path.abspath(new_path)
        new_mgr = CheckpointManager(new_path)
        new_cache_path = new_mgr.cache_file
        
        # Simpan ke cache job baru jika job_id-nya berbeda
        if new_cache_path and new_cache_path != old_cache_path:
            with open(new_cache_path, "w", encoding="utf-8") as wf:
                json.dump(data, wf, ensure_ascii=False, indent=2)
                
        # Update juga cache lama
        with open(old_cache_path, "w", encoding="utf-8") as wf:
            json.dump(data, wf, ensure_ascii=False, indent=2)
    except Exception as e:
        console.print(f"[dim yellow]Catatan sinkronisasi cache: {e}[/dim]")

def export_partial_menu() -> None:
    """
    Menu terminal untuk mengekstrak terjemahan parsial dari checkpoint cache.
    """
    console.print("\n")
    console.print(Panel.fit("[bold cyan]--- EKSTRAK TERJEMAHAN PARSIAL (DARI CACHE) ---[/]", border_style="cyan"))
    console.print("[dim]Fitur ini menyusun dokumen novel dari bab/chunk yang tersimpan di cache tanpa memanggil API.[/dim]\n")

    cached_jobs = CheckpointManager.list_all_cached_jobs()
    if not cached_jobs:
        console.print("[bold yellow]Tidak ada progres terjemahan yang ditemukan di folder cache (data/cache/).[/]")
        Prompt.ask("\nTekan Enter untuk kembali ke Menu Utama", default="")
        return

    console.print("[bold yellow]Daftar novel dengan progres terjemahan yang tersedia:[/]")
    for i, job in enumerate(cached_jobs):
        file_status = ""
        if not job["file_path"] or not os.path.exists(job["file_path"]):
            file_status = " [red](File sumber tidak ditemukan!)[/]"
        
        total_str = f"/{job['total_chunks']}" if job.get("total_chunks") else ""
        update_str = f" | Terakhir diupdate: {job['last_updated']}" if job.get("last_updated") else ""
        console.print(f"  [cyan]{i+1}.[/] [bold white]{job['file_name']}[/]{file_status}")
        console.print(f"     [dim]Progres: [green]{job['translated_count']}{total_str} chunk tersimpan[/]{update_str}[/dim]")

    while True:
        choice = IntPrompt.ask("\nPilih nomor novel yang ingin diekstrak (atau 0 untuk kembali)", default=1)
        if choice == 0:
            return
        if 1 <= choice <= len(cached_jobs):
            break
        console.print("[bold red]Pilihan tidak valid![/]")

    selected_job = cached_jobs[choice - 1]
    input_path = selected_job["file_path"]

    # Cek apakah file ada di path lama; jika tidak, cari di input/
    if not input_path or not os.path.exists(input_path):
        possible_in_input = os.path.join("input", selected_job["file_name"])
        if os.path.isfile(possible_in_input):
            input_path = os.path.abspath(possible_in_input)
            console.print(f"[bold green]File sumber terdeteksi di folder input/:[/] [cyan]{input_path}[/]")
            _sync_cache_to_new_path(selected_job["job_id"], input_path)

    # Jika masih tidak ditemukan, tawarkan opsi penanganan interaktif
    if not input_path or not os.path.exists(input_path):
        console.print(f"\n[bold yellow]Peringatan:[/] File sumber [cyan]'{selected_job['file_name']}'[/cyan] tidak ditemukan di lokasi aslinya.")
        console.print(f"  [dim]Lokasi lama: {selected_job.get('file_path') or '(Tidak tercatat)'}[/dim]\n")
        console.print("[bold cyan]Opsi Pemulihan:[/]")
        console.print("  [cyan]1.[/] [bold green]Tentukan Lokasi Baru File Novel[/] (Drag & Drop file novel dari folder barunya)")
        console.print("  [cyan]2.[/] [bold green]Ekstrak Teks Terjemahan Saja (.txt)[/] (Langsung dari cache tanpa perlu file novel asli)")
        console.print("  [cyan]0.[/] Kembali ke Menu Utama")
        
        rec_choice = Prompt.ask("\nPilih opsi pemulihan", choices=["1", "2", "0"], default="1")
        if rec_choice == "0":
            return
        elif rec_choice == "1":
            valid_exts = ('.epub', '.pdf', '.docx', '.txt')
            while True:
                new_loc = Prompt.ask("\nDrag & Drop file novel dari lokasi barunya (atau 0 untuk batal)").strip()
                if new_loc == "0":
                    return
                cleaned = new_loc.strip('\'"')
                if os.path.isfile(cleaned) and cleaned.lower().endswith(valid_exts):
                    input_path = os.path.abspath(cleaned)
                    console.print(f"[bold green]Lokasi file baru diterima:[/] [cyan]{input_path}[/]")
                    _sync_cache_to_new_path(selected_job["job_id"], input_path)
                    break
                else:
                    console.print("[bold red]File tidak ditemukan atau format tidak valid (.epub, .pdf, .docx, .txt)! Coba lagi.[/]")
        elif rec_choice == "2":
            _export_raw_cache_txt(selected_job)
            Prompt.ask("\nTekan Enter untuk kembali ke Menu Utama", default="")
            return

    console.print("\n[bold cyan]Pilih Mode Ekstraksi Isi Dokumen:[/]")
    console.print("  [cyan]1.[/] [bold green]Potong Bersih (Hanya bab/chunk yang sudah selesai)[/] [bold yellow][Rekomendasi][/]")
    console.print("      [dim]-> Hanya menyusun bab yang sudah berhasil diterjemahkan.[/dim]")
    console.print("      [dim]-> Di akhir disematkan penanda batas terjemahan.[/dim]")
    console.print("  [cyan]2.[/] [bold green]Dokumen Lengkap / Hybrid (Fallback ke bahasa asli)[/]")
    console.print("      [dim]-> Seluruh novel tetap disusun sampai selesai.[/dim]")
    console.print("      [dim]-> Bab yang belum diterjemahkan tetap ditampilkan dalam teks aslinya.[/dim]")
    
    mode_choice = IntPrompt.ask("Pilih mode", choices=["1", "2"], default=1)

    cfg = load_config()
    default_format = cfg.get("output_format", "docx").lower().replace(".", "")
    console.print(f"\n[bold cyan]Format Output saat ini:[/] [green]{default_format}[/]")
    use_default_format = Confirm.ask("Gunakan format output ini?", default=True)
    if use_default_format:
        out_format = default_format
    else:
        fmt_options = [
            ("docx", "Microsoft Word (.docx) - Format standar, preservasi gambar"),
            ("epub", "Electronic Publication (.epub) - Format eBook e-Reader / HP"),
            ("pdf", "Portable Document Format (.pdf) - Tata letak rapi siap cetak"),
            ("txt", "Plain Text (.txt) - Teks polos tanpa gambar")
        ]
        console.print("\n[bold cyan]--- PILIH FORMAT OUTPUT ---[/]")
        for idx, (f_id, f_desc) in enumerate(fmt_options, 1):
            console.print(f"  [cyan]{idx}.[/] [bold white]{f_id.upper()}[/] [dim]({f_desc})[/dim]")
        f_idx = IntPrompt.ask("Pilih nomor format", choices=[str(i) for i in range(1, len(fmt_options) + 1)], default=1)
        out_format = fmt_options[f_idx - 1][0]

    checkpoint_mgr = CheckpointManager(input_path)
    all_translations = checkpoint_mgr.get_all_translations()

    if not all_translations:
        console.print("[bold red]Tidak ada data chunk terjemahan yang dapat dimuat dari cache![/]")
        Prompt.ask("\nTekan Enter untuk kembali ke Menu Utama", default="")
        return

    cached_wpc = checkpoint_mgr.state.get("words_per_chunk") or selected_job.get("words_per_chunk")
    current_wpc = cfg.get("words_per_chunk", 2000)
    if cached_wpc and cached_wpc != current_wpc:
        console.print(f"[yellow]Peringatan: words_per_chunk saat terjemahan ({cached_wpc}) "
                      f"berbeda dengan konfigurasi ({current_wpc}). Menggunakan nilai cache ({cached_wpc}).[/]")
        words_per_chunk = cached_wpc
    else:
        words_per_chunk = cached_wpc or current_wpc

    console.print(f"\n[cyan]Membaca dokumen sumber & memuat cache terjemahan...[/]")
    try:
        doc_parser = get_parser_for_file(input_path, max_words_per_chunk=words_per_chunk)
        chunks = doc_parser.parse(input_path)
    except Exception as e:
        console.print(f"[bold red]Gagal membaca dokumen sumber:[/] {e}")
        Prompt.ask("\nTekan Enter untuk kembali ke Menu Utama", default="")
        return

    checkpoint_mgr.set_metadata(total_chunks=len(chunks), words_per_chunk=words_per_chunk)

    try:
        build_partial_document(
            input_path=input_path,
            chunks=chunks,
            all_translations=all_translations,
            mode_choice=mode_choice,
            out_format=out_format,
            bilingual=cfg.get("bilingual_output", False),
            target_language=selected_job.get("target_language") or cfg.get("target_language", "Bahasa Indonesia")
        )
    except Exception as e:
        console.print(f"[bold red]Gagal menyusun dokumen parsial:[/] {e}")

    Prompt.ask("\nTekan Enter untuk kembali ke Menu Utama", default="")
