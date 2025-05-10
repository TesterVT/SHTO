import json
import random
import asyncio
import time
from twitchio.ext import commands

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
                cat["channel"] = "global"  # или ctx.channel.name.lower() если известно
        save_cats(cats)


    @commands.command(name="cat", aliases=["cot", "koshka"])
    async def cat_command(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "cat"):
            await ctx.send("❌ Использование: !cat(!cat, !koshka) запрещенно на данном канале.")
            return
        args = ctx.message.content.split()
        username = ctx.author.name.lower()

        if len(args) < 2:
            await ctx.send("Доступные команды: adopt, top, inv, friends, feed, soup, info, rename, shop, sell, sell_all, meet, pet")
            return

        action = args[1].lower()
        
        if action == "adopt":
            if username in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя уже есть кот! 🐱")
                return
            name = args[2] if len(args) > 2 else random.choice(["Барсик", "Мурка", "Рыжик"])
            cats[username] = {"name": name, "hunger": 100, "level": 1, "busy": False, "experience": 0, "currency": 0, "food": 1, "inventory": [], "friends": [], "happiness": 100, "cleanliness": 100, "channel": ctx.channel.name.lower(), "boost_until": 0  }
            save_cats(cats)
            await ctx.send(f"@{ctx.author.name} завёл кота {name}! 🐾")

        elif action == "rename":
            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота.")
                return
            new_name = args[2] if len(args) > 2 else "Безымянный"
            cats[username]["name"] = new_name
            save_cats(cats)
            await ctx.send(f"@{ctx.author.name} переименовал кота в {new_name}!")

        elif action == "feed":
            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота. Используй !cat adopt 🐾")
                return
            if cats[username]["food"] <= 0:
                await ctx.send(f"@{ctx.author.name}, у тебя нет еды! Купи её в !cat shop 🛒")
                return
            cats[username]["food"] -= 1
            cats[username]["hunger"] = min(100, cats[username]["hunger"] + 30)
            save_cats(cats)
            await ctx.send(f"@{ctx.author.name} покормил кота {cats[username]['name']} ! 😺")
        
        elif action == "walk":
            user_id = str(ctx.author.name).lower()

            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота.")
                return
            
            cat = cats[username]

            if cat["busy"]:
                await ctx.send(f"{ctx.author.name}, твой кот сейчас занят! 😺")
                return

            # Проверка минимального счастья и чистоты
            if cat["happiness"] < 5:
                await ctx.send(f"{ctx.author.name}, у твоего кота слишком низкое счастье, чтобы идти гулять! 😺")
                return
            if cat["cleanliness"] < 10:
                await ctx.send(f"{ctx.author.name}, твой кот слишком грязный для прогулки! 😺")
                return

            # Устанавливаем кота занятым и запускаем прогулку
            cat["busy"] = True
            walk_time = 30 * 60  # 30 минут

            # Снижение параметров
            cat["happiness"] -= 5
            cat["cleanliness"] = max(0, cat["cleanliness"] - 10)

            save_cats(cats)

            await ctx.send(f"{ctx.author.name}, твой кот отправился на прогулку на 30 минут 🐾")

            await asyncio.sleep(walk_time)

            cat["busy"] = False
            save_cats(cats)

            found_item = random.choice(items) if random.random() < 0.5 else None
            if found_item:
                cat["inventory"].append(found_item)
                await ctx.send(f"@{ctx.author.name}, кот {cat['name']} вернулся с прогулки и нашел: {found_item}! 🎁")
            else:
                await ctx.send(f"@{ctx.author.name}, кот {cat['name']} вернулся с прогулки. 🌿")



        elif action == "soup":
            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота. 🐾")
                return

            cat = cats[username]

            if cat["hunger"] < 10:
                await ctx.send(f"@{ctx.author.name}, кот {cat['name']} слишком голоден, чтобы варить суп! 🍲")
                return

            if cat["busy"]:
                await ctx.send(f"@{ctx.author.name}, кот {cat['name']} уже чем-то занят! ⏳")
                return

            cat["busy"] = True
            save_cats(cats)
            await ctx.send(f"@{ctx.author.name}, кот {cat['name']} начал варить суп! 🍲 Это займет 1 час.")

            await asyncio.sleep(3600)

            cat["busy"] = False
            cat["hunger"] -= 10
            soup_name, (_, price) = random.choice(list(SOUPS.items()))
            cat["inventory"].append(soup_name)
            if username in cats and cats[username]["boost_until"] > time.time():
                # Если буст активен, увеличиваем опыт и доход на 50%
                cat["experience"] += 10 * 1.5  # Увеличиваем опыт
                # Прочие изменения, связанные с бустами
            cat["experience"] += 10

            level_up(cat)
            save_cats(cats)

            await ctx.send(f"@{ctx.author.name}, кот {cat['name']} сварил {soup_name}! 🍽️")



        
        elif action == "sell":
            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота. 🐾")
                return
            for soup, (_, price) in SOUPS.items():
                if soup in cats[username]["inventory"]:
                    cats[username]["inventory"].remove(soup)
                    cats[username]["currency"] += price
                    save_cats(cats)
                    await ctx.send(f"@{ctx.author.name}, кот {cats[username]['name']} продал {soup} за {price} монет! 💰")
                    return
            await ctx.send(f"@{ctx.author.name}, у тебя нет супа для продажи! 🍲")


        elif action == "sell_all":
            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота. 🐾")
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
                await ctx.send(f"@{ctx.author.name}, у тебя нет супа для продажи! 🍲")
            else:
                save_cats(cats)
                await ctx.send(f"@{ctx.author.name}, кот {cats[username]['name']} продал {count} супов за {total_earnings} монет! 💰")

        elif action == "cancel":
            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота. 🐾")
                return
            if not cats[username]["busy"]:
                await ctx.send(f"@{ctx.author.name}, кот {cats[username]['name']} ничем не занят.")
                return
            cats[username]["busy"] = False
            save_cats(cats)
            await ctx.send(f"@{ctx.author.name}, кот {cats[username]['name']} теперь свободен. 🚫")


        elif action == "shop":
            await ctx.send("🛒 В магазине есть: Корм (10 монет) - !cat buy food")
        
        elif action == "buy":
            if len(args) < 3:
                await ctx.send("Используй: !cat buy food")
                return
            if args[2] == "food":
                if cats[username]["currency"] < 10:
                    await ctx.send(f"@{ctx.author.name}, у тебя недостаточно монет! 💰")
                    return
                cats[username]["currency"] -= 10
                cats[username]["food"] += 1
                save_cats(cats)
                await ctx.send(f"@{ctx.author.name} купил корм! 🍖")
            elif args[2] == "boost":
                if cats[username]["currency"] < 50:
                    await ctx.send(f"@{ctx.author.name}, у тебя недостаточно монет! 💰")
                    return
                cats[username]["currency"] -= 50
                # Устанавливаем новый boost_until на 1 час вперёд
                cats[username]["boost_until"] = int(time.time()) + 3600  # Время в секундах + 1 час
                save_cats(cats)
                await ctx.send(f"@{ctx.author.name} купил буст для кота! 🚀")


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
                await ctx.send("На этом канале ещё нет котов для топа.")
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
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота. 🐾")
                return
            cat = cats[username]
            add_petting_stat(cat)
            save_cats(cats)
            await ctx.send(f"@{ctx.author.name} погладил кота {cat['name']} ! 😻")
        
        elif action == "meet":
            if len(args) < 3:
                await ctx.send("Используй: !cat meet <username>")
                return
            friend = args[2].lower()
            if friend not in cats:
                await ctx.send(f"@{ctx.author.name}, у {friend} нет кота. 🐾")
                return
            if friend in cats[username]["friends"]:
                await ctx.send(f"@{ctx.author.name}, ваши коты уже друзья! 🐱🐱")
                return
            cats[username]["friends"].append(friend)
            cats[friend]["friends"].append(username)
            save_cats(cats)
            await ctx.send(f"@{ctx.author.name} и {friend} теперь друзья! 🐱🐱")
        
        elif action.startswith("info"):
            parts = action.split(maxsplit=1)
            target_user = parts[1].lower() if len(parts) > 1 else username
            cat = cats[username]
            if target_user not in cats:
                await ctx.send(f"@{ctx.author.name}, у пользователя {target_user} нет кота. 🐾")
                return

            experience_to_next_level = 100 * cat['level'] + (cat['level'] * 50)

            await ctx.send(
                f"@{ctx.author.name}, {cat['name']} 🐱 | Уровень: {cat['level']} | Опыт: {cat['experience']}/{experience_to_next_level} | "
                f"Сытость: {cat['hunger']}% 🍖 | Чистота: {cat['cleanliness']}% 🛁 | Веселье: {cat['happiness']}% 🎾 | "
                f"Баланс: {cat['currency']} 💰"
            )

        elif action == "friends":
            parts = action.split(maxsplit=1)
            target_user = parts[1].lower() if len(parts) > 1 else username
            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота. 🐾")
                return
            cat = cats[target_user]
            friends = [cats[friend]["name"] for friend in cat["friends"] if friend in cats]
            friends_list = ", ".join(friends) if friends else "Нет"
            await ctx.send(
                f"@{ctx.author.name}, Друзья: {friends_list} 🐱"
            )
        elif action == "inv":
            parts = action.split(maxsplit=1)
            target_user = parts[1].lower() if len(parts) > 1 else username
            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота. 🐾")
                return
            cat = cats[target_user]
            await ctx.send(
                f"@{ctx.author.name}, Инвентарь: {', '.join(cat['inventory']) if cat['inventory'] else 'Пусто'}"
            )

        
        elif action == "wash":
            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота. 🐾")
                return

            cat = cats[username]
            cat["cleanliness"] = 100
            save_cats(cats)
            await ctx.send(f"@{ctx.author.name}, кот {cat['name']} теперь чистый и доволен! 🛁✨")

        elif action == "play":
            if username not in cats:
                await ctx.send(f"@{ctx.author.name}, у тебя нет кота. 🐾")
                return

            cat = cats[username]
            cat["happiness"] = min(100, cat["happiness"] + 20)
            save_cats(cats)
            await ctx.send(f"@{ctx.author.name}, кот {cat['name']} поиграл и теперь счастлив! 🎾🐾")

