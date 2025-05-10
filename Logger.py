# logger.py
import logging
from datetime import datetime

LOG_FILE = "chat.log"

def log_to_file(username: str, message: str, log_file: str = LOG_FILE):
    """Логирует сообщение пользователя в текстовый файл."""
    try:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {username}: {message}\n")
    except Exception as e:
        logging.error(f"Ошибка при логировании в файл: {e}")

def get_last_messages(limit: int = 30, log_file: str = LOG_FILE):
    """Возвращает последние N сообщений из лог-файла."""
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return [line.strip() for line in lines[-limit:] if line.strip()]
    except FileNotFoundError:
        logging.warning(f"Файл {log_file} не найден. Возвращаю пустой список.")
        return []
    except Exception as e:
        logging.error(f"Ошибка при чтении логов: {e}")
        return []
