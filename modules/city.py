from twitchio.ext import commands
import random
import asyncio

class CityCommands(commands.Cog):  # ИСПРАВЛЕНО имя класса
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}  # {channel: {"players": [], "used_cities": [], "turn_index": 0}}
        self.cities = self.load_cities()
        self.banned_players = {}
        self.bot_owner = "testervt"

    def load_cities(self):
        try:
            with open("cities.txt", "r", encoding="utf-8") as file:
                return {city.strip().lower() for city in file.readlines()}
        except FileNotFoundError:
            return set()

    @commands.command(name="city")
    async def city(self, ctx: commands.Context, subcommand: str = None, *args):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "city"):
            await ctx.send("❌ Использование: !city запрещенно на данном канале.")
            return
        if not subcommand:
            await ctx.send("Доступные команды: !city create, join, play <город>, leave, end, info")
            return

        subcommand = subcommand.lower()
        if subcommand == "create":
            await self.create(ctx)
        elif subcommand == "join":
            await self.join(ctx)
        elif subcommand == "ban":
            await self.ban(ctx, args)
        elif subcommand == "kick":
            if args:
                await self.kick(ctx, args[0])
            else:
                await ctx.send("Использование: !city kick <ник>")
        elif subcommand == "play":
            await self.play(ctx, " ".join(args) if args else "")
        elif subcommand == "leave":
            await self.leave(ctx)
        elif subcommand == "end":
            await self.end(ctx)
        elif subcommand == "info":
            await self.info(ctx)
        else:
            await ctx.send("Неизвестная команда. Используйте !city для справки.")

    async def ban(self, ctx, args):
        author = ctx.author.name.lower()
        if author != self.bot_owner:
            await ctx.send("Только владелец бота может банить игроков.")
            return
        if not args:
            await ctx.send("Укажите ник: !city ban <ник>")
            return
        banned_user = args[0].lower()
        self.banned_players.setdefault(ctx.channel.name, []).append(banned_user)
        await ctx.send(f"{banned_user} забанен и не сможет участвовать.")

    async def start_turn_timer(self, channel_name, player_name, timeout=180):
        game = self.active_games.get(channel_name)
        if not game:
            return
        previous_task = game.get("current_timer_task")
        if previous_task and not previous_task.done():
            previous_task.cancel()
        task = asyncio.create_task(self.wait_for_turn(channel_name, player_name, timeout))
        game["current_timer_task"] = task

    async def wait_for_turn(self, channel_name, player_name, timeout):
        await asyncio.sleep(timeout)

        game = self.active_games.get(channel_name)
        if not game or player_name not in game["players"]:
            return

        turn_index = game["turn_index"]
        if game["players"][turn_index] != player_name:
            return

        # Исключение игрока за пропуск
        game["players"].remove(player_name)
        await self.bot.get_channel(channel_name).send(
            f"{player_name} не сделал ход вовремя и был исключён из игры.")

        if not game["players"]:
            del self.active_games[channel_name]
            await self.bot.get_channel(channel_name).send("Игра завершена, все игроки исключены.")
            return

        if turn_index >= len(game["players"]):
            game["turn_index"] = 0

        next_player = game["players"][game["turn_index"]]
        await self.bot.get_channel(channel_name).send(f"Следующий ход за {next_player}.")
        await self.start_turn_timer(channel_name, next_player)

    async def create(self, ctx):
        if ctx.channel.name in self.active_games:
            await ctx.send("Игра уже идёт.")
            return
        self.active_games[ctx.channel.name] = {"players": [], "used_cities": [], "turn_index": 0}
        await ctx.send("Игра создана! Присоединяйтесь с !city join")

    async def join(self, ctx):
        game = self.active_games.get(ctx.channel.name)
        if not game:
            await ctx.send("Сначала создайте игру с !city create")
            return
        if ctx.author.name.lower() in self.banned_players.get(ctx.channel.name, []):
            await ctx.send("Вы забанены и не можете участвовать.")
            return
        if ctx.author.name in game["players"]:
            await ctx.send("Вы уже в игре.")
            return
        game["players"].append(ctx.author.name)
        await ctx.send(f"{ctx.author.name} присоединился к игре!")

    async def kick(self, ctx, username):
        game = self.active_games.get(ctx.channel.name)
        if not game:
            await ctx.send("Игра не запущена.")
            return
        if ctx.author.name != game["players"][0]:
            await ctx.send("Только создатель игры может кикать.")
            return
        username = username.lower()
        for player in game["players"]:
            if player.lower() == username:
                game["players"].remove(player)
                await ctx.send(f"{player} был удалён.")
                if game["turn_index"] >= len(game["players"]):
                    game["turn_index"] = 0
                return
        await ctx.send("Игрок не найден.")

    async def play(self, ctx, city):
        game = self.active_games.get(ctx.channel.name)
        if not game:
            await ctx.send("Игра не запущена.")
            return
        if ctx.author.name not in game["players"]:
            await ctx.send("Вы не в игре. Присоединяйтесь с !city join")
            return

        current_player = game["players"][game["turn_index"]]
        if ctx.author.name != current_player:
            await ctx.send(f"Сейчас ход {current_player}. Подождите своей очереди!")
            return

        city = city.strip().lower()
        if not city:
            await ctx.send("Вы не указали город.")
            return
        if city in game["used_cities"]:
            await ctx.send("Этот город уже был назван!")
            return
        if city not in self.cities:
            await ctx.send("Такого города нет в базе.")
            return

        if game["used_cities"]:
            last = game["used_cities"][-1]
            last_letter = last[-1]
            if last_letter in "ьъы":
                last_letter = last[-2]
            if city[0] != last_letter:
                await ctx.send(f"Город должен начинаться на букву '{last_letter.upper()}'!")
                return

        game["used_cities"].append(city)
        game["turn_index"] = (game["turn_index"] + 1) % len(game["players"])
        next_player = game["players"][game["turn_index"]]
        await ctx.send(f"{ctx.author.name} назвал город {city.capitalize()}! Следующий ход: {next_player}.")
        await self.start_turn_timer(ctx.channel.name, next_player)

    async def leave(self, ctx):
        game = self.active_games.get(ctx.channel.name)
        if not game:
            await ctx.send("Нет активной игры.")
            return
        if ctx.author.name not in game["players"]:
            await ctx.send("Вы не в игре.")
            return

        was_current = game["players"][game["turn_index"]] == ctx.author.name
        index_before = game["players"].index(ctx.author.name)
        game["players"].remove(ctx.author.name)

        if was_current:
            timer_task = game.get("current_timer_task")
            if timer_task and not timer_task.done():
                timer_task.cancel()
            if game["turn_index"] >= len(game["players"]):
                game["turn_index"] = 0
            if game["players"]:
                next = game["players"][game["turn_index"]]
                await ctx.send(f"{ctx.author.name} вышел. Ход передан {next}.")
                await self.start_turn_timer(ctx.channel.name, next)
            else:
                del self.active_games[ctx.channel.name]
                await ctx.send("Игра завершена: игроков не осталось.")
        else:
            if index_before < game["turn_index"]:
                game["turn_index"] -= 1
            await ctx.send(f"{ctx.author.name} покинул игру.")

    async def end(self, ctx):
        game = self.active_games.get(ctx.channel.name)
        if not game:
            await ctx.send("Нет активной игры.")
            return
        if ctx.author.name not in game["players"]:
            await ctx.send("Только участник игры может её завершить.")
            return
        timer_task = game.get("current_timer_task")
        if timer_task and not timer_task.done():
            timer_task.cancel()
        del self.active_games[ctx.channel.name]
        await ctx.send("Игра завершена!")

    async def info(self, ctx):
        game = self.active_games.get(ctx.channel.name)
        if not game:
            await ctx.send("Нет активной игры.")
            return
        if not game["players"]:
            await ctx.send("Нет игроков в игре.")
            return
        current = game["players"][game["turn_index"]]
        if game["used_cities"]:
            last = game["used_cities"][-1]
            letter = last[-1]
            if letter in "ьъы":
                letter = last[-2]
            letter = letter.upper()
        else:
            letter = "любая (первый ход)"
        order = " → ".join(game["players"])
        await ctx.send(f"Очередь: {order} | Сейчас ходит: {current} | Буква: {letter}")

def setup(bot):
    bot.add_cog(CityCommands(bot))
