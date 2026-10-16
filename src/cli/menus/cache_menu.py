import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm

from src.translator.checkpoint import CheckpointManager

console = Console()

def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

def manage_cache_menu() -> None:
    """
    Menu CRUD untuk mengelola file checkpoint cache (data/cache/).
    """
    cache_dir = os.path.join("data", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    
    while True:
        cached_jobs = CheckpointManager.list_all_cached_jobs()
        
        console.print("\n")
        console.print(Panel.fit("[bold cyan]--- KELOLA CACHE TERJEMAHAN (data/cache/) ---[/]", border_style="cyan"))
        
        if not cached_jobs:
            console.print("[yellow]Folder cache (data/cache/) saat ini kosong. Tidak ada checkpoint terjemahan.[/]\n")
        else:
            table = Table(title="Daftar Checkpoint Terjemahan di data/cache/", border_style="cyan", header_style="bold magenta")
            table.add_column("No", justify="right", style="cyan", width=4)
            table.add_column("Nama Novel", style="bold white")
            table.add_column("Job ID", style="dim", justify="center")
            table.add_column("Progress Chunk", justify="center", style="green")
            table.add_column("Ukuran", justify="right", style="yellow")
            table.add_column("Terakhir Diupdate", justify="center", style="dim")
            
            for i, job in enumerate(cached_jobs, 1):
                cache_file_path = os.path.join(cache_dir, f"job_{job['job_id']}.json")
                file_sz = os.path.getsize(cache_file_path) if os.path.exists(cache_file_path) else 0
                sz_str = _format_size(file_sz)
                
                total_str = f"/{job['total_chunks']}" if job.get("total_chunks") else ""
                prog_str = f"{job['translated_count']}{total_str}"
                last_up = job.get("last_updated") or "-"
                
                table.add_row(str(i), job["file_name"], job["job_id"], prog_str, sz_str, last_up)
                
            console.print(table)
            
        console.print("\n[dim]Pilihan Aksi:[/dim]")
        console.print("  [cyan]1.[/] Hapus Cache Novel Tertentu")
        console.print("  [cyan]2.[/] Bersihkan SEMUA Cache (Reset)")
        console.print("  [cyan]3.[/] Buka Folder data/cache/ di File Explorer")
        console.print("  [cyan]0.[/] Kembali")
        
        choice = Prompt.ask("\nPilih opsi", choices=["1", "2", "3", "0"], default="0")
        
        if choice == "0":
            break
        elif choice == "1":
            if not cached_jobs:
                console.print("[bold red]Tidak ada file cache untuk dihapus![/]")
                continue
            idx = IntPrompt.ask(f"Pilih nomor novel yang ingin dihapus cache-nya (1-{len(cached_jobs)})", default=1)
            if 1 <= idx <= len(cached_jobs):
                target = cached_jobs[idx - 1]
                cf_path = os.path.join(cache_dir, f"job_{target['job_id']}.json")
                if Confirm.ask(f"[bold red]Yakin ingin menghapus cache '{target['file_name']}'?[/]", default=False):
                    try:
                        if os.path.exists(cf_path):
                            os.remove(cf_path)
                        console.print(f"[bold green]OK Cache untuk '{target['file_name']}' berhasil dihapus![/]")
                    except Exception as e:
                        console.print(f"[bold red]Gagal menghapus file cache:[/] {e}")
            else:
                console.print("[bold red]Nomor tidak valid![/]")
        elif choice == "2":
            if not cached_jobs:
                console.print("[bold yellow]Folder cache sudah kosong.[/]")
                continue
            if Confirm.ask("[bold red]Yakin ingin menghapus SEMUA cache terjemahan? (Proses resume tidak bisa dilanjutkan)[/]", default=False):
                try:
                    for f in os.listdir(cache_dir):
                        if f.startswith("job_") and f.endswith(".json"):
                            os.remove(os.path.join(cache_dir, f))
                    console.print("[bold green]OK Seluruh cache terjemahan berhasil dibersihkan![/]")
                except Exception as e:
                    console.print(f"[bold red]Gagal membersihkan cache:[/] {e}")
        elif choice == "3":
            if os.name == 'nt':
                os.startfile(os.path.abspath(cache_dir))
                console.print(f"[bold green]Folder dibuka:[/] {os.path.abspath(cache_dir)}")
            else:
                console.print(f"Lokasi folder: {os.path.abspath(cache_dir)}")

def _load_context_summary(file_path: str) -> dict:
    """Membaca isi file context dan menghitung ringkasan karakter & glosarium."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return {"lang": "-", "char_count": 0, "gloss_count": 0, "data": {}}

    lang_keys = [k for k in data.keys() if k not in ("characters", "glossary", "_scanned_chapters")]
    target_lang = lang_keys[0] if lang_keys else "indonesia"
    
    lang_data = data.get(target_lang, {})
    if not isinstance(lang_data, dict):
        lang_data = {}
        
    chars = lang_data.get("characters") or data.get("characters") or {}
    gloss = lang_data.get("glossary") or data.get("glossary") or {}
    
    return {
        "lang": target_lang.title(),
        "char_count": len(chars) if isinstance(chars, dict) else 0,
        "gloss_count": len(gloss) if isinstance(gloss, dict) else 0,
        "data": data,
        "chars": chars if isinstance(chars, dict) else {},
        "gloss": gloss if isinstance(gloss, dict) else {}
    }

def manage_context_menu() -> None:
    """
    Menu CRUD untuk mengelola file konteks & glosarium novel (data/context/).
    """
    ctx_dir = os.path.join("data", "context")
    os.makedirs(ctx_dir, exist_ok=True)
    
    while True:
        raw_files = sorted([f for f in os.listdir(ctx_dir) if f.endswith(".json")])
        ctx_list = []
        for f in raw_files:
            fp = os.path.join(ctx_dir, f)
            sz = os.path.getsize(fp)
            summary = _load_context_summary(fp)
            ctx_list.append({
                "file_name": f,
                "file_path": fp,
                "size_str": _format_size(sz),
                "lang": summary["lang"],
                "char_count": summary["char_count"],
                "gloss_count": summary["gloss_count"],
                "chars": summary["chars"],
                "gloss": summary["gloss"]
            })
            
        console.print("\n")
        console.print(Panel.fit("[bold cyan]--- KELOLA KONTEKS & GLOSARIUM NOVEL (data/context/) ---[/]", border_style="cyan"))
        
        if not ctx_list:
            console.print("[yellow]Belum ada file konteks novel di folder data/context/.[/]\n")
        else:
            table = Table(title="Daftar Berkas Konteks & Glosarium di data/context/", border_style="cyan", header_style="bold magenta")
            table.add_column("No", justify="right", style="cyan", width=4)
            table.add_column("Nama Berkas Konteks", style="bold white")
            table.add_column("Bahasa", justify="center", style="green")
            table.add_column("Jml Karakter", justify="center", style="yellow")
            table.add_column("Jml Glosarium", justify="center", style="magenta")
            table.add_column("Ukuran", justify="right", style="dim")
            
            for i, c in enumerate(ctx_list, 1):
                clean_name = c["file_name"].replace("_auto_context.json", "").replace(".json", "")
                table.add_row(str(i), clean_name, c["lang"], str(c["char_count"]), str(c["gloss_count"]), c["size_str"])
                
            console.print(table)
            
        console.print("\n[dim]Pilihan Aksi:[/dim]")
        console.print("  [cyan]1.[/] Pratinjau (Preview) Karakter & Glosarium")
        console.print("  [cyan]2.[/] Buka & Edit File di Notepad (Windows)")
        console.print("  [cyan]3.[/] Buat Berkas Konteks Baru (Create)")
        console.print("  [cyan]4.[/] Hapus Berkas Konteks Tertentu (Delete)")
        console.print("  [cyan]5.[/] Bersihkan SEMUA Berkas Konteks")
        console.print("  [cyan]6.[/] Buka Folder data/context/ di File Explorer")
        console.print("  [cyan]0.[/] Kembali")
        
        choice = Prompt.ask("\nPilih opsi", choices=["1", "2", "3", "4", "5", "6", "0"], default="0")
        
        if choice == "0":
            break
        elif choice == "1":
            if not ctx_list:
                console.print("[bold red]Belum ada file konteks untuk dilihat![/]")
                continue
            idx = IntPrompt.ask(f"Pilih nomor berkas konteks (1-{len(ctx_list)})", default=1)
            if 1 <= idx <= len(ctx_list):
                selected = ctx_list[idx - 1]
                console.print(f"\n[bold cyan]=== PRATINJAU KONTEKS: {selected['file_name']} ===[/]")
                
                # Tampilkan Karakter
                char_table = Table(title="Daftar Karakter", border_style="green", header_style="bold yellow")
                char_table.add_column("Nama Karakter", style="bold white", width=18)
                char_table.add_column("Gaya Bicara / Pronoun", style="cyan", width=22)
                char_table.add_column("Deskripsi & Kepribadian", style="dim")
                
                if selected["chars"]:
                    for c_name, c_info in selected["chars"].items():
                        if isinstance(c_info, dict):
                            style_str = f"Pronoun: {c_info.get('pronouns', '-')}\nStyle: {c_info.get('speaking_style', '-')}"
                            desc_str = f"{c_info.get('description', '')}\n[italic]{c_info.get('personality', '')}[/italic]".strip()
                        else:
                            style_str = "-"
                            desc_str = str(c_info)
                        char_table.add_row(c_name, style_str, desc_str)
                    console.print(char_table)
                else:
                    console.print("[yellow]Belum ada entri karakter pada berkas ini.[/]")
                    
                # Tampilkan Glosarium
                gloss_table = Table(title="Daftar Istilah & Glosarium", border_style="magenta", header_style="bold yellow")
                gloss_table.add_column("Istilah Asli", style="bold white", width=20)
                gloss_table.add_column("Terjemahan Baku", style="bold green", width=25)
                gloss_table.add_column("Tipe / Deskripsi", style="dim")
                
                if selected["gloss"]:
                    for g_key, g_val in selected["gloss"].items():
                        if isinstance(g_val, dict):
                            trans = g_val.get("translation") or g_val.get("terjemahan") or "-"
                            g_type = f"[{g_val.get('type')}] " if g_val.get('type') else ""
                            desc = g_val.get("description") or g_val.get("deskripsi") or ""
                            gloss_table.add_row(g_key, trans, f"{g_type}{desc}".strip())
                        else:
                            gloss_table.add_row(g_key, str(g_val), "-")
                    console.print(gloss_table)
                else:
                    console.print("[yellow]Belum ada entri glosarium pada berkas ini.[/]")
                    
                Prompt.ask("\nTekan Enter untuk kembali ke daftar konteks", default="")
            else:
                console.print("[bold red]Nomor tidak valid![/]")
        elif choice == "2":
            if not ctx_list:
                console.print("[bold red]Belum ada file konteks untuk diedit![/]")
                continue
            idx = IntPrompt.ask(f"Pilih nomor berkas konteks yang ingin diedit (1-{len(ctx_list)})", default=1)
            if 1 <= idx <= len(ctx_list):
                selected = ctx_list[idx - 1]
                if os.name == 'nt':
                    os.startfile(os.path.abspath(selected["file_path"]))
                    console.print(f"[bold green]File dibuka di editor:[/] {os.path.abspath(selected['file_path'])}")
                    console.print("[dim yellow]Silakan edit, lalu simpan (Ctrl+S) dan tutup editor.[/dim yellow]")
                else:
                    console.print(f"Lokasi file: {os.path.abspath(selected['file_path'])}")
                Prompt.ask("\nTekan Enter jika sudah selesai mengedit", default="")
            else:
                console.print("[bold red]Nomor tidak valid![/]")
        elif choice == "3":
            novel_name = Prompt.ask("\nMasukkan Nama Judul Novel (misal: 'Overlord Volume 1')").strip()
            if not novel_name:
                console.print("[bold red]Nama novel tidak boleh kosong![/]")
                continue
            clean_fname = f"{novel_name}_auto_context.json"
            target_fp = os.path.join(ctx_dir, clean_fname)
            if os.path.exists(target_fp):
                console.print(f"[bold yellow]Berkas konteks untuk '{novel_name}' sudah ada![/]")
                continue
            template_data = {
                "indonesia": {
                    "_scanned_chapters": [],
                    "characters": {},
                    "glossary": {}
                }
            }
            try:
                with open(target_fp, 'w', encoding='utf-8') as wf:
                    json.dump(template_data, wf, indent=4, ensure_ascii=False)
                console.print(f"[bold green]OK Berkas konteks baru berhasil dibuat:[/] [cyan]{clean_fname}[/]")
                if os.name == 'nt' and Confirm.ask("Buka file ini sekarang di Notepad untuk mulai menambahkan istilah?", default=True):
                    os.startfile(os.path.abspath(target_fp))
            except Exception as e:
                console.print(f"[bold red]Gagal membuat file konteks:[/] {e}")
        elif choice == "4":
            if not ctx_list:
                console.print("[bold red]Belum ada file konteks untuk dihapus![/]")
                continue
            idx = IntPrompt.ask(f"Pilih nomor berkas konteks yang ingin dihapus (1-{len(ctx_list)})", default=1)
            if 1 <= idx <= len(ctx_list):
                selected = ctx_list[idx - 1]
                if Confirm.ask(f"[bold red]Yakin ingin menghapus berkas konteks '{selected['file_name']}'?[/]", default=False):
                    try:
                        if os.path.exists(selected["file_path"]):
                            os.remove(selected["file_path"])
                        console.print(f"[bold green]OK Berkas '{selected['file_name']}' berhasil dihapus![/]")
                    except Exception as e:
                        console.print(f"[bold red]Gagal menghapus file konteks:[/] {e}")
            else:
                console.print("[bold red]Nomor tidak valid![/]")
        elif choice == "5":
            if not ctx_list:
                console.print("[bold yellow]Folder data/context/ sudah kosong.[/]")
                continue
            if Confirm.ask("[bold red]PERINGATAN: Yakin ingin menghapus SEMUA berkas konteks & glosarium novel?[/]", default=False):
                try:
                    for c in ctx_list:
                        if os.path.exists(c["file_path"]):
                            os.remove(c["file_path"])
                    console.print("[bold green]OK Seluruh berkas konteks berhasil dibersihkan![/]")
                except Exception as e:
                    console.print(f"[bold red]Gagal membersihkan berkas konteks:[/] {e}")
        elif choice == "6":
            if os.name == 'nt':
                os.startfile(os.path.abspath(ctx_dir))
                console.print(f"[bold green]Folder dibuka:[/] {os.path.abspath(ctx_dir)}")
            else:
                console.print(f"Lokasi folder: {os.path.abspath(ctx_dir)}")

def manage_cache_context_menu() -> None:
    """
    Menu induk pengelola Cache (data/cache/) dan Konteks (data/context/).
    """
    while True:
        console.print("\n")
        console.print(Panel.fit(
            "[bold cyan]--- KELOLA CACHE & KONTEKS NOVEL (CRUD) ---[/]\n"
            "[dim]---------------------------------------------[/]\n"
            "  [cyan]1.[/] Kelola Checkpoint Cache Terjemahan [dim](data/cache/)[/dim]\n"
            "  [cyan]2.[/] Kelola Konteks, Karakter & Glosarium [dim](data/context/)[/dim]\n"
            "  [cyan]0.[/] Kembali ke Menu Utama",
            border_style="cyan"
        ))
        
        c = Prompt.ask("Pilih opsi", choices=["1", "2", "0"], default="0")
        if c == "1":
            manage_cache_menu()
        elif c == "2":
            manage_context_menu()
        elif c == "0":
            break

def clear_cache_menu() -> None:
    """
    Fungsi alias untuk kompatibilitas mundur.
    """
    manage_cache_menu()
