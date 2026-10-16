import os
import re
import time
import logging
from typing import Dict, Optional, Set, Any
from google import genai
from google.genai import types
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class NetworkAPIError(Exception):
    """Error jaringan/server yang layak di-retry (429, 5xx, timeout, connection)."""
    pass


class LowCoverageError(Exception):
    """Output AI kehilangan terlalu banyak index paragraf."""
    def __init__(self, missing_indices: Set[int], coverage: float, partial_result: Dict[int, str]):
        self.missing_indices = missing_indices
        self.coverage = coverage
        self.partial_result = partial_result
        super().__init__(
            f"Coverage rendah: {coverage:.0%} — "
            f"{len(missing_indices)} index hilang: {sorted(missing_indices)[:10]}..."
        )


class GeminiTranslator:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-3.0-flash",
        target_language: str = "Bahasa Indonesia",
        delay_seconds: float = 1.0,
        glossary: Optional[Dict[str, Any]] = None,
        character_db: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        coverage_threshold: float = 0.8,
        max_repair_attempts: int = 3,
        cooldown_seconds: float = 3.0,
    ):
        raw_key = api_key or os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY")
        if not raw_key:
            raise ValueError("GEMINI_API_KEY tidak ditemukan. Harap atur environment variable atau file .env.")

        self.api_keys = [k.strip() for k in raw_key.split(",") if k.strip()]
        self.clients = [
            genai.Client(api_key=key, http_options={'timeout': 300000})
            for key in self.api_keys
        ]
        self.current_client_idx = 0
        self.model_name = model_name
        self.target_language = target_language
        self.delay_seconds = delay_seconds
        self.glossary = glossary or {}
        self.character_db = character_db or {}
        self.system_prompt = system_prompt or (
            "Anda adalah penerjemah novel profesional yang sangat berpengalaman.\n"
            "Tugas Anda adalah menerjemahkan teks novel ke dalam {target_language} dengan gaya bahasa novel yang mengalir, alami, lugas, dan sesuai konteks cerita."
        )

        # Konfigurasi validasi & repair
        self.coverage_threshold = coverage_threshold
        self.max_repair_attempts = max_repair_attempts

        # Cooldown per API key: {key_index: timestamp_cooldown_selesai}
        self.cooldown_seconds = cooldown_seconds
        self._key_cooldowns: Dict[int, float] = {}

    def get_client(self):
        """
        Round-robin dengan cooldown: skip key yang sedang dalam masa cooldown.
        Jika semua key cooldown, tunggu key yang paling cepat selesai.
        """
        now = time.time()
        start_idx = self.current_client_idx

        for _ in range(len(self.clients)):
            idx = self.current_client_idx
            self.current_client_idx = (idx + 1) % len(self.clients)

            cooldown_until = self._key_cooldowns.get(idx, 0)
            if now >= cooldown_until:
                return idx, self.clients[idx]

        # Semua key sedang cooldown — tunggu yang paling cepat selesai
        min_cooldown = min(self._key_cooldowns.values())
        wait_time = max(min_cooldown - now, 1.0)
        logger.warning(f"Semua API key dalam cooldown. Menunggu {wait_time:.0f} detik...")
        time.sleep(wait_time)

        # Setelah tunggu, ambil key yang cooldown-nya sudah selesai
        self.current_client_idx = start_idx
        for _ in range(len(self.clients)):
            idx = self.current_client_idx
            self.current_client_idx = (idx + 1) % len(self.clients)
            if time.time() >= self._key_cooldowns.get(idx, 0):
                return idx, self.clients[idx]

        # Fallback: pakai key pertama
        return 0, self.clients[0]

    def _set_cooldown(self, key_idx: int, seconds: Optional[float] = None):
        """Tandai API key untuk di-skip selama `seconds` detik."""
        cd = seconds if seconds is not None else self.cooldown_seconds
        self._key_cooldowns[key_idx] = time.time() + cd
        logger.info(f"API key #{key_idx} di-cooldown selama {cd:.0f} detik")

    def _build_system_instruction(self, chunk_text: str = "") -> str:
        prompt_persona = self.system_prompt.replace("{target_language}", self.target_language)
        
        base_instruction = (
            f"ATURAN SISTEM (DILARANG MENGABAIKAN ATURAN INI):\n"
            f"1. Setiap paragraf diawali dengan penanda indeks seperti `[0]`, `[1]`, `[2]`, dst.\n"
            f"2. Anda HARUS mempertahankan penanda indeks `[n]` tersebut tepat di awal setiap paragraf hasil terjemahan.\n"
            f"3. Jangan mengubah, mengurangi, atau menggabungkan nomor indeks `[n]`.\n"
            f"{prompt_persona}"
        )

        chunk_lower = chunk_text.lower()

        if self.glossary:
            active_glossary = {}
            for k, v in self.glossary.items():
                matched = k.lower() in chunk_lower
                if not matched and isinstance(v, dict):
                    orig = str(v.get("original", "")).lower()
                    trans = str(v.get("translation", "")).lower()
                    if (orig and orig in chunk_lower) or (trans and trans in chunk_lower):
                        matched = True
                if matched:
                    active_glossary[k] = v
                    
            if active_glossary:
                glossary_lines = []
                for k, v in active_glossary.items():
                    if isinstance(v, dict):
                        trans = v.get("translation") or v.get("terjemahan") or ""
                        g_type = v.get("type") or v.get("tipe") or ""
                        desc = v.get("description") or v.get("deskripsi") or ""
                        
                        type_str = f"[{g_type}] " if g_type else ""
                        if trans and trans.lower() != k.lower():
                            trans_str = f"-> terjemahkan sebagai: \"{trans}\""
                        elif trans:
                            trans_str = f"-> pertahankan sebagai: \"{trans}\""
                        else:
                            trans_str = ""
                            
                        desc_str = f" (Keterangan: {desc})" if desc else ""
                        glossary_lines.append(f"- {type_str}\"{k}\" {trans_str}{desc_str}".strip())
                    else:
                        glossary_lines.append(f"- {k} -> {v}")

                glossary_lines_str = "\n".join(glossary_lines)
                base_instruction += (
                    f"\n\nGLOSARIUM (DAFTAR ISTILAH WAJIB):\n"
                    f"Pastikan untuk menerjemahkan atau mempertahankan istilah berikut persis seperti daftar di bawah ini:\n"
                    f"{glossary_lines_str}"
                )

        if self.character_db:
            char_lines = "\n".join([f"- {k}: {v}" for k, v in self.character_db.items()])
            base_instruction += (
                f"\n\nDATABASE KARAKTER (PERSONA & GAYA BAHASA):\n"
                f"Gunakan informasi berikut untuk menyesuaikan tingkat kesopanan, nada bicara (tone), dan kata ganti (aku/saya/kamu/kau) yang digunakan oleh setiap karakter dalam dialog:\n"
                f"{char_lines}"
            )

        return base_instruction

    def _call_api(self, prompt: str, system_instruction: str) -> str:
        """
        Panggil Gemini API dengan retry untuk error jaringan/server.
        Menangani 429, 5xx, timeout, dan connection error.
        """
        last_exception = None

        for attempt in range(10):
            key_idx, client = self.get_client()
            try:
                logger.info(f"Mengirim chunk ke Gemini API (Model: {self.model_name}, Key #{key_idx+1}, Percobaan #{attempt+1})")
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.3,
                )
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )

                if self.delay_seconds > 0:
                    time.sleep(self.delay_seconds)

                logger.info(f"Sukses menerima respons dari Gemini API (Model: {self.model_name}, Key #{key_idx+1})")
                return response.text or ""

            except Exception as e:
                error_str = str(e).lower()
                error_type = type(e).__name__

                # Deteksi error yang layak di-retry
                is_retryable = any(keyword in error_str for keyword in [
                    "429", "rate limit", "quota",
                    "500", "502", "503", "504", "internal",
                    "timeout", "timed out",
                    "connection", "network", "unavailable",
                    "resource exhausted", "overloaded",
                ])

                if is_retryable:
                    # Jika 429 / rate limit → cooldown key ini
                    if any(k in error_str for k in ["429", "rate limit", "quota", "resource exhausted"]):
                        self._set_cooldown(key_idx)
                        logger.warning(f"Key #{key_idx+1} terkena limit / kuota habis. Memasukkan key ke mode cooldown.")

                    wait_time = min(2 ** attempt * 2, 60)
                    logger.warning(
                        f"[Retry {attempt+1}/10] {error_type}: {str(e)[:150]}... "
                        f"Menunggu {wait_time}s sebelum retry."
                    )
                    time.sleep(wait_time)
                    last_exception = e
                    continue
                else:
                    # Error non-retryable (misal: invalid API key, bad request, 404 model not found)
                    logger.error(
                        f"Error non-retryable dari Gemini API (Model: {self.model_name}, Key #{key_idx+1}): {error_type}: {e}",
                        exc_info=True
                    )
                    raise

        logger.error(f"Gagal setelah 10 retry. Error terakhir: {last_exception}", exc_info=True)
        raise NetworkAPIError(f"Gagal setelah 10 retry. Error terakhir: {last_exception}")

    def translate_chunk_text(
        self,
        chunk_text: str,
        expected_indices: Optional[Set[int]] = None,
    ) -> Dict[int, str]:
        """
        Mengirimkan potongan teks berindeks ke Gemini API dan mengembalikan
        dictionary {index_int: translated_text}.
        
        Jika expected_indices diberikan, akan memvalidasi coverage dan
        melakukan repair retry jika terlalu banyak index hilang.
        """
        if not chunk_text.strip():
            return {}

        prompt = (
            f"Terjemahkan teks novel berikut ke {self.target_language}.\n"
            f"Pastikan format penanda `[n]` di awal paragraf tetap utuh.\n\n"
            f"{chunk_text}"
        )

        system_instruction = self._build_system_instruction(chunk_text)

        # Panggil API (dengan network retry internal)
        response_text = self._call_api(prompt, system_instruction)
        result = self._parse_indexed_response(response_text)

        # Validasi coverage jika expected_indices diberikan
        if expected_indices and len(expected_indices) > 0:
            returned = set(result.keys())
            missing = expected_indices - returned
            coverage = len(returned & expected_indices) / len(expected_indices)

            if missing and coverage < self.coverage_threshold:
                logger.warning(
                    f"Coverage {coverage:.0%} < threshold {self.coverage_threshold:.0%}. "
                    f"Missing: {sorted(missing)[:10]}... Memulai repair."
                )
                result = self._repair_missing_indices(
                    chunk_text, missing, result, system_instruction
                )

        return result

    def _repair_missing_indices(
        self,
        original_chunk_text: str,
        missing_indices: Set[int],
        existing_result: Dict[int, str],
        system_instruction: str,
    ) -> Dict[int, str]:
        """
        Kirim ulang HANYA paragraf yang index-nya hilang dari response sebelumnya.
        Maksimal self.max_repair_attempts kali percobaan.
        """
        lines = original_chunk_text.strip().split("\n")
        pattern = re.compile(r"^\[(\d+)\]\s*(.*)$")

        for attempt in range(self.max_repair_attempts):
            if not missing_indices:
                break

            # Filter: ambil hanya baris dengan index yang hilang
            repair_lines = []
            current_idx = None
            for line in lines:
                match = pattern.match(line.strip())
                if match:
                    idx = int(match.group(1))
                    if idx in missing_indices:
                        current_idx = idx
                        repair_lines.append(line)
                    else:
                        current_idx = None
                else:
                    # Baris lanjutan dari paragraf multi-line
                    if current_idx is not None:
                        repair_lines.append(line)

            if not repair_lines:
                break

            repair_text = "\n".join(repair_lines)
            repair_prompt = (
                f"Terjemahkan HANYA paragraf berikut ke {self.target_language}.\n"
                f"Pertahankan penanda indeks `[n]` di awal setiap paragraf.\n"
                f"JANGAN menambah atau mengubah nomor indeks.\n\n"
                f"{repair_text}"
            )

            logger.info(
                f"Repair attempt {attempt+1}/{self.max_repair_attempts}: "
                f"mengirim {len(missing_indices)} paragraf hilang."
            )

            try:
                repair_response = self._call_api(repair_prompt, system_instruction)
                repair_result = self._parse_indexed_response(repair_response)

                # Gabungkan hanya index yang memang kita minta
                for idx, text in repair_result.items():
                    if idx in missing_indices:
                        existing_result[idx] = text

                # Update missing
                missing_indices = missing_indices - set(repair_result.keys())

            except Exception as e:
                logger.warning(f"Repair attempt {attempt+1} gagal: {e}")
                break

        if missing_indices:
            logger.warning(
                f"Repair selesai tapi masih ada {len(missing_indices)} index hilang: "
                f"{sorted(missing_indices)[:10]}... Akan fallback ke teks asli."
            )

        return existing_result

    def _parse_indexed_response(self, response_text: str) -> Dict[int, str]:
        """
        Mengekstrak baris terjemahan berindeks `[0] Teks...` menjadi dictionary {0: 'Teks...'}.
        Juga membersihkan kemungkinan duplikasi penanda indeks (seperti `[0] [0] Teks...`).
        """
        result_map: Dict[int, str] = {}
        # Pattern mencocokkan `[0] Teks paragraf`
        pattern = re.compile(r"^\[(\d+)\]\s*(.*)$")

        lines = response_text.strip().split("\n")
        current_idx = None
        current_text_lines = []

        for line in lines:
            line_clean = line.strip()
            match = pattern.match(line_clean)
            if match:
                # Simpan paragraf sebelumnya jika ada
                if current_idx is not None:
                    result_map[current_idx] = "\n".join(current_text_lines).strip()
                    current_text_lines = []

                current_idx = int(match.group(1))
                text_part = match.group(2)
                # Bersihkan jika AI menduplikasi penanda indeks (misal: [0] [0] Teks... atau [0] (0) Teks...)
                while True:
                    sub_m = re.match(r"^(\[\d+\]|\(\d+\)|\b\d+[\.:\-])\s*", text_part)
                    if not sub_m:
                        break
                    text_part = text_part[sub_m.end():].strip()
                current_text_lines.append(text_part)
            else:
                if current_idx is not None:
                    current_text_lines.append(line_clean)

        if current_idx is not None and current_text_lines:
            result_map[current_idx] = "\n".join(current_text_lines).strip()

        # Pembersihan menyeluruh di level akhir setiap nilai
        for k in list(result_map.keys()):
            val = result_map[k]
            while True:
                sub_m = re.match(r"^(\[\d+\]|\(\d+\)|\b\d+[\.:\-])\s*", val)
                if not sub_m:
                    break
                val = val[sub_m.end():].strip()
            result_map[k] = val

        return result_map

    @retry(
        stop=stop_after_attempt(15),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        reraise=True
    )
    def update_novel_context(self, next_text: str, current_state_json: str) -> str:
        """
        Memindai teks bab baru untuk mengekstrak atau memperbarui daftar karakter dan glosarium.
        Mengembalikan string berformat JSON yang telah diperbarui.
        """
        prompt = (
            "Anda adalah asisten penerjemah novel profesional.\n"
            "Tugas Anda adalah memperbarui database karakter dan glosarium berdasarkan teks cerita (Bab) terbaru.\n\n"
            "STATE JSON SAAT INI:\n"
            f"{current_state_json}\n\n"
            "INSTRUKSI:\n"
            "1. Bacalah teks bab terbaru di bawah ini.\n"
            f"2. PENTING: Tuliskan SEMUA hasil ekstraksi deskripsi karakter (seperti sifat, gaya bicara) maupun arti glosarium dalam bahasa: {self.target_language}.\n"
            "3. Jika ada karakter baru yang muncul, tambahkan ke dalam kamus 'characters' beserta sifat, gaya bicara, dan kata ganti yang mereka gunakan.\n"
            "4. Jika karakter yang sudah ada menunjukkan sifat atau gaya bicara baru yang penting, perbarui deskripsinya.\n"
            f"5. Jika ada istilah khusus baru (seperti nama tempat/lokasi, sihir/skill, item/senjata, makanan, organisasi/klub, gelar kehormatan, atau istilah budaya/adat), tambahkan ke kamus 'glossary' dengan struktur objek:\n"
            f'   "Nama Istilah": {{\n'
            f'       "translation": "terjemahan istilah ke {self.target_language} (atau pertahankan istilah asli jika nama khas/proper noun)",\n'
            f'       "type": "kategori istilah (misal: lokasi, skill, item, makanan, organisasi, gelar, budaya, dll.)",\n'
            f'       "description": "penjelasan ringkas mengenai arti atau konteks istilah tersebut"\n'
            f'   }}\n'
            "   (Jika ada istilah lama di glossary yang masih berformat string teks biasa, Anda boleh memperbaruinya ke format objek di atas).\n"
            "6. JANGAN MENGHAPUS karakter atau istilah yang sudah ada di State JSON Saat Ini. Hanya tambah atau perbarui.\n"
            "7. Format keluaran WAJIB berupa JSON murni tanpa blok markdown (```json). Struktur harus sama persis seperti state saat ini.\n\n"
            f"TEKS BAB TERBARU:\n{next_text}"
        )

        config = types.GenerateContentConfig(
            system_instruction="Anda adalah asisten analisis konteks novel.",
            temperature=0.1,
            response_mime_type="application/json",
        )
        
        client_idx, client = self.get_client()
        logger.info(f"Memindai konteks novel via Gemini (Model: {self.model_name}, Key #{client_idx+1})")
        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )

            if self.delay_seconds > 0:
                time.sleep(self.delay_seconds)

            logger.info("Pemindaian konteks bab berhasil diterima dari Gemini.")
            return response.text or current_state_json
        except Exception as e:
            logger.error(f"Gagal saat memindai konteks bab via Gemini (Model: {self.model_name}): {e}", exc_info=True)
            raise
