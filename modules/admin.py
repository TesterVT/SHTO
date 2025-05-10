import json
import requests
from twitchio.ext import commands
import logging
import importlib
import sqlite3
import os
import sys
import os
from modules.profiles import get_mention, get_all_owners

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data import config_loader

DB_PATH = "data/admin.db"
os.makedirs("data", exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

echo_user = None  # Глобальная переменная для хранения имени пользователя

def save_config():
    config = {
        "token": TOKEN,
        "channels": CHANNELS,
        "owner_channel": OWNER_CHANNEL,
        "emote_set_id": EMOTE_SET_ID,
        "owners": OWNERS,
    }
    try:
        with open("data/config.json", "w") as f:
            json.dump(config, f, indent=4)
        logger.info("Конфигурация успешно сохранена.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении конфигурации: {e}")


TOKEN = config_loader.get_token()
CHANNELS = config_loader.get_channels()
OWNER_CHANNEL = config_loader.get_owner_channel()
OWNERS = get_all_owners()
EMOTE_SET_ID = config_loader.get_emote_set_id()

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.modules = {
            "cat": "modules.cats",
            "general": "modules.general",
            "admin": "modules.admin",
            "city": "modules.city",
            "rcon": "rcon_module",
            "weather": "modules.weather",
            "alias": "modules.alias",
            "AI": "modules.AI",
            "emote": "modules.emote_tracker",
            "holiday": "modules.holiday",
            "profile": "modules.profile"
        }
        logger.debug(f"Доступные модули: {self.modules}")
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS ignored_users (username TEXT PRIMARY KEY)""")
        self.conn.commit()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS disabled_modules (
                channel_name TEXT,
                module_name TEXT,
                PRIMARY KEY (channel_name, module_name)
            )
        """)
        self.conn.commit()


    def is_ignored(self, username: str) -> bool:
        self.cursor.execute("SELECT 1 FROM ignored_users WHERE username = ?", (username.lower(),))
        return self.cursor.fetchone() is not None

    def add_ignored_user(self, username: str):
        self.cursor.execute("INSERT OR IGNORE INTO ignored_users (username) VALUES (?)", (username.lower(),))
        self.conn.commit()

    def remove_ignored_user(self, username: str):
        self.cursor.execute("DELETE FROM ignored_users WHERE username = ?", (username.lower(),))
        self.conn.commit()

    def get_all_ignored_users(self):
        self.cursor.execute("SELECT username FROM ignored_users")
        return [row[0] for row in self.cursor.fetchall()]

    # Основной обработчик команд с префиксом !a
    @commands.command(name="a")
    async def admin_command(self, ctx: commands.Context, action: str, *args):
        if ctx.author.name.lower() not in OWNERS:
            await ctx.send(get_mention(ctx) + "У вас нет прав для использования этой команды.")
            return

        if action == "echo":
            await self.set_echo_user(ctx, *args)
        elif action == "stop":
            await self.stop_echo(ctx)
        elif action == "add_channel":
            await self.add_channel(ctx, *args)
        elif action == "reload":
            await self.reload_emotes(ctx)
        elif action == "load_module":
            await self.load_module(ctx, *args)
        elif action == "unload_module":
            await self.unload_module(ctx, *args)
        elif action == "reload_module":
            await self.reload_module(ctx, *args)
        elif action == "ignore":
            await self.ignore_user(ctx, *args)
        elif action == "unignore":
            await self.unignore_user(ctx, *args)
        elif action == "ignore_list":
            await self.list_ignored(ctx)
        elif action == "disable":
            await self.disable_bot(ctx, *args)
        elif action == "enable":
            await self.enable_bot(ctx, *args)
        else:
            await ctx.send(get_mention(ctx) + "Неизвестная команда.")

    async def disable_bot(self, ctx, *args):
        channel = args[0].lower() if args else ctx.channel.name.lower()

        if channel not in CHANNELS:
            await ctx.send(get_mention(ctx) + f"Канал {channel} не подключён к боту.")
            return

        self.cursor.execute("INSERT OR IGNORE INTO disabled_channels (channel_name) VALUES (?)", (channel,))
        self.conn.commit()
        await ctx.send(get_mention(ctx) + f"Бот отключён на канале {channel}.")


    async def enable_bot(self, ctx, *args):
        channel = args[0].lower() if args else ctx.channel.name.lower()

        if channel not in CHANNELS:
            await ctx.send(get_mention(ctx) + f"Канал {channel} не подключён к боту.")
            return

        self.cursor.execute("DELETE FROM disabled_channels WHERE channel_name = ?", (channel,))
        self.conn.commit()
        await ctx.send(get_mention(ctx) + f"Бот снова включён на канале {channel}.")


    async def set_echo_user(self, ctx: commands.Context, *args):
        global echo_user
        if len(args) > 0:
            echo_user = args[0].lower()
            await ctx.send(get_mention(ctx) + f"Теперь повторяю сообщения от @{echo_user}")
        else:
            await ctx.send(get_mention(ctx) + "Используй: !a echo <username>")

    async def stop_echo(self, ctx: commands.Context):
        global echo_user
        if ctx.author.name.lower() == echo_user or ctx.author.name.lower() in OWNERS:
            echo_user = None
            await ctx.send(get_mention(ctx) + "Теперь не повторяю сообщения.")
        else:
            await ctx.send(get_mention(ctx) + "Вы не тот пользователь, чьи сообщения бот повторяет.")

    async def add_channel(self, ctx: commands.Context, channel_name: str):
        channels = config_loader.get_channels()
        if channel_name not in channels:
            channels.append(channel_name)
            config_loader.set_channels(channels)
            await self.bot.join_channels([channel_name])
            await ctx.send(get_mention(ctx) + f"Канал {channel_name} был добавлен.")
            await self.send_message_to_channel(get_mention(ctx) + " " + channel_name, "Канал был успешно добавлен!")
        else:
            await ctx.send(get_mention(ctx) + f"Канал {channel_name} уже в списке.")

    async def send_message_to_channel(self, channel_name, message):
        channel = self.get_channel(channel_name)
        if channel:
            await channel.send(message)

    async def reload_emotes(self, ctx: commands.Context):
        TOKEN = config_loader.get_token()
        CHANNELS = config_loader.get_channels()
        OWNER_CHANNEL = config_loader.get_owner_channel()
        EMOTE_SET_ID = config_loader.get_emote_set_id()
        OWNERS = config_loader.get_owners()

        for channel in self.bot.connected_channels:
            if channel.name not in CHANNELS:
                await self.bot.part_channels([channel.name])

        for channel in CHANNELS:
            if channel not in [c.name for c in self.bot.connected_channels]:
                await self.bot.join_channels([channel])

        await self.bot.fetch_emotes()
        await ctx.send(get_mention(ctx) + f"Конфигурация обновлена и бот переподключился к каналам.")

    def is_module_disabled(self, channel: str, module: str) -> bool:
        self.cursor.execute(
            "SELECT 1 FROM disabled_modules WHERE channel_name = ? AND module_name = ?",
            (channel.lower(), module.lower())
        )
        return self.cursor.fetchone() is not None


    async def load_module(self, ctx: commands.Context, *args):
        if len(args) < 1:
            await ctx.send(get_mention(ctx) + "Использование: !a load_module <module> или !a load_module <channel> <module>")
            return

        if len(args) == 1:
            # Глобальное включение модуля
            module_name = args[0].lower()
            channel_name = None
        else:
            channel_name = args[0].lower()
            module_name = args[1].lower()

        if module_name not in self.modules:
            await ctx.send(get_mention(ctx) + f"Модуль {module_name} не найден.")
            return

        module_path = self.modules[module_name]

        # Удаляем запись из disabled_modules
        if channel_name:
            self.cursor.execute("DELETE FROM disabled_modules WHERE channel_name = ? AND module_name = ?", (channel_name, module_name))
            self.conn.commit()
            await ctx.send(get_mention(ctx) + f"Модуль {module_name} включён на канале {channel_name}.")
            return

        else:
            self.cursor.execute("DELETE FROM disabled_modules WHERE module_name = ?", (module_name,))
            self.conn.commit()

            # Если модуль ещё не загружен — загружаем его
            if module_name not in self.bot.loaded_modules:
                try:
                    module = importlib.import_module(module_path)
                    cog_class = next((getattr(module, attr) for attr in dir(module) if isinstance(getattr(module, attr), type)), None)
                    self.bot.add_cog(cog_class(self.bot))
                    self.bot.loaded_modules.add(module_name)
                    await ctx.send(get_mention(ctx) + f"Модуль {module_name} загружен и включён глобально.")
                except Exception as e:
                    await ctx.send(get_mention(ctx) + f"Ошибка при загрузке модуля {module_name}: {e}")
            else:
                await ctx.send(get_mention(ctx) + f"Модуль {module_name} уже был загружен. Он теперь включён глобально.")


    async def unload_module(self, ctx: commands.Context, *args):
        if len(args) == 1:
            # Глобальное отключение
            module_name = args[0].lower()
            self.cursor.execute("DELETE FROM disabled_modules WHERE module_name = ?", (module_name,))
            self.conn.commit()
            # Выгрузи из бота
            if module_name in self.bot.loaded_modules:
                try:
                    self.bot.remove_cog(module_name.capitalize() + "Commands")
                    self.bot.loaded_modules.remove(module_name)
                except Exception as e:
                    await ctx.send(get_mention(ctx) + f"Ошибка выгрузки модуля: {e}")
            await ctx.send(get_mention(ctx) + f"Модуль {module_name} отключён глобально.")
            return

        elif len(args) == 2:
            # Отключение на конкретном канале
            channel_name = args[0].lower()
            module_name = args[1].lower()
            self.cursor.execute(
                "INSERT OR IGNORE INTO disabled_modules (channel_name, module_name) VALUES (?, ?)",
                (channel_name, module_name)
            )
            self.conn.commit()
            await ctx.send(get_mention(ctx) + f"Модуль {module_name} отключён на канале {channel_name}.")
            return


    async def reload_module(self, ctx: commands.Context, *args):
        if len(args) < 1:
            await ctx.send(get_mention(ctx) + "Использование: !a reload_module <module>")
            return
        module_name = args[0].lower()
        if module_name not in self.modules:
            await ctx.send(get_mention(ctx) + f"Модуль {module_name} не найден.")
            return
        await self.unload_module(ctx, *args)
        await self.load_module(ctx, *args)

    async def ignore_user(self, ctx: commands.Context, *args):
        if len(args) < 1:
            await ctx.send(get_mention(ctx) + "Использование: !a ignore <username>")
            return
        user = args[0].lower()
        self.add_ignored_user(user)
        await ctx.send(get_mention(ctx) + f"@{user} добавлен в игнор-лист.")

    async def unignore_user(self, ctx: commands.Context, *args):
        if len(args) < 1:
            await ctx.send(get_mention(ctx) + "Использование: !a unignore <username>")
            return
        user = args[0].lower()
        if self.is_ignored(user):
            self.remove_ignored_user(user)
            await ctx.send(get_mention(ctx) + f"@{user} удалён из игнор-листа.")
        else:
            await ctx.send(get_mention(ctx) + f"@{user} не в списке игнора.")

    async def list_ignored(self, ctx: commands.Context):
        users = self.get_all_ignored_users()
        if users:
            await ctx.send(get_mention(ctx) + "Игнор-лист: " + ", ".join(f"@{u}" for u in users))
        else:
            await ctx.send(get_mention(ctx) + "Игнор-лист пуст.")
