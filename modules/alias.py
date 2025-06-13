import sqlite3
import random
import logging
import time
import re
import aiohttp
from twitchio.ext import commands
from py_mini_racer import py_mini_racer

user_say_cooldowns = {}  # username: last_used_time
COOLDOWN_SECONDS = 5

logger = logging.getLogger(__name__)

ALLOWED_SUBCOMMANDS = [
    "say {0}", "echo {0}", "ping", "pong", "meow",
    "!cat feed", "!cat soup", "!cat buy food", "!cat pet",
    "!cat info", "!weather {0}", "!afk", "!back", "!city play {0}", "!ai {0}"
]

class AliasCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = sqlite3.connect("aliases.db")
        self.db.execute('''CREATE TABLE IF NOT EXISTS aliases (
            name TEXT,
            owner TEXT,
            command TEXT
        )''')
        self.db.commit()


    @staticmethod
    async def fetch_js_from_gist(gist_url, func, args_list, message):
        """
        Загружает JS-код из GitHub Gist и выполняет указанную функцию с аргументами.
        Возвращает результат выполнения в виде строки.
        """
        try:
            # Извлечение ID gist-а
            match = re.search(r"gist\.github\.com/(?:[^/]+/)?([a-f0-9]+)", gist_url)
            if not match:
                return "❌ Неверная ссылка на Gist."
            gist_id = match.group(1)

            # Получение содержимого Gist
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.github.com/gists/{gist_id}") as resp:
                    if resp.status != 200:
                        return f"❌ Не удалось загрузить Gist (HTTP {resp.status})"
                    data = await resp.json()

            # Используем первый найденный .js файл
            js_file = next((file["content"] for file in data["files"].values() if file["filename"].endswith(".js")), None)
            if js_file is None:
                return "❌ В Gist нет JS-файла."

            # Подготовка аргументов для JS — сериализация в JSON
            import json
            # Сериализуем список аргументов
            args_json = json.dumps(args_list)  # Превратит ['яблоко', 'банан'] в '["яблоко","банан"]'
            # Имя пользователя из сообщения (автора)
            username_json = json.dumps(message.author.name)  # в кавычках и экранировано

            # Формируем JS-код с вызовом функции func(args_list, username)
            # например: main_result = main(["яблоко","банан"], "TesterVT");
            function_call = f"main_result = {func}({args_json}, {username_json});"

            # Собираем полный код для выполнения
            full_code = f"{js_file}\n{function_call}\n"

            # Создаём контекст PyMiniRacer
            ctx = py_mini_racer.MiniRacer()

            # Выполняем весь JS-код
            ctx.eval(full_code)

            # Получаем результат
            result = ctx.eval("main_result")

            # Если результат — Promise, PyMiniRacer не сможет его обработать, 
            # поэтому нужно, чтобы JS-функция была синхронной (см. пояснения ниже)

            return str(result)

        except Exception as e:
            return f"❌ Ошибка при выполнении JS: {e}"

    @staticmethod
    async def handle_custom_alias(bot, message):
        db = sqlite3.connect("aliases.db")
        alias_name = message.content[2:].split(" ", 1)[0].lower()
        args = message.content[2 + len(alias_name):].strip()
        username = message.author.name.lower()

        cursor = db.execute("SELECT command FROM aliases WHERE name=? AND owner=?", (alias_name, username))
        rows = cursor.fetchall()
        if not rows:
            return False

        try:
            chatters = list(message.channel.chatters)
            chatter_names = [chatter.name for chatter in chatters]
            random_chatter = random.choice(chatter_names) if chatter_names else "someone"
        except Exception as e:
            logger.warning(f"❌ Ошибка получения чаттеров: {e}")
            random_chatter = "someone"

        args_list = args.split()

        commands_and_filters = [row[0] for row in rows]
        commands = []
        replacements = []

        for command in commands_and_filters:
            if command.startswith("replace "):
                match = re.search(r'regex:"(.+?)"\s+replacement:"(.+?)"', command)
                if match:
                    pattern, repl = match.groups()
                    replacements.append((pattern, repl))
            else:
                commands.append(command)

        for command in commands:
            if command.startswith("js importGist:"):
                match = re.match(r'js importGist:(\w+)\s+function:"(.+?)"', command)
                if match:
                    gist_id, func = match.groups()
                    gist_url = f"https://gist.github.com/{gist_id}"

                    js_result = await AliasCommands.fetch_js_from_gist(gist_url, func, args_list, message)
                    formatted = f"say {js_result.strip()}"
                else:
                    formatted = "say ⚠️ Неверный формат команды js importGist"
            else:
                try:
                    formatted = command.format(
                        *args_list,
                        user=message.author.name,
                        channel=message.channel.name,
                        rc=random_chatter
                    )
                except Exception as e:
                    await message.channel.send(f"⚠️ Ошибка: {e}")
                    return True

            for pattern, repl in replacements:
                formatted = re.sub(pattern, repl, formatted)

            if formatted.lower().startswith("say "):
                now = time.time()
                last_used = user_say_cooldowns.get(username, 0)
                if now - last_used < COOLDOWN_SECONDS:
                    return True
                user_say_cooldowns[username] = now
                await message.channel.send(formatted[4:].strip())
            else:
                message.content = formatted
                await bot.handle_commands(message)

        return True



    @commands.command(name="alias")
    async def alias_cmd(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "alias"):
            await ctx.send("❌ Использование: !alias запрещенно на данном канале.")
            return
        parts = ctx.message.content.split(" ", 3)
        if len(parts) < 2:
            await ctx.send("Использование: !alias [add|remove|list|link|reload] ...")
            return

        subcommand = parts[1].lower()
        cursor = self.db.cursor()

        if subcommand == "add":
            content = ctx.message.content[len("!alias add "):]
            if "=" not in content:
                await ctx.send("❌ Использование: !alias add имя = команды")
                return

            name, commands_str = content.split("=", 1)
            name = name.strip().lower()
            command_list = [c.strip() for c in commands_str.split(";") if c.strip()]

            for command in command_list:
                if command.startswith("replace "):
                    continue  # Пропускаем проверку фильтров
                if command.startswith("js importGist:"):
                    match = re.match(r'js importGist:\w+\s+function:"(.+?)"', command)
                    if not match:
                        await ctx.send(f"⚠️ Неверный формат JS-команды.")
                        return
                elif not any(command.startswith(a.split(" ")[0]) for a in ALLOWED_SUBCOMMANDS):
                    await ctx.send(f"⚠️ Команда `{command}` не разрешена.")
                    return

            cursor.execute("DELETE FROM aliases WHERE name=? AND owner=?", (name, ctx.author.name))
            for cmd in command_list:
                cursor.execute("INSERT INTO aliases (name, owner, command) VALUES (?, ?, ?)",
                               (name, ctx.author.name, cmd))
            self.db.commit()
            await ctx.send(f"✅ Алиас `{name}` создан. Вызывайте как `!!{name}`")

        elif subcommand == "remove":
            if len(parts) < 3:
                await ctx.send("❌ Использование: !alias remove [название]")
                return
            name = parts[2].strip().lower()
            cursor.execute("DELETE FROM aliases WHERE name=? AND owner=?", (name, ctx.author.name))
            self.db.commit()
            await ctx.send(f"🗑️ Алиас `{name}` удалён.")

        elif subcommand == "list":
            cursor.execute("SELECT name FROM aliases WHERE owner=?", (ctx.author.name,))
            names = sorted(set(row[0] for row in cursor.fetchall()))
            if names:
                await ctx.send(f"📜 Ваши алиасы: {', '.join(['!!' + n for n in names])}")
            else:
                await ctx.send("🔍 У вас нет алиасов.")

        elif subcommand == "link":
            if len(parts) < 4:
                await ctx.send("Использование: !alias link [ник] [название]")
                return
            target_user, alias_name = parts[2], parts[3].lower()
            cursor.execute("SELECT command FROM aliases WHERE name=? AND owner=?", (alias_name, target_user))
            commands_to_copy = cursor.fetchall()
            if not commands_to_copy:
                await ctx.send("❌ Алиас не найден у указанного пользователя.")
                return
            new_name = f"{alias_name}"
            cursor.execute("DELETE FROM aliases WHERE name=? AND owner=?", (new_name, ctx.author.name))
            for (cmd,) in commands_to_copy:
                cursor.execute("INSERT INTO aliases (name, owner, command) VALUES (?, ?, ?)",
                               (new_name, ctx.author.name, cmd))
            self.db.commit()
            await ctx.send(f"🔗 Алиас `{alias_name}` скопирован как `!!{new_name}`")

        elif subcommand == "reload":
            await ctx.send("🔄 Алиасы перезагружены.")
