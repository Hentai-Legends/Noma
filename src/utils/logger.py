import os
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger("translator")

def setup_logging(log_dir: str = "logs", log_filename: str = "translator.log") -> str:
    """
    Konfigurasi logging ke file logs/translator.log dengan rotasi otomatis (5 MB x 3 backup).
    """
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, log_filename)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)
        root_logger.addHandler(handler)

    return log_file
