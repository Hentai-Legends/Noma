import os
import dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, FloatPrompt, Confirm

from src.utils.config import load_config, save_config

console = Console()

def manage_system_prompt_menu() -> None:
    """
    Menu terminal untuk melihat dan mengedit berkas system_prompt.txt (Persona AI).
    """
    prompt_path = "data/system_prompt.txt"
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            current_prompt = f.read().strip()
    except Exception:
        current_prompt = "(File tidak ditemukan)"
        
    console.print("\n[bold cyan]--- System Prompt (Persona AI) Saat Ini ---[/]")
    console.print(Panel(current_prompt, border_style="green"))
    
    if os.name == 'nt':
        open_editor = Confirm.ask("Buka file ini di Notepad / Editor Teks untuk diedit?", default=True)
        if open_editor:
            os.startfile(os.path.abspath(prompt_path))
            console.print("[bold yellow]File telah dibuka! Silakan edit, lalu simpan (Ctrl+S) dan tutup editor tersebut.[/]")
    else:
        console.print(f"[bold yellow]Silakan edit file secara manual di:[/] {os.path.abspath(prompt_path)}")
        
    Prompt.ask("\nTekan Enter untuk kembali ke Menu Utama", default="")

def manage_api_keys_menu() -> None:
    """
    Menu terminal untuk mengelola daftar GEMINI_API_KEY (tambah, hapus, reset).
    """
    while True:
        current_key_str = os.getenv("GEMINI_API_KEY", "")
        keys = [k.strip() for k in current_key_str.split(",") if k.strip()]
        
        console.print("\n")
        console.print(Panel.fit("[bold cyan]--- DAFTAR API KEY GEMINI ---[/]", border_style="cyan"))
        
        if not keys:
            console.print("[yellow]Belum ada API Key yang tersimpan.[/]")
        else:
            for i, key in enumerate(keys):
                masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else key
                console.print(f"  [cyan]{i+1}.[/] {masked}")
                
        console.print("\n[dim]Menu API Key:[/dim]")
        console.print("  [cyan]1.[/] Tambah API Key Baru")
        console.print("  [cyan]2.[/] Hapus API Key")
        console.print("  [cyan]3.[/] Hapus Semua")
        console.print("  [cyan]4.[/] Kembali")
        
        c = IntPrompt.ask("\nPilih opsi", choices=["1", "2", "3", "4"])
        
        if c == 1:
            new_key = Prompt.ask("Masukkan API Key baru")
            if new_key.strip():
                keys.append(new_key.strip())
                new_key_str = ",".join(keys)
                if not os.path.exists(".env"):
                    open(".env", "w").close()
                dotenv.set_key(".env", "GEMINI_API_KEY", new_key_str)
                os.environ["GEMINI_API_KEY"] = new_key_str
                console.print("[bold green]API Key berhasil ditambahkan![/]")
        elif c == 2:
            if not keys:
                console.print("[bold red]Tidak ada API Key untuk dihapus![/]")
                continue
            idx = IntPrompt.ask("Nomor API Key yang ingin dihapus", choices=[str(i+1) for i in range(len(keys))])
            removed = keys.pop(idx - 1)
            new_key_str = ",".join(keys)
            dotenv.set_key(".env", "GEMINI_API_KEY", new_key_str)
            os.environ["GEMINI_API_KEY"] = new_key_str
            console.print("[bold green]API Key berhasil dihapus![/]")
        elif c == 3:
            if not os.path.exists(".env"):
                open(".env", "w").close()
            dotenv.set_key(".env", "GEMINI_API_KEY", "")
            os.environ["GEMINI_API_KEY"] = ""
            console.print("[bold green]Semua API Key berhasil dihapus![/]")
        elif c == 4:
            break

