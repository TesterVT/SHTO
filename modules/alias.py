import sqlite3
import random
import logging
import time
import re
import aiohttp
from twitchio.ext import commands

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
    async def fetch_js_from_gist(gist_id, function_call):
        """Загружает JS-код из Gist и выполняет его через Deno."""
        gist_url = f"https://gist.githubusercontent.com/raw/{gist_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(gist_url) as response:
                    if response.status != 200:
                        return f"⚠️ Gist не найден: {gist_id}"
                    js_code = await response.text()

            deno_payload = {
                "files": {"main.js": js_code},
                "stdin": "",
                "language": "javascript",
                "args": [],
                "run_timeout": 3000,
                "compile_timeout": 3000,
                "compile_memory_limit": -1,
                "run_memory_limit": -1,
            }

            # Используем JDoodle или REPL.it API, либо свой сервер с Deno (здесь псевдозапрос)
            # Замените URL на настоящий если у вас есть сервер для запуска JS
            async with aiohttp.ClientSession() as session:
                async with session.post("https://emulated-deno-server/execute", json=deno_payload) as resp:
                    result = await resp.json()
                    return result.get("stdout", "⚠️ Ошибка выполнения JS")
        except Exception as e:
            return f"⚠️ Ошибка JS: {e}"

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
            # Обработка вызова JS через gist
            if command.startswith("js importGist:"):
                match = re.match(r'js importGist:(\w+)\s+function:"(.+?)"', command)
                if match:
                    gist_id, func = match.groups()
                    js_result = await AliasCommands.fetch_js_from_gist(gist_id, func)
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
                if not any(command.startswith(a.split(" ")[0]) for a in ALLOWED_SUBCOMMANDS):
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
