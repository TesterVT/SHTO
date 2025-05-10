import sqlite3
from functools import lru_cache
import pycountry
from twitchio.ext import commands

DB_PATH = "profiles.db"  # Путь к базе данных

# === Работа с Базой Данных ===
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                twitch_id TEXT PRIMARY KEY,
                nickname TEXT NOT NULL,
                opt_in INTEGER DEFAULT 1,
                location TEXT DEFAULT '',
                unmention INTEGER DEFAULT 0,
                tokens_remaining INTEGER DEFAULT 10000,
                country TEXT DEFAULT ''
            )
        """)
        conn.commit()

def upsert_profile(twitch_id, nickname):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM profiles WHERE twitch_id = ?", (twitch_id,))
        exists = cursor.fetchone()
        if not exists:
            cursor.execute("""
                INSERT INTO profiles (twitch_id, nickname, opt_in, location, unmention, tokens_remaining, country)
                VALUES (?, ?, 1, '', 0, 10000, '')
            """, (twitch_id, nickname))
            conn.commit()

def update_profile_field(twitch_id, field, value):
    if field not in {"opt_in", "country", "unmention", "location"}:
        raise ValueError("Недопустимое поле профиля")
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE profiles SET {field} = ? WHERE twitch_id = ?", (value, twitch_id))
        conn.commit()

def is_valid_country_code(code):
    return pycountry.countries.get(alpha_2=code.upper()) is not None

# === Кэширование ===
@lru_cache(maxsize=1024)
def get_user_data_cached(twitch_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT unmention, country, location FROM profiles WHERE twitch_id = ?", (twitch_id,))
        row = cursor.fetchone()
        if row:
            return {
                "unmention": bool(row[0]),
                "country": row[1] if row[1] else None,
                "location": row[2] if row[2] else None
            }
        return {
            "unmention": False,
            "country": None,
            "location": None
        }

# === Геттеры для использования в других модулях ===

def get_mention(ctx):
    twitch_id = str(ctx.author.id)
    data = get_user_data_cached(twitch_id)
    return "" if data["unmention"] else f"@{ctx.author.name} "

def get_country(ctx):
    twitch_id = str(ctx.author.id)
    data = get_user_data_cached(twitch_id)
    return data["country"]

def get_location(ctx):
    twitch_id = str(ctx.author.id)
    data = get_user_data_cached(twitch_id)
    return data["location"]

def get_all_owners():
    with sqlite3.connect("profiles.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nickname FROM profiles WHERE owner = 1")
        return [row[0].lower() for row in cursor.fetchall()]


def clear_user_data_cache(twitch_id):
    get_user_data_cached.cache_clear()
    get_user_data_cached(twitch_id)  # Перезагрузка

def set_country(twitch_id, country_code):
    if not is_valid_country_code(country_code):
        raise ValueError("Неверный код страны. Используйте двухбуквенный код ISO.")
    update_profile_field(twitch_id, "country", country_code)

# === Команды Twitch ===
class ProfileCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        init_db()

    @commands.command(name="set")
    async def set_command(self, ctx: commands.Context):
        args = ctx.message.content.strip().split(maxsplit=2)
        if len(args) < 3:
            await ctx.send("❌ Использование: !set <opt|unmention|country|location> <значение>")
            return

        twitch_id = str(ctx.author.id)
        nickname = ctx.author.name
        field = args[1].lower()
        value = args[2].strip()

        upsert_profile(twitch_id, nickname)

        if field == "opt":
            if value not in {"true", "false"}:
                await ctx.send("❌ opt может быть только true или false")
                return
            update_profile_field(twitch_id, "opt_in", int(value == "true"))
            await ctx.send(f"✅ opt установлен в {value}")

        elif field == "unmention":
            if value not in {"true", "false"}:
                await ctx.send("❌ unmention может быть только true или false")
                return
            update_profile_field(twitch_id, "unmention", int(value == "true"))
            get_user_data_cached.cache_clear()
            await ctx.send(f"✅ unmention установлен в {value}")

        elif field == "country":
            if not is_valid_country_code(value):
                await ctx.send("❌ Неверный код страны. Используйте двухбуквенный код ISO (например, RU, US, FR)")
                return
            set_country(twitch_id, value.upper())
            get_user_data_cached.cache_clear()
            await ctx.send(f"✅ Страна установлена в {value.upper()}")

        elif field == "location":
            if len(value) < 2:
                await ctx.send("❌ Город должен быть не короче 2 символов.")
                return
            update_profile_field(twitch_id, "location", value)
            get_user_data_cached.cache_clear()
            await ctx.send(f"✅ Локация установлена в: {value}")

        else:
            await ctx.send("❌ Неизвестное поле. Доступно: opt, unmention, country, location")
