# Planning Project: Gemini Novel Translator (Python CLI)

## Deskripsi Ringkasan
Proyek ini adalah aplikasi berbasis **Python CLI** yang memanfaatkan **Gemini API** untuk menerjemahkan novel berukuran besar (format PDF, DOCX, EPUB, TXT, dll.). Aplikasi ini secara otomatis memecah dokumen novel menjadi bagian-bagian kecil (maksimal 2000 kata per bagian), menerjemahkannya, mempertahankan gambar yang ada pada novel asli, dan menggabungkan hasilnya kembali ke format `.docx` (atau format pendukung lainnya).

---

## Fitur Utama & Spesifikasi

1. **Antarmuka CLI (Command Line Interface)**
   - Dibuat menggunakan Python (dengan pustaka `rich` untuk visualisasi progress bar, status, dan logging yang interaktif).
   - Mudah dijalankan dengan perintah sederhana.

2. **Dukungan Banyak Format Input & Output**
   - **Input**: PDF, DOCX, EPUB, TXT.
   - **Output Default**: DOCX (sesuai kebutuhan `prompt.txt`), serta opsional EPUB/TXT.

3. **Pemecahan Dokumen (Smart Chunking)**
   - Memecah novel menjadi potongan teks ≤ 2000 kata per bagian.
   - Pemotongan berbasis paragraf/kalimat agar tidak memotong kata di tengah dialog atau kalimat.

4. **Preservasi Gambar (Image Preservation)**
   - Mendeteksi dan mengasingkan gambar dari file novel asli (DOCX, EPUB, PDF).
   - Mempertahankan urutan dan letak gambar relatif terhadap bab/paragraf ketika menyusun kembali file novel yang diterjemahkan.

5. **Antisipasi Token Limit & Error Handling API Gemini**
   - Integrasi SDK `google-genai` (Gemini 3.0).
   - Penanganan otomatis `Rate Limit` (HTTP 429) & `Token Limit` dengan mekanisme **Exponential Backoff & Retry**.
   - Penundaan waktu (*rate limiting delay*) otomatis jika penggunaan token mendekati kuota harian/menit.

6. **Fitur Checkpoint / Resume State**
   - Menyimpan hasil terjemahan per chunk ke file cache sementara `.cache/`.
   - Pengguna dapat melanjutkan proses terjemahan yang terputus (akibat mati listrik, gangguan koneksi, atau batas token tercapai) tanpa harus membayar token ulang dari awal.

---

## Rencana Tahapan Eksekusi (Implementation Tasks)

### Tahap 1: Inisialisasi Proyek & Struktur Modul
- [x] Buat file `requirements.txt` (`google-genai`, `python-docx`, `ebooklib`, `beautifulsoup4`, `PyMuPDF`, `rich`, `python-dotenv`, `tenacity`).
- [x] Buat file `.env.example` untuk konfigurasi `GEMINI_API_KEY`.
- [x] Susun hirarki folder modul `src/` (`parsers/`, `translator/`, `builder/`, `cli/`).

### Tahap 2: Parser Dokumen & Ekstraksi Gambar
- [x] `src/parsers/docx_parser.py`: Parser file DOCX untuk teks & gambar.
- [x] `src/parsers/epub_parser.py`: Parser file EPUB (HTML/CSS + gambar).
- [x] `src/parsers/pdf_parser.py`: Parser file PDF dengan `PyMuPDF`.
- [x] Implementasi algoritma chunking teks (≤ 2000 kata per chunk).

### Tahap 3: Modul Terjemahan Gemini & Limit Handler
- [x] `src/translator/gemini_client.py`: Integrasi SDK `google-genai` dengan prompt khusus terjemahan novel.
- [x] Terapkan penanganan backoff retry (`tenacity`) untuk HTTP 429 / rate limit.
- [x] `src/translator/checkpoint.py`: Fitur simpan & resume state terjemahan berbasis JSON cache.

### Tahap 4: Builder & Rekonstruksi Dokumen
- [x] `src/builder/docx_builder.py`: Menggabungkan teks terjemahan & gambar menjadi dokumen `.docx` utuh.
- [x] `src/builder/epub_builder.py`: Builder dokumen `.epub` (opsional).

### Tahap 5: Antarmuka CLI & Pengujian
- [x] `main.py`: Entry point CLI dengan animasi progress bar (`rich`), argument parser, dan log informatif.
- [x] Pengujian terjemahan novel sampel (DOCX, EPUB, PDF) dan verifikasi keberadaan gambar pada output `.docx`.