def manage_settings_menu() -> None:
    """
    Menu terminal untuk mengonfigurasi pengaturan global (bahasa, model, chunk size, delay, format).
    """
    cfg = load_config()
    while True:
        console.print("\n")
        console.print(Panel.fit("[bold cyan]--- PENGATURAN GLOBAL ---[/]", border_style="cyan"))
        console.print(f"  [cyan]1.[/] Bahasa Target     : [bold white]{cfg['target_language']}[/]")
        console.print(f"  [cyan]2.[/] Model Gemini      : [bold magenta]{cfg['model_name']}[/]")
        console.print(f"  [cyan]3.[/] Batas Kata/Chunk  : [yellow]{cfg['words_per_chunk']}[/]")
        console.print(f"  [cyan]4.[/] Jeda Waktu (detik): [yellow]{cfg['delay_seconds']}[/]")
        console.print(f"  [cyan]5.[/] Format Output     : [green]{cfg.get('output_format', 'docx')}[/]")
        bilingual_status = "Aktif" if cfg.get('bilingual_output', False) else "Nonaktif"
        console.print(f"  [cyan]6.[/] Output Bilingual  : [yellow]{bilingual_status}[/]")
        console.print(f"  [cyan]7.[/] Kelola API Key    : [yellow](List API Keys)[/]")
        console.print("  [cyan]8.[/] Kembali ke Menu Utama")
        
        c = IntPrompt.ask("\nPilih pengaturan yang ingin diubah", choices=["1", "2", "3", "4", "5", "6", "7", "8"])
        if c == 1:
            cfg['target_language'] = Prompt.ask("Masukkan Bahasa Target baru", default=cfg['target_language'])
        elif c == 2:
            models = [
                "gemini-2.5-flash",
                "gemini-2-flash",
                "gemini-2.5-pro",
                "gemini-2.5-flash-lite",
                "gemini-3-flash",
                "gemini-3.1-pro",
                "gemini-3.1-flash-lite",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.6-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
            ]
            console.print("\n[bold cyan]--- PILIH MODEL GEMINI ---[/]")
            for idx, m_id in enumerate(models, 1):
                is_curr = " [bold green](Aktif)[/]" if cfg['model_name'] == m_id else ""
                console.print(f"  [cyan]{idx}.[/] [bold white]{m_id}[/]{is_curr}")
            console.print(f"  [cyan]{len(models) + 1}.[/] [yellow]Ketik Manual Nama Model...[/]")
            console.print("  [cyan]0.[/] Batal")
            
            choice_m = Prompt.ask("\nPilih nomor model", choices=[str(i) for i in range(len(models) + 2)], default="1")
            if choice_m == "0":
                continue
            elif int(choice_m) <= len(models):
                cfg['model_name'] = models[int(choice_m) - 1]
            else:
                custom_m = Prompt.ask("Masukkan nama model Gemini", default=cfg['model_name']).strip()
                if custom_m:
                    cfg['model_name'] = custom_m

        elif c == 3:
            cfg['words_per_chunk'] = IntPrompt.ask("Masukkan Batas Kata per Chunk", default=cfg['words_per_chunk'])
        elif c == 4:
            cfg['delay_seconds'] = FloatPrompt.ask("Masukkan Jeda Waktu (detik)", default=cfg['delay_seconds'])
        elif c == 5:
            formats = [
                ("docx", "Microsoft Word (.docx) - Format standar, preservasi gambar & margin dinamis"),
                ("epub", "Electronic Publication (.epub) - Format eBook standar e-Reader / HP"),
                ("pdf", "Portable Document Format (.pdf) - Tata letak rapi siap cetak"),
                ("txt", "Plain Text (.txt) - Teks polos ringan tanpa gambar"),
            ]
            console.print("\n[bold cyan]--- PILIH FORMAT OUTPUT DOKUMEN ---[/]")
            curr_fmt = cfg.get('output_format', 'docx').lower()
            for idx, (fmt_id, fmt_desc) in enumerate(formats, 1):
                is_curr = " [bold green](Aktif)[/]" if curr_fmt == fmt_id else ""
                console.print(f"  [cyan]{idx}.[/] [bold white]{fmt_id.upper()}[/]{is_curr}\n      [dim]-> {fmt_desc}[/dim]")
            console.print("  [cyan]0.[/] Batal")
            
            choice_f = Prompt.ask("\nPilih nomor format", choices=[str(i) for i in range(len(formats) + 1)], default="1")
            if choice_f == "0":
                continue
            else:
                cfg['output_format'] = formats[int(choice_f) - 1][0]
        elif c == 6:
            cfg['bilingual_output'] = Confirm.ask("Aktifkan Output Bilingual (Teks Asli di atas Terjemahan)?", default=not cfg.get('bilingual_output', False))
        elif c == 7:
            manage_api_keys_menu()
            continue
        elif c == 8:
            break
            
        save_config(cfg)
        console.print("[bold green]Pengaturan berhasil disimpan![/]")
