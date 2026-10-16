import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.utils.logger import setup_logging
from src.core.pipeline import execute_translation
from src.cli.menus.novel_menu import select_novel_menu
from src.cli.menus.scanner_menu import scan_glossary_only_menu
from src.cli.menus.partial_menu import export_partial_menu
from src.cli.menus.settings_menu import manage_system_prompt_menu, manage_settings_menu
from src.cli.menus.cache_menu import manage_cache_context_menu
from src.cli.menus.logs_menu import view_logs_menu

console = Console()

def main_menu_loop() -> None:
    """
    Loop utama antarmuka terminal Gemini Novel Translator (Menu 1-8).
    """
    setup_logging()
    valid_exts = ('.epub', '.pdf', '.docx', '.txt')
    while True:
        console.print("\n")
        console.print(Panel.fit(
            f"[bold cyan]GEMINI NOVEL TRANSLATOR - MAIN MENU[/]\n"
            f"[dim]-------------------------------------[/]\n"
            f"  1. Pilih & Terjemahkan Novel [dim](Bisa Drag & Drop)[/dim]\n"
            f"  2. Pindai Glosarium & Karakter Saja [dim](Scan Glossary Only)[/dim]\n"
            f"  3. Ekstrak Terjemahan Parsial (Dari Cache)\n"
            f"  4. Edit System Prompt (Persona AI)\n"
            f"  5. Pengaturan Global (Settings)\n"
            f"  6. Kelola Cache & Konteks [dim](CRUD Cache & Context)[/dim]\n"
            f"  7. Lihat Log Sistem & Error (View Logs)\n"
            f"  8. Keluar",
            border_style="cyan"
        ))
        
        choice = Prompt.ask("Pilih menu (1-8) atau Drag & Drop file novel ke sini", default="1").strip()
        cleaned_choice = choice.strip('\'"')
        
        # Cek jika pengguna langsung drag & drop file novel ke menu utama
        if os.path.isfile(cleaned_choice) and cleaned_choice.lower().endswith(valid_exts):
            args = select_novel_menu(preselected_path=cleaned_choice)
            if args:
                execute_translation(args)
            continue

        if choice == "1":
            args = select_novel_menu()
            if args:
                execute_translation(args)
        elif choice == "2":
            scan_glossary_only_menu()
        elif choice == "3":
            export_partial_menu()
        elif choice == "4":
            manage_system_prompt_menu()
        elif choice == "5":
            manage_settings_menu()
        elif choice == "6":
            manage_cache_context_menu()
        elif choice == "7":
            view_logs_menu()
        elif choice == "8":
            console.print("[bold green]Terima kasih telah menggunakan Gemini Novel Translator![/]")
            sys.exit(0)
        else:
            console.print("[bold red]Pilihan tidak valid![/]")
