import os
import threading
import logging

logging.basicConfig(filename='db_errors.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

DB_LOCK = threading.Lock()
DB_FILE = "users.txt"

class DatabaseManager:
    """Управляет чтением и записью пользователей с защитой от параллельных запросов"""

    def __init__(self, filename):
        self.filename = filename

    def load_users(self):
        """Загружает базу из файла. Возвращает словарь пользователей."""
        users = {}
        if not os.path.exists(self.filename):
            return users

        with DB_LOCK:
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or ":" not in line:
                            continue
                        parts = line.split(":")
                        if len(parts) < 7:
                            continue
                        username = parts[0]
                        users[username] = {
                            "password":  parts[1],
                            "coins":     int(parts[2]),
                            "xp":        int(parts[3]),
                            "level":     int(parts[4]),
                            "skin":      parts[5],
                            "clicks":    int(parts[6])
                        }
            except Exception as e:
                logging.error(f"Ошибка чтения БД: {e}")
        return users

    def save_users(self, users):
        """Записывает актуальное состояние пользователей в файл."""
        with DB_LOCK:
            try:
                with open(self.filename, "w", encoding="utf-8") as f:
                    for u, i in users.items():
                        f.write(
                            f"{u}:{i['password']}:{i['coins']}:{i['xp']}:"
                            f"{i['level']}:{i['skin']}:{i['clicks']}\n"
                        )
            except Exception as e:
                logging.error(f"Ошибка сохранения БД: {e}")
                raise

    def get_user(self, username):
        """Возвращает одного юзера или None."""
        users = self.load_users()
        return users.get(username)

db = DatabaseManager(DB_FILE)
