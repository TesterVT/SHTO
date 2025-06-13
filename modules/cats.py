import json
import os
import random
import asyncio
import time
from twitchio.ext import commands
import logging
import aiofiles
from modules.profiles import get_mention, get_country

BANK_DATA_PATH = "data/cat_bank.json"

logger = logging.getLogger(__name__)


def calculate_currency_rate(total_invested):
    base_rate = 1.0
    return round(base_rate + (total_invested / 10000), 2)

def calculate_price(base_price, currency_rate):
    return int(base_price * currency_rate)

async def async_load_bank_data():
    if not os.path.exists(BANK_DATA_PATH):
        return {"total_invested": 0, "currency_rate": 1.0}
    async with aiofiles.open(BANK_DATA_PATH, "r", encoding="utf-8") as f:
        contents = await f.read()
        return json.loads(contents)

async def async_save_bank_data(data):
    async with aiofiles.open(BANK_DATA_PATH, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))

TIMER_FILE = "cat_timers.json"

def load_timers():
    try:
        with open(TIMER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_timers(data):
    with open(TIMER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

active_timers = load_timers()


# Загрузка конфигурации и списка котов
def load_cats():
    try:
        with open("cats.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
def load_data(filename, default=None):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}


def save_cats(data):
    with open("cats.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

cats = load_cats()
items = load_data("items.json", ["Игрушка", "Рыба", "Редкий камень", "Перышко"])

SOUPS = {
    "Суп 🍲": (10, 50),
    "Суп из рыбы 🐟": (10, 60),
    "Мясной суп 🍖": (15, 75),
    "Овощной суп 🥕": (12, 55),
    "Суп-сюрприз 🎁": (18, 90)
}


def level_up(cat):
    leveled_up = False
    while cat['experience'] >= (100 * cat['level'] + (cat['level'] * 50)):  # Увеличение опыта для каждого уровня
        experience_to_next_level = 100 * cat['level'] + (cat['level'] * 50)
        cat['experience'] -= experience_to_next_level
        cat['level'] += 1
        leveled_up = True
    return leveled_up

# Добавление статистики по поглаживанию
def add_petting_stat(cat):
    if 'pettings' not in cat:
        cat['pettings'] = 0
    cat['pettings'] += 1

class CatCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # При запуске бота сбрасываем "busy"
        for cat in cats.values():
            cat["busy"] = False
            if "channel" not in cat:
                cat["channel"] = "global"
        save_cats(cats)
        load_timers()
        self.available_actions = {
    "adopt", "feed", "pet", "info", "walk", "buy", "inv", "boost", "soup", "cancel",
    "bank", "top", "top_global", "friend",
    "meet", "help"
}



    async def ensure_bank_timer(self):
        logger.info("🚀 ensure_bank_timer запущен")
        username = "__bank__"
        duration = 300
        end_time = time.time() + duration
        active_timers[username] = {
            "type": "bank",
            "channel": "global",
            "end_time": end_time
        }
        save_timers(active_timers)
        logger.info(f"🕓 Таймер банка ПЕРЕзапущен, на {duration} сек.")
        asyncio.create_task(self.resume_timer(username, "bank", duration))




    async def load_timers(self):
        for username, data in list(active_timers.items()):
            try:
                remaining = data["end_time"] - time.time()
                if remaining > 0:
                    asyncio.create_task(self.resume_timer(username, data["type"], remaining))
                else:
                    asyncio.create_task(self.finish_timer(username, data["type"]))
            except Exception as e:
                logger.warning(f"🚫 Ошибка запуска таймера {username}: {e}")

    async def load_random_story(self, filename, cat_name, friend_name=None, item_name=None):
        path = f"data/post_walk_events/{filename}"
        try:
            with open(path, encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            if not lines:
                return ""
            text = random.choice(lines)
            text = text.replace("{cat}", cat_name)
            if friend_name:
                text = text.replace("{friend}", friend_name)
            if item_name:
                text = text.replace("{item}", item_name)
            return text
        except FileNotFoundError:
            return ""

    async def resume_timer(self, username, timer_type, duration=None):
        logger.info(f"[⏱️] Запущен таймер: {username} ({timer_type}), спим {duration} сек.")
        timer = active_timers.get(username)
        if not timer:
            return

        remaining = (timer["end_time"] - time.time()) if duration is None else duration
        if remaining > 0:
            await asyncio.sleep(remaining)

        await self.finish_timer(username, timer_type)

        # Удалить из таймеров, если не банкир
        if username in active_timers:
            del active_timers[username]
            save_timers(active_timers)


    async def finish_timer(self, username, timer_type):
        logger.info(f"[✅] Завершение таймера: {username} ({timer_type})")
        timer = active_timers.get(username)
        if not timer:
            return

        if timer_type in ["walk", "soup"]:
            cat = cats.get(username)
            if not cat:
                return
            cat["busy"] = False

        channel_name = timer["channel"]

        if timer_type == "walk":
            found_item = random.choice(items) if random.random() < 0.5 else None
            story_file = ""
            story_context = {}

            if found_item:
                cat["inventory"].append(found_item)
                cat["experience"] += 20
                story_file = "item_found.txt"
                story_context["item"] = found_item
            else:
                cat["experience"] += 10
                # Попытка встретить друга
                if cat.get("friends") and random.random() < 0.4:
                    friend = random.choice(cat["friends"])
                    story_file = "friend_meeting.txt"
                    story_context["friend"] = friend
                else:
                    story_file = "nothing_happened.txt"

            # Загрузка и отправка истории
            story = await self.load_random_story(story_file, cat["name"], story_context.get("friend"), story_context.get("item"))
            if story:
                await self.bot.get_channel(channel_name).send(f"🐈 | @{username}, {story}")

        elif timer_type == "soup":
            cat["hunger"] -= 10
            soup_name, (_, price) = random.choice(list(SOUPS.items()))
            cat["inventory"].append(soup_name)
            if cat.get("boost_until", 0) > time.time():
                cat["experience"] += int(10 * 1.5)
            else:
                cat["experience"] += 30
            level_up(cat)
            await self.bot.get_channel(channel_name).send(
                f"🐈🍽️ | @{username}, {cat['name']} сварил {soup_name}!"
            )

        elif timer_type == "bank":
            try:
                bank_data = await async_load_bank_data()
                logger.info(f"[🏦] Обработка банковского таймера, total_invested: {bank_data['total_invested']}")
                if bank_data["total_invested"] > 0:
                    expense = int(bank_data["total_invested"] * random.uniform(0.01, 0.05))
                    bank_data["total_invested"] = max(0, bank_data["total_invested"] - expense)
                    bank_data["currency_rate"] = calculate_currency_rate(bank_data["total_invested"])
                    await async_save_bank_data(bank_data)
                    logger.info(f"[💸] Авторасход: -{expense}, курс: x{bank_data['currency_rate']:.2f}")
            except Exception as e:
                logger.error(f"[❌] Ошибка при авторасходе банка: {e}")

            # Перезапускаем новый банк-таймер
            asyncio.create_task(self.ensure_bank_timer())


        save_cats(cats)
        active_timers.pop(username, None)
        save_timers(active_timers)


    @commands.command(name="cat", aliases=["cot", "koshka"])
    async def cat_command(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "cat"):
            await ctx.send("❌ Использование: !cat(!cat, !koshka) запрещенно на данном канале.")
            return
        args = ctx.message.content.split()
        username = ctx.author.name.lower()

        if len(args) < 2:
            await ctx.send(f"📋 | {get_mention(ctx)}, доступные команды: {', '.join(sorted(self.available_actions))}")
            return

        action = args[1].lower()
        
        if action == "adopt":
            if username in cats:
                await ctx.send(f"{get_mention(ctx)}, у тебя уже есть кот! 🐱")
                return
            name = args[2] if len(args) > 2 else random.choice(["Барсик", "Мурка", "Рыжик"])
            cats[username] = {"name": name, "hunger": 100, "level": 1, "busy": False, "experience": 0, "currency": 0, "food": 1, "inventory": [], "friends": [], "happiness": 100, "cleanliness": 100, "channel": ctx.channel.name.lower(), "boost_until": 0  }
            save_cats(cats)
            await ctx.send(f"{get_mention(ctx)} завёл кота {name}! 🐾")

        elif action == "help":
            await ctx.send(f"📋 | {get_mention(ctx)} доступные команды: {', '.join(sorted(self.available_actions))}")

            
        elif action == "bank":
            subcommand = args[2].lower() if len(args) > 2 else "info"

            bank_data = await async_load_bank_data()

            if subcommand == "info":
                await ctx.send(
                    f"🏦 Кошачий банк: вложено {bank_data['total_invested']} монет. Текущий курс: x{bank_data["currency_rate"]}"
                )

            elif subcommand == "deposit":
                if username not in cats:
                    await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота! 🐾")
                    return

                if len(args) < 4 or not args[3].isdigit():
                    await ctx.send(f"{get_mention(ctx)}, укажи сумму: !cat bank deposit <сумма>")
                    return

                amount = int(args[3])
                if amount <= 0:
                    await ctx.send(f"{get_mention(ctx)}, сумма должна быть больше нуля.")
                    return

                cat = cats[username]

                if cat["currency"] < amount:
                    await ctx.send(f"{get_mention(ctx)}, недостаточно монет.")
                    return

                cat["currency"] -= amount
                bank_data["total_invested"] += amount
                bank_data["currency_rate"] = calculate_currency_rate(bank_data["total_invested"])

                save_cats(cats)
                await async_save_bank_data(bank_data)

                await ctx.send(f"{get_mention(ctx)}, ты вложил {amount} монет в банк. Спасибо! 🏦")

        elif action == "rename":
            if username not in cats:
                await ctx.send(f"{get_mention(ctx)}, у тебя нет кота.")
                return
            new_name = args[2] if len(args) > 2 else "Безымянный"
            cats[username]["name"] = new_name
            save_cats(cats)
            await ctx.send(f"🐈 |  {get_mention(ctx)} переименовал кота в {new_name}!")

        elif action == "feed":
            if username not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота. Используй !cat adopt 🐾")
                return

            try:
                amount = int(args[2]) if len(args) >= 3 else 1
                if amount < 1 or amount > 10:
                    raise ValueError
            except ValueError:
                await ctx.send(f"❌ | {get_mention(ctx)}, укажи корректное количество (например, !cat feed 3)")
                return

            if cats[username]["food"] < amount:
                await ctx.send(f"❌ | {get_mention(ctx)}, у тебя недостаточно еды (есть только {cats[username]['food']})!")
                return

            cats[username]["food"] -= amount
            cats[username]["hunger"] = min(100, cats[username]["hunger"] + 30 * amount)
            save_cats(cats)
            await ctx.send(f"🍖 | {get_mention(ctx)} покормил кота {cats[username]['name']} {amount} раз(а)! Сытость: {cats[username]["hunger"]}%  😺")


        
        elif action == "walk":
            if username not in cats:
                await ctx.send(f"🐈 |  {get_mention(ctx)}, у тебя нет кота.")
                return
            cat = cats[username]
            if cat["busy"]:
                await ctx.send(f"🐈 | {ctx.author.name}, твой кот сейчас занят! 😺")
                return
            if cat["happiness"] < 5:
                await ctx.send(f"🐈 | {ctx.author.name}, у твоего кота слишком низкое счастье, чтобы идти гулять! 😺")
                return
            if cat["cleanliness"] < 10:
                await ctx.send(f"🐈 | {ctx.author.name}, твой кот слишком грязный для прогулки! 😺")
                return

            cat["busy"] = True
            cat["happiness"] -= 5
            cat["cleanliness"] = max(0, cat["cleanliness"] - 10)
            walk_time = 60 * 30
            end_time = time.time() + walk_time
            active_timers[username] = {"type": "walk", "end_time": end_time, "channel": ctx.channel.name.lower()}
            save_cats(cats)
            save_timers(active_timers)

            await ctx.send(f"🐈 | {ctx.author.name}, твой кот отправился на прогулку на 30 минут 🐾")
            asyncio.create_task(self.resume_timer(username, "walk", walk_time))


        elif action == "soup":
            if username not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота. 🐾")
                return
            cat = cats[username]
            if cat["hunger"] < 10:
                await ctx.send(f"🐈 | {get_mention(ctx)}, кот {cat['name']} слишком голоден, чтобы варить суп! 🍲")
                return
            if cat["busy"]:
                await ctx.send(f"🐈 | {get_mention(ctx)}, кот {cat['name']} уже чем-то занят! ⏳")
                return

            cat["busy"] = True
            soup_time = 45 * 60
            end_time = time.time() + soup_time
            active_timers[username] = {"type": "soup", "end_time": end_time, "channel": ctx.channel.name.lower()}
            save_cats(cats)
            save_timers(active_timers)

            await ctx.send(f"🐈 | {get_mention(ctx)}, кот {cat['name']} начал варить суп! 🍲 Это займет 45 минут.")
            asyncio.create_task(self.resume_timer(username, "soup", soup_time))

        elif action == "test":
            logger.info("🚀 ensure_bank_timer запущен")
            username = "__bank__"
            if username not in active_timers:
                duration = 300  # каждые 5 минут
                end_time = time.time() + duration
                active_timers[username] = {
                    "type": "bank",
                    "channel": "global", 
                    "end_time": end_time
                }
                save_timers(active_timers)
                asyncio.create_task(self.resume_timer(username, "bank", duration))
                save_timers(active_timers)

    
        elif action == "sell":
            if username not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота. 🐾")
                return
            for soup, (_, price) in SOUPS.items():
                if soup in cats[username]["inventory"]:
                    cats[username]["inventory"].remove(soup)
                    cats[username]["currency"] += price
                    save_cats(cats)
                    await ctx.send(f"🐈 | {get_mention(ctx)}, кот {cats[username]['name']} продал {soup} за {price} монет! 💰")
                    bank_data = await async_load_bank_data()
                    bank_data["total_invested"] += int(price * 0.1)
                    await async_save_bank_data(bank_data)
                    return
            await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет супа для продажи! 🍲")


        elif action == "sell_all":
            if username not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота. 🐾")
                return

            total_earnings = 0
            count = 0
            for soup, (_, price) in SOUPS.items():
                while soup in cats[username]["inventory"]:
                    cats[username]["inventory"].remove(soup)
                    cats[username]["currency"] += price
                    total_earnings += price
                    count += 1

            if count == 0:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет супа для продажи! 🍲")
            else:
                save_cats(cats)
                await ctx.send(f"🐈 | {get_mention(ctx)}, кот {cats[username]['name']} продал {count} супов за {total_earnings} монет! 💰")
                bank_data = await async_load_bank_data()
                bank_data["total_invested"] += int(total_earnings * 0.1)
                await async_save_bank_data(bank_data)

        elif action == "cancel":
            if username not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота.")
                return
            cat = cats[username]
            if not cat["busy"]:
                await ctx.send(f"🐈 | {get_mention(ctx)}, твой кот и так свободен.")
                return

            cat["busy"] = False
            if username in active_timers:
                del active_timers[username]
                save_timers(active_timers)
            save_cats(cats)
            await ctx.send(f"🐈 | {get_mention(ctx)}, действие кота {cat['name']} отменено. ❌")


        elif action == "shop":
            bank_data = await async_load_bank_data()
            await ctx.send(f"🛒🐈 |  В магазине есть: Корм {calculate_price(30, bank_data["currency_rate"])} | Буст {calculate_price(50, bank_data["currency_rate"])} - !cat buy (вещь)")
        
        elif action == "buy":
            bank_data = await async_load_bank_data()

            if len(args) < 3:
                await ctx.send("🐈 | Используй: !cat buy food/boost [кол-во]")
                return

            item = args[2].lower()
            try:
                quantity = int(args[3]) if len(args) >= 4 else 1
                if quantity < 1 or quantity > 100:
                    raise ValueError
            except ValueError:
                await ctx.send(f"❌ | {get_mention(ctx)}, укажи корректное количество (например: !cat buy food 5)")
                return

            if item == "food":
                total_cost = calculate_price(30, bank_data["currency_rate"]) * quantity
                if cats[username]["currency"] < total_cost:
                    await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя недостаточно монет! 💰 Нужно {total_cost}")
                    return
                cats[username]["currency"] -= total_cost
                cats[username]["food"] += quantity
                save_cats(cats)
                await ctx.send(f"🐈 | {get_mention(ctx)} купил {quantity} корм(а)! 🍖")

            elif item == "boost":
                total_cost = calculate_price(50, bank_data["currency_rate"]) * quantity
                if cats[username]["currency"] < total_cost:
                    await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя недостаточно монет! 💰 Нужно {total_cost}")
                    return
                cats[username]["currency"] -= total_cost
                cats[username]["boost_until"] = int(time.time()) + 3600 * quantity
                save_cats(cats)
                await ctx.send(f"🐈 | {get_mention(ctx)} купил буст на {quantity} час(а)! 🚀")

            else:
                await ctx.send("❌ | Указан неизвестный товар. Используй: food или boost.")



        elif action == "top":
            channel = ctx.channel.name.lower()
            top_cats = [
                (user, data)
                for user, data in cats.items()
                if data.get("channel") == channel
            ]
            top_cats.sort(key=lambda x: x[1].get("level", 0), reverse=True)
            top_cats = top_cats[:5]

            if not top_cats:
                await ctx.send("🐈 | На этом канале ещё нет котов для топа.")
                return

            msg = "🏆 Топ котов канала:\n"
            for i, (user, data) in enumerate(top_cats, 1):
                msg += f" {i}. {data['name']} — Уровень: {data['level'] } | \n"
            await ctx.send(msg)

        elif action == "top_global":
            top_cats = sorted(
                cats.items(), key=lambda x: x[1].get("level", 0), reverse=True
            )[:5]

            msg = "🌍 Глобальный топ котов:\n"
            for i, (user, data) in enumerate(top_cats, 1):
                msg += f" {i}. {data['name']} — Уровень: {data['level']} | \n"
            await ctx.send(msg)


        elif action == "pet":
            if username not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота. 🐾")
                return
            cat = cats[username]
            add_petting_stat(cat)
            save_cats(cats)
            await ctx.send(f"🐈 | {get_mention(ctx)} погладил кота {cat['name']} ! 😻")
        
        elif action == "meet":
            if len(args) < 3:
                await ctx.send("🐈 | Используй: !cat meet <username>")
                return
            friend = args[2].lower()
            if friend not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у {friend} нет кота. 🐾")
                return
            if friend in cats[username]["friends"]:
                await ctx.send(f"🐈 | {get_mention(ctx)}, ваши коты уже друзья! 🐱🐱")
                return
            cats[username]["friends"].append(friend)
            cats[friend]["friends"].append(username)
            save_cats(cats)
            await ctx.send(f"🐈 | {get_mention(ctx)} и {friend} теперь друзья! 🐱🐱")
        
        elif action.startswith("info"):
            parts = action.split(maxsplit=1)
            target_user = parts[1].lower() if len(parts) > 1 else username
            cat = cats[username]
            if target_user not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у пользователя {target_user} нет кота. 🐾")
                return

            experience_to_next_level = 100 * cat['level'] + (cat['level'] * 50)

            await ctx.send(
                f"{get_mention(ctx)}, {cat['name']} 🐱 | Уровень: {cat['level']} | Опыт: {cat['experience']}/{experience_to_next_level} | "
                f"Сытость: {cat['hunger']}% 🍖 | Чистота: {cat['cleanliness']}% 🛁 | Веселье: {cat['happiness']}% 🎾 | "
                f"Баланс: {cat['currency']} 💰"
            )

        elif action == "friends":
            parts = action.split(maxsplit=1)
            target_user = parts[1].lower() if len(parts) > 1 else username
            if username not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота. 🐾")
                return
            cat = cats[target_user]
            friends = [cats[friend]["name"] for friend in cat["friends"] if friend in cats]
            friends_list = ", ".join(friends) if friends else "Нет"
            await ctx.send(
                f"{get_mention(ctx)}, Друзья: {friends_list} 🐱"
            )

        elif action.startswith("inv"):
            # Парсим аргументы из полного текста сообщения
            msg_parts = ctx.message.content.strip().split()
            args = msg_parts[2:] if len(msg_parts) > 2 else []

            # По умолчанию — текущий пользователь
            target_user = username
            if args and args[0] not in ["items", "soups"] and not args[0].isdigit():
                target_user = args.pop(0).lower()

            if target_user not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота. 🐾")
                return

            cat = cats[target_user]
            inventory = cat.get("inventory", [])

            filter_type = "all"
            page = 1

            for arg in args:
                if arg == "items":
                    filter_type = "items"
                elif arg == "soups":
                    filter_type = "soups"
                elif arg.isdigit():
                    page = int(arg)

            if filter_type == "soups":
                filtered = [item for item in inventory if item in SOUPS]
            elif filter_type == "items":
                filtered = [item for item in inventory if item not in SOUPS]
            else:
                filtered = inventory

            if not filtered:
                await ctx.send(f"🐈 | {get_mention(ctx)}, инвентарь пуст.")
                return

            items_per_page = 5
            total_pages = (len(filtered) + items_per_page - 1) // items_per_page
            if page < 1 or page > total_pages:
                await ctx.send(f"🐈 | {get_mention(ctx)}, такой страницы нет. Всего страниц: {total_pages}.")
                return

            start = (page - 1) * items_per_page
            end = start + items_per_page
            page_items = filtered[start:end]

            title_map = {
                "all": "🎒 Инвентарь",
                "items": "🧸 Вещи",
                "soups": "🍲 Супы"
            }
            title = title_map.get(filter_type, "🎒 Инвентарь")
            formatted = ", ".join(page_items)
            await ctx.send(f"🐈 | {get_mention(ctx)}, {title} (стр. {page}/{total_pages}): {formatted}")
        
        elif action == "wash":
            if username not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота. 🐾")
                return

            cat = cats[username]
            cat["cleanliness"] = 100
            save_cats(cats)
            await ctx.send(f"🐈 | {get_mention(ctx)}, кот {cat['name']} теперь чистый и доволен! 🛁✨")

        elif action == "play":
            if username not in cats:
                await ctx.send(f"🐈 | {get_mention(ctx)}, у тебя нет кота. 🐾")
                return

            cat = cats[username]
            cat["happiness"] = min(100, cat["happiness"] + 20)
            save_cats(cats)
            await ctx.send(f"🐈 | {get_mention(ctx)}, кот {cat['name']} поиграл и теперь счастлив! 🎾🐾")

    @commands.Cog.event()
    async def event_ready(self):
        asyncio.create_task(self.ensure_bank_timer())

