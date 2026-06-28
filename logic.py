import random
from database import db

XP_PER_LEVEL = 10000  # XP нужен для каждого уровня

WORDS = ["питон", "программист", "сервер", "код", "матрица", "скрипт", "база", "сайт"]

SKINS = {
    "default": {"path": "default", "name": "Базовый фон", "price": 0},
    "matrix":  {"path": "/static/matrix.jpeg", "name": "Хакерская матрица 🖥️",  "price": 1000},
    "rabbit":  {"path": "/static/rabbit.jpg",  "name": "Безумный кролик 67 🐰", "price": 2500},
}

class GameProcessor:
    """Класс для обработки всей игровой механики"""

    def __init__(self):
        self.active_games = {}  # {username: {"word": str, "guessed": list}}

    # ──────────────────────────────────────────────
    # Вспомогательные методы
    # ──────────────────────────────────────────────

    def _check_level_up(self, user: dict):
        """Повышает уровень пока хватает XP."""
        while user["xp"] >= XP_PER_LEVEL:
            user["xp"] -= XP_PER_LEVEL
            user["level"] += 1

    def _save_user(self, username: str, user: dict):
        """Загружает всю БД, обновляет одного юзера, сохраняет."""
        users = db.load_users()
        users[username] = user
        db.save_users(users)

    # ──────────────────────────────────────────────
    # Кликер
    # ──────────────────────────────────────────────

    def handle_click(self, username: str, click_type: str = "normal"):
        """Обрабатывает клик пользователя. Возвращает обновлённые данные или None."""
        users = db.load_users()
        if username not in users:
            return None

        user = users[username]
        result_type = click_type

        if click_type == "bonus":
            user["coins"] += 50
            user["xp"]    += 50

        elif click_type == "penalty":
            user["coins"] = max(0, user["coins"] - 20)

        else:
            # 5% шанс на крит
            if random.random() < 0.05:
                user["coins"]  += 100
                user["xp"]     += 50
                user["clicks"] += 1
                result_type = "crit"
            else:
                user["coins"]  += 0
                user["xp"]     += 0
                user["clicks"] += 1
                result_type = "normal"

        self._check_level_up(user)
        db.save_users(users)

        return {
            "coins":         user["coins"],
            "clicks":        user["clicks"],
            "xp":            user["xp"],
            "level":         user["level"],
            "next_level_xp": XP_PER_LEVEL,
            "skin":          user["skin"],
            "click_type":    result_type,
        }

    def exchange_clicks(self, username: str, amount: int):
        """Обменивает клики на XP (курс 2:1). Возвращает данные или строку-ошибку."""
        users = db.load_users()
        if username not in users:
            return "Пользователь не найден"

        user = users[username]

        if user["level"] < 2:
            return "Нужен минимум 2 уровень!"
        if amount <= 0 or user["clicks"] < amount:
            return "Недостаточно кликов!"

        max_cap = user["level"] * 1000
        if amount > max_cap:
            return f"Максимум для вашего уровня: {max_cap}"

        user["clicks"] -= amount
        user["xp"]     += amount // 2
        self._check_level_up(user)
        db.save_users(users)

        return {
            "coins":         user["coins"],
            "clicks":        user["clicks"],
            "xp":            user["xp"],
            "level":         user["level"],
            "next_level_xp": XP_PER_LEVEL,
        }

    def buy_skin(self, username: str, skin_key: str):
        """Покупка скина по ключу ('matrix' / 'rabbit'). Возвращает данные или строку-ошибку."""
        if skin_key not in SKINS:
            return "Неизвестный скин"

        skin_info = SKINS[skin_key]
        users = db.load_users()
        if username not in users:
            return "Пользователь не найден"

        user = users[username]
        if user["coins"] < skin_info["price"]:
            return "Недостаточно монет!"

        user["coins"] -= skin_info["price"]
        user["skin"]   = skin_info["path"]
        db.save_users(users)

        return {
            "coins":         user["coins"],
            "clicks":        user["clicks"],
            "xp":            user["xp"],
            "level":         user["level"],
            "next_level_xp": XP_PER_LEVEL,
            "skin":          user["skin"],
        }

    # ──────────────────────────────────────────────
    # Игра «Угадай слово»
    # ──────────────────────────────────────────────

    def start_word_game(self, username: str):
        """Начинает новую игру — выбирает слово."""
        self.active_games[username] = {
            "word":    random.choice(WORDS),
            "guessed": []
        }

    def get_word_display(self, username: str):
        """Возвращает слово с подчёркиваниями для неугаданных букв."""
        session = self.active_games.get(username)
        if not session:
            return None
        word = session["word"]
        return " ".join(c if c in session["guessed"] else "_" for c in word)

    def check_letter(self, username: str, letter: str):
        """Проверяет букву или слово целиком. Возвращает dict с результатом."""
        session = self.active_games.get(username)
        if not session:
            return {"error": "Игра не начата"}

        user_input = letter.strip().lower()
        if not user_input:
            return {"display_word": self.get_word_display(username), "is_win": False}

        word = session["word"]
        is_win = False

        if len(user_input) == 1:
            if user_input not in session["guessed"]:
                session["guessed"].append(user_input)
            is_win = all(c in session["guessed"] for c in word)
        else:
            if user_input == word:
                is_win = True
                session["guessed"] = list(word)

        display = " ".join(c if c in session["guessed"] else "_" for c in word)

        if is_win:
            reward = self._calc_word_reward(username)
            del self.active_games[username]
            return {"display_word": display, "is_win": True, "reward": reward}

        return {"display_word": display, "is_win": False}

    def get_hint(self, username: str):
        """Подсказывает одну случайную букву за 20 монет."""
        session = self.active_games.get(username)
        if not session:
            return {"error": "Игра не начата"}

        users = db.load_users()
        user = users.get(username)
        if not user:
            return {"error": "Пользователь не найден"}

        if user["coins"] < 20:
            return {"error": "Недостаточно монет для подсказки!"}

        word = session["word"]
        remaining = [c for c in word if c not in session["guessed"]]
        if not remaining:
            return {"error": "Нет доступных букв"}

        hint_letter = random.choice(remaining)
        session["guessed"].append(hint_letter)
        user["coins"] -= 20
        db.save_users(users)

        display = " ".join(c if c in session["guessed"] else "_" for c in word)
        is_win = all(c in session["guessed"] for c in word)

        if is_win:
            reward = self._calc_word_reward(username)
            del self.active_games[username]
            return {"display_word": display, "is_win": True,
                    "letter": hint_letter, "coins": user["coins"], "reward": reward}

        return {"display_word": display, "is_win": False,
                "letter": hint_letter, "coins": user["coins"]}

    def _calc_word_reward(self, username: str):
        """Считает и начисляет награду за победу в слове."""
        users = db.load_users()
        user = users.get(username)
        if not user:
            return 0

        lvl = user["level"]
        if lvl < 5:       bonus = 0.25
        elif lvl < 10:    bonus = 0.50
        elif lvl < 15:    bonus = 0.75
        else:             bonus = 1.00

        reward = int(100 * (1 + bonus))
        user["coins"] += reward
        user["xp"]    += 100
        self._check_level_up(user)
        db.save_users(users)
        return reward


processor = GameProcessor()
