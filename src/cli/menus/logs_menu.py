import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console()

def view_logs_menu() -> None:
    """
    Menu terminal untuk melihat 50 baris terakhir dari file log logs/translator.log
    dan opsi untuk mereset/mengosongkan log.
    """
    log_file = os.path.join("logs", "translator.log")

    if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
        console.print("\n[yellow]Belum ada catatan log di 'logs/translator.log'.[/]")
        Prompt.ask("\nTekan Enter untuk kembali ke Menu Utama", default="")
        return

    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        last_lines = lines[-50:]
        log_content = "".join(last_lines).strip()

        console.print("\n")
        console.print(Panel(
            log_content,
            title=f"[bold cyan]Log Aktivitas Sistem (50 Baris Terakhir)[/]",
            subtitle=f"[dim]File: {os.path.abspath(log_file)} | Total: {len(lines)} baris[/dim]",
            border_style="cyan"
        ))

        if Confirm.ask("\n[bold yellow]Ingin mengosongkan (reset) isi file log ini?[/]", default=False):
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("")
            console.print("[bold green]File log berhasil dikosongkan.[/]")
    except Exception as e:
        console.print(f"[bold red]Gagal membaca file log:[/] {e}")

    Prompt.ask("\nTekan Enter untuk kembali ke Menu Utama", default="")
