import argparse
import json
import os
from typing import Optional, Dict, Any, List

def parse_cli_args(args_list: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gemini Novel Translator CLI - Terjemahkan novel PDF, DOCX, EPUB dengan mempertahankan gambar."
    )
    parser.add_argument("-i", "--input", help="Jalur file novel input (.pdf, .docx, .epub, .txt)")
    parser.add_argument("positional_input", nargs="?", default=None, help="Jalur file novel input via drag & drop")
    parser.add_argument("-o", "--output", help="Jalur file hasil terjemahan (default: <nama_input>_translated.docx)")
    parser.add_argument("-l", "--lang", default="Bahasa Indonesia", help="Bahasa sasaran (default: Bahasa Indonesia)")
    parser.add_argument("-m", "--model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), help="Model Gemini (default: gemini-2.5-flash)")
    parser.add_argument("-w", "--words-per-chunk", type=int, default=int(os.getenv("MAX_WORDS_PER_CHUNK", "2000")), help="Batas kata per chunk (default: 2000)")
    parser.add_argument("--delay", type=float, default=1.0, help="Jeda detik antar panggilan API (default: 1.0)")
    parser.add_argument("--key", help="Gemini API Key (atau atur via GEMINI_API_KEY di .env)")
    parser.add_argument("--clear-cache", action="store_true", help="Hapus cache terjemahan lama dan mulai dari awal")
    parser.add_argument("-g", "--glossary", help="Jalur file JSON untuk daftar istilah khusus (default: glossary.json jika ada)")
    parser.add_argument("-c", "--characters", help="Jalur file JSON untuk basis data karakter (default: characters.json jika ada)")
    parser.add_argument("--auto-scan", action="store_true", help="Pindai karakter dan glosarium secara real-time tiap pergantian bab (auto_context.json)")
    parser.add_argument("--bilingual", action="store_true", help="Output teks asli (di atas) dan terjemahan (di bawah)")
    parser.add_argument("--rules", help="Jalur file JSON yang berisi daftar (list) aturan terjemahan kustom.")
    parser.add_argument("--export-partial", action="store_true", help="Ekstrak hasil terjemahan sementara yang ada di cache tanpa memanggil API.")
    parser.add_argument("--scan-only", action="store_true", help="Hanya pindai glosarium dan karakter per bab ke auto_context.json tanpa menerjemahkan teks novel.")
    
    parsed = parser.parse_args(args_list)
    if not parsed.input and parsed.positional_input:
        parsed.input = parsed.positional_input
    if parsed.input:
        parsed.input = parsed.input.strip('\'"')
    return parsed

def load_config(config_path: str = "data/config.json") -> Dict[str, Any]:
    default_cfg = {
        "target_language": "Bahasa Indonesia",
        "model_name": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "words_per_chunk": int(os.getenv("MAX_WORDS_PER_CHUNK", "2000")),
        "delay_seconds": 1.0,
        "output_format": "docx",
        "bilingual_output": False
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                default_cfg.update(json.load(f))
        except Exception:
            pass
    return default_cfg

def save_config(cfg: Dict[str, Any], config_path: str = "data/config.json") -> None:
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
