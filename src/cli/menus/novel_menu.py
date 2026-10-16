import os
from typing import Optional, Any
from rich.console import Console
from rich.prompt import Prompt, Confirm

from src.utils.config import load_config

console = Console()

def select_novel_menu(preselected_path: Optional[str] = None) -> Optional[Any]:
    """
    Menu interaktif untuk memilih file novel dari folder input/ atau drag & drop.
    Mengembalikan object argumen konfigurasi atau None jika batal.
    """
    valid_exts = ('.epub', '.pdf', '.docx', '.txt')
    selected_path = None
    
    if preselected_path:
        cleaned = preselected_path.strip('\'"')
        if os.path.isfile(cleaned) and cleaned.lower().endswith(valid_exts):
            selected_path = os.path.abspath(cleaned)
            console.print(f"\n[bold green]File terpilih via Drag & Drop:[/] [bold cyan]{os.path.basename(selected_path)}[/]")
            console.print(f"[dim]Lokasi: {selected_path}[/dim]")
        else:
            console.print(f"[bold red]File '{preselected_path}' tidak ditemukan atau format tidak didukung ({', '.join(valid_exts)})[/]")
            return None
    
    if not selected_path:
        try:
            files = [f for f in os.listdir('input') if os.path.isfile(os.path.join('input', f)) and f.lower().endswith(valid_exts)]
        except FileNotFoundError:
            files = []
        
        console.print("\n[bold cyan]--- PILIH NOVEL UNTUK DITERJEMAHKAN ---[/]")
        if files:
            console.print("[bold yellow]File yang tersedia di folder 'input/':[/]")
            for i, f in enumerate(files):
                console.print(f"  [cyan]{i+1}.[/] {f}")
            console.print("[dim]Tips: Anda dapat memilih nomor atau langsung drag & drop file novel ke jendela ini.[/dim]")
        else:
            console.print("[yellow]Folder 'input/' saat ini belum berisi file novel.[/]")
            console.print("[dim]Silakan drag & drop file novel (.epub, .pdf, .docx, .txt) ke jendela terminal ini lalu tekan Enter.[/dim]")
            
        while True:
            user_input = Prompt.ask("\n[bold white]Pilih nomor file atau Drag & Drop file ke sini (0 untuk kembali)[/]").strip()
            
            if user_input == "0":
                return None
                
            cleaned = user_input.strip('\'"')
            
            # Cek apakah nomor pilihan dari folder input/
            if cleaned.isdigit() and files:
                num = int(cleaned)
                if 1 <= num <= len(files):
                    selected_path = os.path.abspath(os.path.join("input", files[num - 1]))
                    break
                else:
                    console.print("[bold red]Nomor pilihan tidak valid![/]")
                    continue
                    
            # Cek apakah input berupa path file (drag & drop)
            if os.path.isfile(cleaned):
                if cleaned.lower().endswith(valid_exts):
                    selected_path = os.path.abspath(cleaned)
                    break
                else:
                    console.print(f"[bold red]Format file tidak didukung! Format yang didukung: {', '.join(valid_exts)}[/]")
                    continue
            else:
                # Cek juga barangkali nama file ada di folder input/ tanpa path lengkap
                check_in_input = os.path.join("input", cleaned)
                if os.path.isfile(check_in_input) and check_in_input.lower().endswith(valid_exts):
                    selected_path = os.path.abspath(check_in_input)
                    break
                console.print("[bold red]File tidak ditemukan atau format tidak valid. Silakan coba lagi.[/]")

    auto_scan = Confirm.ask("[bold white]Jalankan Auto-Scan Real-Time (Update karakter & glosarium otomatis tiap bab)?[/]", default=True)
    clear_cache = Confirm.ask("[bold white]Hapus cache terjemahan lama (mulai dari awal)?[/]", default=False)
    
    cfg = load_config()
    
    class DummyArgs:
        def __init__(self):
            self.input = selected_path
            self.output = None
            self.lang = cfg['target_language']
            self.model = cfg['model_name']
            self.words_per_chunk = cfg['words_per_chunk']
            self.delay = cfg['delay_seconds']
            self.key = None
            self.clear_cache = clear_cache
            self.glossary = None
            self.characters = None
            self.auto_scan = auto_scan
            self.bilingual = cfg.get('bilingual_output', False)
            self.export_partial = False
            
    return DummyArgs()
