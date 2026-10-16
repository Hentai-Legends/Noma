"""
Gemini Novel Translator - CLI Entry Point
Modul ini bertindak sebagai entry point CLI untuk menjalankan aplikasi penerjemah novel.
"""

import os
import sys
from dotenv import load_dotenv
from rich.console import Console

from src.utils.logger import setup_logging, logger
from src.utils.config import parse_cli_args
from src.core.pipeline import execute_translation
from src.cli.menus.novel_menu import select_novel_menu
from src.cli.menus.main_menu import main_menu_loop

console = Console()

def run_cli() -> None:
    """
    Titik masuk utama aplikasi baris perintah (CLI).
    Mendukung mode interaktif menu utama, drag-and-drop, serta CLI flag langsung.
    """
    setup_logging()
    logger.info("Aplikasi Gemini Translator dimulai.")
    try:
        # Load .env file jika ada
        load_dotenv()
        
        # Pastikan direktori-direktori penting tersedia
        os.makedirs("input", exist_ok=True)
        os.makedirs("output", exist_ok=True)
        os.makedirs("data/cache", exist_ok=True)
        os.makedirs("data/context", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        # Pastikan system_prompt.txt tersedia
        system_prompt_path = "data/system_prompt.txt"
        if not os.path.exists(system_prompt_path):
            with open(system_prompt_path, 'w', encoding='utf-8') as f:
                f.write("Anda adalah penerjemah novel profesional yang sangat berpengalaman.\n")
                f.write("Tugas Anda adalah menerjemahkan teks novel ke dalam {target_language} dengan gaya bahasa novel yang mengalir, alami, lugas, dan sesuai konteks cerita.")

        valid_exts = ('.epub', '.pdf', '.docx', '.txt')
        if len(sys.argv) == 1:
            main_menu_loop()
        elif len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
            # Kasus Drag & Drop langsung ke file start.bat di Windows Explorer
            dragged = sys.argv[1].strip('\'"')
            if os.path.isfile(dragged) and dragged.lower().endswith(valid_exts):
                args = select_novel_menu(preselected_path=dragged)
                if args:
                    execute_translation(args)
            else:
                args = parse_cli_args()
                execute_translation(args)
        else:
            args = parse_cli_args()
            execute_translation(args)
            
    except KeyboardInterrupt:
        logger.info("Proses dibatalkan oleh pengguna (Ctrl+C).")
        console.print("\n[bold yellow]⚠ Proses dibatalkan oleh pengguna (Ctrl+C). Program dihentikan secara aman.[/]")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled fatal error: {e}", exc_info=True)
        console.print(f"\n[bold red]Terjadi error fatal yang tidak tertangani:[/] {e}")
        console.print("[yellow]Detail error selengkapnya telah dicatat di file log [bold cyan]logs/translator.log[/bold cyan] (Menu 7).[/yellow]")
        sys.exit(1)

if __name__ == "__main__":
    run_cli()
