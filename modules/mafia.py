import asyncio
import random
from twitchio.ext import commands

class MafiaCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}  # {"channel": {...}}

    @commands.command(name="mafia")
    async def mafia(self, ctx, action: str = None):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "mafia"):
            await ctx.send("❌ Использование: !mafia запрещенно на данном канале.")
            return
        if action == "join":
            await self.join(ctx)
        elif action == "leave":
            await self.leave(ctx)
        elif action == "start":
            await self.start(ctx)
        elif action == "end":
            await self.end(ctx)
        else:
            await ctx.send("📜 Используйте: !mafia join | leave | start | end")

    async def join(self, ctx):
        channel = ctx.channel.name
        if channel not in self.games:
            self.games[channel] = {"players": {}, "mafia": [], "detective": "", "doctor": "", "votes": {}, "started": False}

        if ctx.author.name in self.games[channel]["players"]:
            await ctx.send("⚠️ Вы уже в игре!")
            return

        self.games[channel]["players"][ctx.author.name] = "civilian"
        await ctx.send(f"✅ {ctx.author.name} присоединился к игре!")

    async def leave(self, ctx):
        channel = ctx.channel.name
        if channel in self.games and ctx.author.name in self.games[channel]["players"]:
            del self.games[channel]["players"][ctx.author.name]
            await ctx.send(f"🚪 {ctx.author.name} вышел из игры.")
        else:
            await ctx.send("⚠️ Вы не в игре.")

    async def start(self, ctx):
        channel = ctx.channel.name
        if channel not in self.games or self.games[channel]["started"]:
            await ctx.send("⚠️ Игра уже идёт или не создана.")
            return

        game = self.games[channel]
        players = list(game["players"].keys())

        if len(players) < 6:
            await ctx.send("🚫 Нужно минимум 6 игроков.")
            return

        await ctx.send("🎮 Игра начинается через 10 секунд!")
        await asyncio.sleep(10)

        random.shuffle(players)
        mafia_count = max(1, len(players) // 4)

        game["mafia"] = players[:mafia_count]
        game["detective"] = players[mafia_count] if mafia_count + 1 < len(players) else None
        game["doctor"] = players[mafia_count + 1] if mafia_count + 2 < len(players) else None
        civilians = players[mafia_count + 2:]

        for mafia in game["mafia"]:
            user = await self.fetch_user(mafia)
            if user:
                await user.send("🤵 Вы - мафия! Уничтожьте всех мирных!")

        if game["detective"]:
            user = await self.fetch_user(game["detective"])
            if user:
                await user.send("🕵️ Вы - детектив! Проверяйте людей каждую ночь.")

        if game["doctor"]:
            user = await self.fetch_user(game["doctor"])
            if user:
                await user.send("🧑‍⚕️ Вы - доктор! Лечите одного игрока каждую ночь.")

        for civilian in civilians:
            user = await self.fetch_user(civilian)
            if user:
                await user.send("😇 Вы - мирный житель. Вычислите мафию и выживите.")

        game["started"] = True
        await self.night_phase(ctx)

    async def night_phase(self, ctx):
        channel = ctx.channel.name
        game = self.games[channel]

        game["night_actions"] = {"kill": None, "heal": None, "check": None}
        await ctx.send("🌙 Наступает ночь. Все засыпают... (30 сек.)")

        await asyncio.sleep(30)

        kill = game["night_actions"]["kill"]
        heal = game["night_actions"]["heal"]
        check = game["night_actions"]["check"]

        if kill and kill != heal and kill in game["players"]:
            await ctx.send(f"☠️ {kill} был убит ночью!")
            del game["players"][kill]
            if kill in game["mafia"]:
                game["mafia"].remove(kill)
            if kill == game["doctor"]:
                game["doctor"] = None
            if kill == game["detective"]:
                game["detective"] = None

        if check and game["detective"]:
            result = "мафия" if check in game["mafia"] else "мирный"
            user = await self.fetch_user(game["detective"])
            if user:
                await user.send(f"🕵️ Проверка: {check} — {result}.")

        await self.check_win(ctx)

    async def day_phase(self, ctx):
        channel = ctx.channel.name
        game = self.games[channel]
        await ctx.send("🌞 Наступил день. Обсуждение — 1 минута.")
        await asyncio.sleep(60)

        game["votes"] = {}
        await ctx.send("🗳️ Время голосования! Используйте !vote <имя>")

        await asyncio.sleep(60)

        if not game["votes"]:
            await ctx.send("😶 Никто не был изгнан.")
        else:
            voted_out = max(game["votes"], key=game["votes"].get)
            await ctx.send(f"🚫 {voted_out} был изгнан из деревни.")
            if voted_out in game["players"]:
                del game["players"][voted_out]
            if voted_out in game["mafia"]:
                game["mafia"].remove(voted_out)
            if voted_out == game["detective"]:
                game["detective"] = None
            if voted_out == game["doctor"]:
                game["doctor"] = None

        await self.check_win(ctx)

    async def check_win(self, ctx):
        channel = ctx.channel.name
        game = self.games[channel]

        mafia_alive = len(game["mafia"])
        civilians_alive = len(game["players"]) - mafia_alive

        if mafia_alive == 0:
            await ctx.send("🎉 Мирные победили! Игра окончена.")
            self.games.pop(channel)
            return
        if mafia_alive >= civilians_alive:
            await ctx.send("💀 Мафия захватила деревню! Победа мафии.")
            self.games.pop(channel)
            return

        await self.day_phase(ctx)

    async def fetch_user(self, name):
        try:
            users = await self.bot.fetch_users(names=[name])
            return users[0] if users else None
        except Exception as e:
            print(f"❌ Ошибка отправки ЛС: {e}")
            return None

    @commands.command(name="kill")
    async def kill(self, ctx, target: str):
        channel = ctx.channel.name
        game = self.games.get(channel)
        if game and ctx.author.name in game["mafia"] and target in game["players"]:
            game["night_actions"]["kill"] = target

    @commands.command(name="check")
    async def check(self, ctx, target: str):
        channel = ctx.channel.name
        game = self.games.get(channel)
        if game and ctx.author.name == game["detective"] and target in game["players"]:
            game["night_actions"]["check"] = target

    @commands.command(name="heal")
    async def heal(self, ctx, target: str):
        channel = ctx.channel.name
        game = self.games.get(channel)
        if game and ctx.author.name == game["doctor"] and target in game["players"]:
            game["night_actions"]["heal"] = target

    @commands.command(name="vote")
    async def vote(self, ctx, target: str):
        channel = ctx.channel.name
        game = self.games.get(channel)
        if game and ctx.author.name in game["players"] and target in game["players"]:
            game["votes"][target] = game["votes"].get(target, 0) + 1

    async def end(self, ctx):
        channel = ctx.channel.name
        if channel in self.games:
            del self.games[channel]
            await ctx.send("🛑 Игра завершена.")

def setup(bot):
    bot.add_cog(MafiaCommands(bot))
