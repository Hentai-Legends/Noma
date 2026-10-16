import os
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt

from src.core.scanner import execute_scan_glossary_only

console = Console()

def scan_glossary_only_menu(preselected_path: Optional[str] = None) -> None:
    """
    Menu terminal untuk memilih file yang hanya akan dipindai karakter & glosariumnya.
    """
    valid_exts = ('.epub', '.pdf', '.docx', '.txt')
    selected_path = None

    if preselected_path:
        cleaned = preselected_path.strip('\'"')
        if os.path.isfile(cleaned) and cleaned.lower().endswith(valid_exts):
            selected_path = os.path.abspath(cleaned)
            console.print(f"\n[bold green]File terpilih:[/] [bold cyan]{os.path.basename(selected_path)}[/]")
        else:
            console.print(f"[bold red]File '{preselected_path}' tidak ditemukan atau format tidak didukung.[/]")
            return

    if not selected_path:
        input_dir = "input"
        available_files = []
        if os.path.exists(input_dir):
            available_files = sorted([f for f in os.listdir(input_dir) if f.lower().endswith(valid_exts)])

        console.print("\n[bold cyan]--- PINDAI GLOSARIUM & KARAKTER SAJA ---[/]")
        if available_files:
            console.print("[yellow]Pilih file novel yang ingin dipindai:[/]")
            for idx, fname in enumerate(available_files, 1):
                console.print(f"  [cyan]{idx}.[/] {fname}")
            console.print("\n[dim]Tips: Anda dapat memilih nomor atau langsung drag & drop file novel ke sini.[/dim]")
        else:
            console.print("[yellow]Folder 'input/' kosong. Silakan drag & drop file novel ke jendela ini.[/]")

        while True:
            choice = Prompt.ask("\nPilih nomor novel atau Drag & Drop file (0 untuk kembali)").strip()
            if choice == "0":
                return

            cleaned_choice = choice.strip('\'"')

            if os.path.isfile(cleaned_choice) and cleaned_choice.lower().endswith(valid_exts):
                selected_path = os.path.abspath(cleaned_choice)
                break
            elif choice.isdigit() and 1 <= int(choice) <= len(available_files):
                selected_path = os.path.abspath(os.path.join(input_dir, available_files[int(choice) - 1]))
                break
            else:
                check_in_input = os.path.join(input_dir, cleaned_choice)
                if os.path.isfile(check_in_input) and check_in_input.lower().endswith(valid_exts):
                    selected_path = os.path.abspath(check_in_input)
                    break
                console.print("[bold red]File tidak ditemukan atau format tidak valid. Silakan coba lagi.[/]")

    execute_scan_glossary_only(selected_path)
