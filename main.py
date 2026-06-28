import os
from fastapi import FastAPI, HTTPException, Cookie, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from database import db
from logic import processor, SKINS, XP_PER_LEVEL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Создаём папку static если нет
os.makedirs("static", exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# ──────────────────────────────────────────────
# Вспомогалка: читаем юзера из куки
# ──────────────────────────────────────────────

def decode_username(username):
    if not username:
        return None
    try:
        return bytes.fromhex(username).decode('utf-8')
    except Exception:
        return username
    
def get_current_user(username):
    u = decode_username(username)
    if not u:
        return None
    return db.get_user(u)

# ──────────────────────────────────────────────
# HTML страницы
# ──────────────────────────────────────────────

def read_html(name: str) -> str:
    with open(name, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/", response_class=HTMLResponse)
async def index():
    return read_html("index.html")

@app.get("/register-page", response_class=HTMLResponse)
async def register_page():
    return read_html("register.html")

@app.get("/menu-page", response_class=HTMLResponse)
async def menu_page():
    return read_html("menu.html")

@app.get("/clicker-game", response_class=HTMLResponse)
async def clicker_page():
    return read_html("clicker.html")

@app.get("/word-game", response_class=HTMLResponse)
async def word_game_page(username: str | None = Cookie(default=None)):
    username = decode_username(username)
    # Стартуем новую игру при открытии страницы
    if username and db.get_user(username):
        processor.start_word_game(username)
    return read_html("game.html")

# ──────────────────────────────────────────────
# Авторизация
# ──────────────────────────────────────────────

@app.post("/register")
async def register(data: dict, response: Response):
    u = data.get("username", "").strip()
    p = data.get("password", "").strip()
    if not u or not p:
        raise HTTPException(400, "Заполните все поля")

    users = db.load_users()
    if u in users:
        raise HTTPException(400, "Пользователь уже существует")

    users[u] = {
        "password": p,
        "coins":    100,
        "xp":       0,
        "level":    1,
        "skin":     "🪙",
        "clicks":   0
    }
    db.save_users(users)

    # Сохраняем имя в куки
    response.set_cookie(key="username", value=u.encode('utf-8').hex(), httponly=True)
    return {"status": "success", "redirect": "/menu-page"}

@app.post("/login")
async def login(data: dict, response: Response):
    u = data.get("username", "").strip()
    p = data.get("password", "").strip()

    users = db.load_users()
    if u not in users or users[u]["password"] != p:
        raise HTTPException(401, "Неверный логин или пароль")

    response.set_cookie(key="username", value=u.encode ('utf-8').hex(), httponly=True)
    return {"status": "success", "redirect": "/menu-page"}

@app.post("/logout")
async def logout(response: Response):
    response.delete_cookie("username")
    return {"status": "ok"}

# ──────────────────────────────────────────────
# Статистика
# ──────────────────────────────────────────────

@app.get("/get-stats")
async def get_stats(username: str | None = Cookie(default=None)):
    username = decode_username(username)
    user = get_current_user(username)
    if not username:
        raise HTTPException(401, "Не авторизован")
    return {
        "coins":         user["coins"],
        "clicks":        user["clicks"],
        "xp":            user["xp"],
        "level":         user["level"],
        "next_level_xp": XP_PER_LEVEL,
        "skin":          user["skin"],
        "username":      username,
    }

# ──────────────────────────────────────────────
# Кликер
# ──────────────────────────────────────────────

@app.post("/click")
async def click(data: dict, username: str | None = Cookie(default=None)):
    try:
        username = bytes.fromhex(username).decode('utf-8')
    except Exception:
        pass
    if not username:
        raise HTTPException(401, "Не авторизован")

    click_type = data.get("type", "normal")
    result = processor.handle_click(username, click_type)
    if result is None:
        raise HTTPException(404, "Пользователь не найден")
    return result

@app.post("/exchange-clicks")
async def exchange_clicks(data: dict, username: str | None = Cookie(default=None)):
    username = decode_username(username)
    if not username:
        raise HTTPException(401, "Не авторизован")

    amount = data.get("clicks_to_exchange", 0)
    result = processor.exchange_clicks(username, int(amount))
    if isinstance(result, str):
        raise HTTPException(400, result)
    return result

@app.post("/buy-skin")
async def buy_skin(data: dict, username: str | None = Cookie(default=None)):
    username = decode_username(username)
    if not username:
        raise HTTPException(401, "Не авторизован")

    skin_key = data.get("skin_key", "")
    result = processor.buy_skin(username, skin_key)
    if isinstance(result, str):
        raise HTTPException(400, result)
    return result

@app.get("/get-skins")
async def get_skins():
    """Возвращает список доступных скинов для магазина."""
    return [
        {"key": k, "name": v["name"], "price": v["price"], "path": v["path"]}
        for k, v in SKINS.items()
    ]

# ──────────────────────────────────────────────
# Угадай слово
# ──────────────────────────────────────────────

@app.get("/word-game-init")
async def word_game_init(username: str | None = Cookie(default=None)):
    username = decode_username(username)
    if not username:
        raise HTTPException(401, "Не авторизован")

    user = db.get_user(username)
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    display = processor.get_word_display(username) or "_ _ _ _ _"
    return {
        "display_word":  display,
        "coins":         user["coins"],
        "level":         user["level"],
        "next_level_xp": XP_PER_LEVEL,
    }

@app.post("/check-letter")
async def check_letter(data: dict, username: str | None = Cookie(default=None)):
    username = decode_username(username)
    if not username:
        raise HTTPException(401, "Не авторизован")

    letter = data.get("letter", "")
    result = processor.check_letter(username, letter)
    if "error" in result:
        raise HTTPException(400, result["error"])

    # Добавляем монеты в ответ
    user = db.get_user(username)
    result["coins"] = user["coins"] if user else 0
    return result

@app.post("/get-hint")
async def get_hint(username: str | None = Cookie(default=None)):
    username = decode_username(username)
    if not username:
        raise HTTPException(401, "Не авторизован")

    result = processor.get_hint(username)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
