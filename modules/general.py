import datetime
import random
from twitchio.ext import commands
import openai

sleep_times = {}
afk_times = {}
import time
import aiohttp

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


    @commands.command(name="gn")
    async def good_night(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        username = ctx.author.name.lower()
        sleep_times[username] = datetime.datetime.now()
    
        message = ctx.message.content[len(ctx.prefix) + len(ctx.command.name) + 1:].strip()
    
        if message:
            await ctx.send(f"@{ctx.author.name} ушел спать: {message}")
        else:
            await ctx.send(f"@{ctx.author.name} ушел спать. Спокойной ночи!")

    @commands.command(name="afk")
    async def away_from_keyboard(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        username = ctx.author.name.lower()

        message = ctx.message.content[len(ctx.prefix) + len(ctx.command.name) + 1:].strip()

        afk_times[username] = datetime.datetime.now()
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

        message = ctx.message.content[len(ctx.prefix) + len(ctx.command.name) + 1:].strip()

        afk_times[username] = datetime.datetime.now()
        if message:
            await ctx.send(f"@{ctx.author.name} ушел на доставку: {message}")
        else:
            await ctx.send(f"@{ctx.author.name} ушел на доставку. Удачи!")

    @commands.command(name="work")
    async def work(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "general"):
            return
        username = ctx.author.name.lower()

        message = ctx.message.content[len(ctx.prefix) + len(ctx.command.name) + 1:].strip()

        afk_times[username] = datetime.datetime.now()
        if message:
            await ctx.send(f"@{ctx.author.name} ушел на работу: {message}")
        else:
            await ctx.send(f"@{ctx.author.name} ушел на работу. Удачи!")

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


