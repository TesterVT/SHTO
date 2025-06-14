import asyncio
import datetime
import random
from twitchio.ext import commands
import openai

sleep_times = {}
afk_times = {}
import time
import aiohttp
import sqlite3
AFK_DB = "afk_storage.db"


BOT_START_TIME = time.time()
command_usage_count = 0


class GeneralCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.version = "1.2"
        self.creator = "TesterVT"
        @bot.event()
        async def event_command(ctx):
            global command_usage_count
            command_usage_count += 1
        self._init_afk_db()
        self.bot.loop.create_task(self.restore_afk_data())

    def _init_afk_db(self):
        with sqlite3.connect(AFK_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS afk_users (
                    username TEXT PRIMARY KEY,
                    type TEXT,
                    message TEXT,
                    since TEXT
                )
            """)
            conn.commit()

    async def restore_afk_data(self):
        await asyncio.sleep(3)  # Даём боту немного времени на запуск

        with sqlite3.connect(AFK_DB) as conn:
            cursor = conn.execute("SELECT username, type, since FROM afk_users")
            for username, afk_type, since in cursor.fetchall():
                dt = datetime.datetime.fromisoformat(since)
                if afk_type == "sleep":
                    sleep_times[username] = dt
                else:
                    afk_times[username] = dt




    @commands.command(name="gn")
    async def good_night(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        username = ctx.author.name.lower()
        now = datetime.datetime.now()

        message = ctx.message.content[len(ctx.prefix) + len(ctx.command.name) + 1:].strip()

        afk_times[username] = now
        with sqlite3.connect(AFK_DB) as conn:
            conn.execute("REPLACE INTO afk_users (username, type, message, since) VALUES (?, ?, ?, ?)",
                        (username, "sleep", message, now.isoformat()))
            conn.commit()

        if message:
            await ctx.send(f"@{ctx.author.name} ушел спать: {message}")
        else:
            await ctx.send(f"@{ctx.author.name} ушел спать. Спокойной ночи!")

    @commands.command(name="afk")
    async def away_from_keyboard(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        username = ctx.author.name.lower()
        now = datetime.datetime.now()

        message = ctx.message.content[len(ctx.prefix) + len(ctx.command.name) + 1:].strip()

        afk_times[username] = now
        with sqlite3.connect(AFK_DB) as conn:
            conn.execute("REPLACE INTO afk_users (username, type, message, since) VALUES (?, ?, ?, ?)",
                        (username, "afk", message, now.isoformat()))
            conn.commit()

        if message:
            await ctx.send(f"@{ctx.author.name} ушел AFK: {message}")
        else:
            await ctx.send(f"@{ctx.author.name} ушел AFK. Вернется позже!")

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        message = ctx.message.content[len(ctx.prefix) + len(ctx.command.name) + 1:].strip()
        shuffled = ''.join(random.sample(message, len(message)))
        await ctx.send(f"@{ctx.author.name}, {shuffled}")

    @commands.command(name="delivery")
    async def delivery(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        username = ctx.author.name.lower()
        now = datetime.datetime.now()

        message = ctx.message.content[len(ctx.prefix) + len(ctx.command.name) + 1:].strip()

        afk_times[username] = now
        with sqlite3.connect(AFK_DB) as conn:
            conn.execute("REPLACE INTO afk_users (username, type, message, since) VALUES (?, ?, ?, ?)",
                        (username, "afk", message, now.isoformat()))
            conn.commit()

        if message:
            await ctx.send(f"@{ctx.author.name} ушел на доставку: {message}")
        else:
            await ctx.send(f"@{ctx.author.name} ушел доставку. Вернется позже!")

    @commands.command(name="work")
    async def work(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        username = ctx.author.name.lower()
        now = datetime.datetime.now()

        message = ctx.message.content[len(ctx.prefix) + len(ctx.command.name) + 1:].strip()

        afk_times[username] = now
        with sqlite3.connect(AFK_DB) as conn:
            conn.execute("REPLACE INTO afk_users (username, type, message, since) VALUES (?, ?, ?, ?)",
                        (username, "afk", message, now.isoformat()))
            conn.commit()

        if message:
            await ctx.send(f"@{ctx.author.name} ушел на работу: {message}")
        else:
            await ctx.send(f"@{ctx.author.name} ушел на работу. Вернется позже!")

    @commands.command(name="tuck")
    async def tuck_someone(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        args = ctx.message.content.split()
        if len(args) > 1:
            target_user = args[1].lower()
            sleep_times[target_user] = datetime.datetime.now()
            await ctx.send(f"@{target_user}, тебя уложили спать! Спокойной ночи!")
        else:
            await ctx.send("Используй: !tuck <username>")

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        global command_usage_count

        # Время аптайма
        uptime_seconds = time.time() - BOT_START_TIME
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        uptime_str = f"{hours} ч. {minutes} м."

        # Пинг до Twitch API
        start = time.perf_counter()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.twitch.tv") as response:
                await response.text()
        end = time.perf_counter()
        latency = int((end - start) * 1000)  # в миллисекундах

        # Кол-во каналов и команд
        channels_count = len(self.bot.connected_channels)
        commands_count = len(self.bot.commands)

        await ctx.send(
            f"🏓 Понг! | 🦊 v. {self.version} - by {self.creator} | 🕐 {uptime_str} | "
            f"👀 {channels_count} таб(ов) | 📜 Загружено {commands_count} комманд, выполнено {command_usage_count} | {latency} мс"
        )

    @commands.command(name="help")
    async def help(self, ctx: commands.Context):

        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        await ctx.send(f"Весь список комманд доступен тут: https://testervt.github.io/ ")


