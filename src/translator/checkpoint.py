import json
import os
import hashlib
import datetime
from typing import Dict, Optional, List

DEFAULT_CACHE_DIR = os.path.join("data", "cache")

class CheckpointManager:
    def __init__(self, file_path: str, cache_dir: str = DEFAULT_CACHE_DIR):
        self.cache_dir = cache_dir
        self.file_path = os.path.abspath(file_path) if file_path else ""
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Migrasi otomatis jika masih ada cache lama di .cache/
        old_dir = ".cache"
        if os.path.exists(old_dir) and os.path.abspath(old_dir) != os.path.abspath(self.cache_dir):
            try:
                for f in os.listdir(old_dir):
                    if f.startswith("job_") and f.endswith(".json"):
                        src_f = os.path.join(old_dir, f)
                        dst_f = os.path.join(self.cache_dir, f)
                        if not os.path.exists(dst_f):
                            os.replace(src_f, dst_f)
                if not os.listdir(old_dir):
                    os.rmdir(old_dir)
            except Exception:
                pass
                
        self.job_id = self._generate_job_id(file_path) if file_path else ""
        self.cache_file = os.path.join(self.cache_dir, f"job_{self.job_id}.json") if self.job_id else ""
        self.state = self._load_state()

    @staticmethod
    def calculate_job_id(file_path: str) -> str:
        """Menghasilkan ID unik berdasarkan nama file dan ukurannya."""
        abs_path = os.path.abspath(file_path)
        file_size = os.path.getsize(abs_path) if os.path.exists(abs_path) else 0
        raw_str = f"{abs_path}_{file_size}"
        return hashlib.md5(raw_str.encode("utf-8")).hexdigest()[:12]

    def _generate_job_id(self, file_path: str) -> str:
        return self.calculate_job_id(file_path)

    def _load_state(self) -> dict:
        if self.cache_file and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not data.get("file_path") and self.file_path:
                        data["file_path"] = self.file_path
                    return data
            except Exception:
                pass
        return {
            "file_path": self.file_path,
            "translated_chunks": {},
            "total_chunks": None,
            "target_language": None,
            "last_updated": None
        }

    def _save_state(self):
        if not self.cache_file:
            return
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def save_chunk(self, chunk_id: int, translated_map: Dict[int, str]):
        """Menyimpan hasil terjemahan satu chunk (map index -> teks terjemahan)."""
        str_chunk_id = str(chunk_id)
        str_key_map = {str(k): v for k, v in translated_map.items()}
        if "translated_chunks" not in self.state:
            self.state["translated_chunks"] = {}
        self.state["translated_chunks"][str_chunk_id] = str_key_map
        if self.file_path and not self.state.get("file_path"):
            self.state["file_path"] = self.file_path
        self.state["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_state()

    def set_metadata(self, total_chunks: Optional[int] = None, target_language: Optional[str] = None, words_per_chunk: Optional[int] = None):
        """Menyimpan informasi tambahan seperti total chunk, bahasa sasaran, dan words_per_chunk."""
        if total_chunks is not None:
            self.state["total_chunks"] = total_chunks
        if target_language is not None:
            self.state["target_language"] = target_language
        if words_per_chunk is not None:
            self.state["words_per_chunk"] = words_per_chunk
        self.state["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_state()

    def is_chunk_translated(self, chunk_id: int) -> bool:
        return str(chunk_id) in self.state.get("translated_chunks", {})

    def get_chunk_translation(self, chunk_id: int) -> Dict[int, str]:
        """Mengambil terjemahan chunk dari cache (mengembalikan map index_int -> teks)."""
        str_chunk_id = str(chunk_id)
        chunks = self.state.get("translated_chunks", {})
        if str_chunk_id in chunks:
            raw_map = chunks[str_chunk_id]
            return {int(k): v for k, v in raw_map.items()}
        return {}

    def get_all_translations(self) -> Dict[int, Dict[int, str]]:
        """Mengambil semua chunk terjemahan yang sudah tersimpan."""
        result = {}
        chunks = self.state.get("translated_chunks", {})
        for str_cid, raw_map in chunks.items():
            try:
                cid = int(str_cid)
                result[cid] = {int(k): v for k, v in raw_map.items()}
            except ValueError:
                continue
        return result

    def get_translated_chunk_ids(self) -> List[int]:
        """Mengembalikan daftar id chunk yang sudah selesai diterjemahkan (terurut)."""
        chunks = self.state.get("translated_chunks", {})
        ids = []
        for k in chunks.keys():
            try:
                ids.append(int(k))
            except ValueError:
                pass
        return sorted(ids)

    def clear(self):
        """Menghapus file cache jika proses penerjemahan selesai sempurna."""
        if self.cache_file and os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
            except OSError:
                pass
        self.state["translated_chunks"] = {}

    @classmethod
    def list_all_cached_jobs(cls, cache_dir: str = DEFAULT_CACHE_DIR, input_dir: str = "input") -> List[Dict]:
        """
        Mendeteksi semua job yang memiliki chunk terjemahan di cache_dir.
        Mencocokkan job_id dengan file di input_dir jika file_path di cache belum ada.
        """
        if not os.path.exists(cache_dir):
            return []

        input_job_map = {}
        if os.path.exists(input_dir):
            for root, _, files in os.walk(input_dir):
                for f in files:
                    file_p = os.path.join(root, f)
                    try:
                        jid = cls.calculate_job_id(file_p)
                        input_job_map[jid] = os.path.abspath(file_p)
                    except Exception:
                        pass

        cached_jobs = []
        for fname in os.listdir(cache_dir):
            if fname.startswith("job_") and fname.endswith(".json"):
                job_id = fname[4:-5]
                cache_p = os.path.join(cache_dir, fname)
                try:
                    with open(cache_p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    translated_chunks = data.get("translated_chunks", {})
                    if not translated_chunks:
                        continue

                    file_path = data.get("file_path", "")
                    if not file_path or not os.path.exists(file_path):
                        if job_id in input_job_map:
                            file_path = input_job_map[job_id]
                            data["file_path"] = file_path
                            try:
                                with open(cache_p, "w", encoding="utf-8") as wf:
                                    json.dump(data, wf, ensure_ascii=False, indent=2)
                            except Exception:
                                pass

                    cached_jobs.append({
                        "job_id": job_id,
                        "file_path": file_path,
                        "file_name": os.path.basename(file_path) if file_path else f"Job {job_id} (File sumber tidak ditemukan)",
                        "translated_count": len(translated_chunks),
                        "total_chunks": data.get("total_chunks"),
                        "target_language": data.get("target_language"),
                        "words_per_chunk": data.get("words_per_chunk"),
                        "last_updated": data.get("last_updated"),
                        "cache_file": cache_p
                    })
                except Exception:
                    continue

        return sorted(cached_jobs, key=lambda x: x["file_name"])
