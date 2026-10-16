# 📖 Noma (Novel Terjemahan)

Aplikasi CLI penerjemah novel (EPUB, DOCX, PDF, TXT) berbasis Google Gemini API dengan fitur preservasi gambar, pemotongan cerdas (_smart chunking_), dan manajemen konteks otomatis.

---

## Feature

- **Image Preservation**: Mengekstrak dan menyisipkan kembali seluruh gambar dan ilustrasi novel (EPUB, DOCX, PDF) ke posisi semula pada dokumen hasil terjemahan.
- **Multi-Format Support**: Mendukung berbagai format dokumen input (`.epub`, `.docx`, `.pdf`, `.txt`) dan menghasilkan dokumen output terjemahan (`.docx`).
- **Smart Chunking**: Membagi teks dokumen secara otomatis menjadi potongan teks terjemahan (default ≤ 2000 kata) berbasis paragraf tanpa memutus dialog atau kalimat.
- **Auto-Context & Character Continuity**: Memindai istilah khusus, gaya bahasa, dan daftar karakter secara berkala ke `data/context/` untuk menjaga konsistensi istilah antar bab maupun volume berikutnya.
- **Checkpoint & Resume Cache**: Menyimpan progres terjemahan per bagian ke dalam `data/cache/`. Jika proses terhenti akibat batas kuota token, kendala jaringan, atau listrik mati, proses dapat dilanjutkan dari potongan terakhir tanpa mengulang dari awal.
- **Partial Translation Extraction**: Memungkinkan pengguna mengekstrak hasil terjemahan sementara yang sudah ada di cache menjadi dokumen utuh tanpa memanggil API.
- **Multi-Key API Rotation**: Mendukung multiple API key dengan rotasi otomatis dan mekanisme _exponential backoff retry_ untuk memitigasi kendala _rate limit_ (HTTP 429).
- **Bilingual Output Mode**: Opsi untuk menghasilkan dokumen dwibahasa (teks bahasa asli di atas dan teks terjemahan di bawah).
- **Interactive CLI & Drag-and-Drop**: Menyediakan antarmuka menu terminal interaktif berbasis `rich` serta dukungan drag-and-drop langsung ke file `start.bat`.

---

## Quick Start

### 1. Prasyarat

- Python 3.10 atau versi yang lebih baru
- Gemini API Key dari [Google AI Studio](https://aistudio.google.com/)

### 2. Instalasi

Clone repository dan pasang pustaka yang diperlukan:

```bash
git clone https://github.com/Hentai-Legends/Noma.git
cd Noma
pip install -r requirements.txt
```

### 3. Konfigurasi API Key

Salin file `.env.example` menjadi `.env` lalu masukkan API Key Anda:

```env
# Masukkan satu atau beberapa key (pisahkan dengan koma untuk rotasi otomatis)
GEMINI_API_KEY=AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_MODEL=gemini-2.5-flash
```

### 4. Menjalankan Aplikasi

Pilih salah satu cara penggunaan berikut:

- **Metode Drag & Drop (Windows)**: Tarik dan lepaskan file novel (`.epub`, `.docx`, `.pdf`, atau `.txt`) langsung ke atas file **`start.bat`**.
- **Metode Menu Interaktif**: Jalankan script utama di terminal:
  ```bash
  python main.py
  ```

---

## CLI Command

Aplikasi dapat dijalankan langsung melalui baris perintah (_command line interface_) dengan berbagai parameter konfigurasi:

```bash
python main.py [options]
```

### Contoh Penggunaan

- **Terjemahan Dasar:**

  ```bash
  python main.py -i input/novel.epub -l "Bahasa Indonesia"
  ```

- **Menggunakan Model Tertentu dan Mode Bilingual:**

  ```bash
  python main.py -i input/novel.docx -m gemini-2.5-flash --bilingual
  ```

- **Menggunakan Glosarium & Database Karakter Kustom:**

  ```bash
  python main.py -i input/novel.pdf -g data/glossary.json -c data/characters.json
  ```

- **Ekstrak Terjemahan Parsial dari Cache (Tanpa Panggil API):**

  ```bash
  python main.py -i input/novel.epub --export-partial
  ```

- **Pindai Karakter & Glosarium Saja (Tanpa Menerjemahkan):**

  ```bash
  python main.py -i input/novel.epub --scan-only
  ```

- **Reset Cache dan Terjemahkan Ulang dari Awal:**
  ```bash
  python main.py -i input/novel.epub --clear-cache
  ```

### Daftar Parameter CLI

| Parameter           | Alias | Tipe / Default                           | Deskripsi                                                            |
| :------------------ | :---- | :--------------------------------------- | :------------------------------------------------------------------- |
| `--input`           | `-i`  | `string`                                 | Jalur file novel sumber (`.epub`, `.docx`, `.pdf`, `.txt`).          |
| `--output`          | `-o`  | `string`                                 | Jalur file hasil terjemahan (default: `<input>_translated.docx`).    |
| `--lang`            | `-l`  | `string` (default: `"Bahasa Indonesia"`) | Bahasa sasaran terjemahan.                                           |
| `--model`           | `-m`  | `string` (default: `gemini-2.5-flash`)   | Nama model Gemini yang digunakan.                                    |
| `--words-per-chunk` | `-w`  | `int` (default: `2000`)                  | Batas maksimal jumlah kata per potongan terjemahan.                  |
| `--delay`           |       | `float` (default: `1.0`)                 | Jeda waktu dalam detik antar pemanggilan API Gemini.                 |
| `--key`             |       | `string`                                 | Override Gemini API Key langsung melalui perintah CLI.               |
| `--clear-cache`     |       | _Flag_                                   | Menghapus cache lama dan memulai terjemahan dari awal.               |
| `--glossary`        | `-g`  | `string`                                 | Jalur file JSON berisi daftar glosarium istilah khusus.              |
| `--characters`      | `-c`  | `string`                                 | Jalur file JSON berisi basis data karakter novel.                    |
| `--auto-scan`       |       | _Flag_                                   | Pindai karakter dan istilah otomatis per bab ke `auto_context.json`. |
| `--bilingual`       |       | _Flag_                                   | Tampilkan teks asli dan teks terjemahan secara berdampingan.         |
| `--rules`           |       | `string`                                 | Jalur file JSON berisi aturan penerjemahan kustom.                   |
| `--export-partial`  |       | _Flag_                                   | Ekstrak dokumen terjemahan parsial dari cache tanpa memanggil API.   |
| `--scan-only`       |       | _Flag_                                   | Hanya jalankan ekstraksi glosarium/karakter tanpa menerjemahkan.     |

---

## License

Proyek ini dilisensikan di bawah lisensi [MIT](LICENSE). Anda bebas menggunakan, memodifikasi, dan mendistribusikan kode ini untuk keperluan pribadi maupun non-komersial/komersial.
