import logging
import json
import random
import asyncio
import datetime
import requests
import twitchio
from twitchio.ext import commands
from Logger import log_to_file
from modules import cats, general, admin, city, mafia, rcon_module, weather, alias, AI, emote_tracker, holiday, profiles
from modules.general import afk_times, sleep_times 
import time
import aiohttp
import re
import aiosqlite
from data import config_loader
from modules.profiles import upsert_profile
from modules.filter import FilterModule

TOKEN = config_loader.get_token()
CHANNELS = config_loader.get_channels()
OWNERS = config_loader.get_owners()
OWNER_CHANNEL = config_loader.get_owner_channel()
EMOTE_SET_ID = config_loader.get_emote_set_id()


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


emotes_list = []

class TwitchBot(commands.Bot):
    def __init__(self):
        super().__init__(token=TOKEN, prefix="!", initial_channels=CHANNELS)
        self.load_modules()
        self.loaded_modules = {"cat", "general", "admin", "city", "mafia","rcon_module","weather","alias", "AI", "emote_tracker", "holiday", "profile"}
        self.loop.create_task(self.periodic_emote_update())
        admin_cog = admin.AdminCommands(self)
        self.admin = admin_cog
        self.filter = FilterModule()

    def load_modules(self):
        self.loaded_modules = set()

        for module_name, module in [("cat", cats), ("general", general), ("admin", admin), ("city", city),("mafia", mafia),("rcon", rcon_module),("weather",weather),("alias", alias),("ai", AI), ("emote", emote_tracker), ("holiday", holiday), ("profle", profiles)]:
            try:
                logger.debug(f"Попытка загрузить модуль: {module_name}")

                # Если модуль уже загружен, сначала выгружаем его
                if module_name in self.loaded_modules:
                    logger.info(f"Модуль {module_name} уже загружен. Выгружаю перед повторной загрузкой.")
                    self.unload_module(module_name)

                # Поиск класса-кога в модуле
                cog_class = next(
                    (getattr(module, attr) for attr in dir(module) if isinstance(getattr(module, attr), type)),
                    None
                )

                if cog_class:
                    self.add_cog(cog_class(self))
                    self.loaded_modules.add(module_name)
                    logger.info(f"Модуль {module_name} успешно загружен!")
                else:
                    logger.warning(f"Не найден класс-cog в модуле {module_name}, пропускаю!")

            except Exception as e:
                logger.error(f"Ошибка загрузки модуля {module_name}: {e}", exc_info=True)




    async def event_ready(self):
        logger.info(f"Бот подключился как {self.nick}")
        await self.fetch_emotes()
        
    async def event_message(self, message):
        if message.author is None:
            return

        username = message.author.name.lower()
        now = datetime.datetime.now()

        # Удаляем пробел между префиксом и командой для !cat, !cot, !koshka
        if message.content.startswith(("! cat", "! cot", "! koshka")):
            message.content = message.content.replace("! ", "!", 1)

        if username in afk_times:
            duration = now - afk_times.pop(username)
            await message.channel.send(f"@{message.author.name} вернулся из AFK. Был AFK {str(duration).split('.')[0]}")

        if username in sleep_times:
            duration = now - sleep_times.pop(username)
            await message.channel.send(f"@{message.author.name} проснулся после сна. Спал {str(duration).split('.')[0]}")

        if admin.echo_user and username == admin.echo_user:
            if self.filter.check_message(message.content):
                logger.warning(f"🚫 Сообщение от {message.author.name} содержит запрещённые слова: {message.content}")
                return
            else:
                await message.channel.send(message.content)

        if self.filter.check_message(message.content):
            logger.warning(f"🚫 Сообщение от {message.author.name} содержит запрещённые слова: {message.content}")
            return

        # ⬇️ Автоматическое создание профиля, если его нет
        twitch_id = str(message.author.id)
        nickname = message.author.name
        upsert_profile(twitch_id, nickname)

        channel_name = message.channel.name.lower()
        admin_cog = self.get_cog("AdminCommands")
        admin_cog.cursor.execute("SELECT 1 FROM disabled_channels WHERE channel_name = ?", (channel_name,))
        command_prefixes = ['!', '!!']
        if admin_cog.cursor.fetchone():
            if any(message.content.startswith(p) for p in command_prefixes):
                return


        if hasattr(bot.get_cog("AdminCommands"), "is_ignored"):
            if bot.get_cog("AdminCommands").is_ignored(message.author.name.lower()):
                return

        logger.info(f"[{message.author.name}]: {message.content}")


        # Обработка кастомных (!!) алиасов
        # Внутри event_message — ДО handle_commands(message)
        if message.content.startswith("!!"):
            clean_content = "!!" + message.content[2:].lstrip()  # удаляем пробелы после !!
            logger.info(f"➡️ Проверка алиаса: {clean_content}")
            message.content = clean_content  # заменяем сообщение на очищенное
            handled = await alias.AliasCommands.handle_custom_alias(self, message)
            if handled:
                return
        

        from Logger import log_to_file
        log_to_file(message.author.name, message.content)
        await self.handle_commands(message)


    async def fetch_emotes(self):
        global emotes_list
        try:
            response = requests.get(f"https://7tv.io/v3/emote-sets/{EMOTE_SET_ID}")
            response.raise_for_status()
            data = response.json()
            if "emotes" in data:
                emotes_list = [emote["name"] for emote in data["emotes"]]
                logger.info(f"Загружено {len(emotes_list)} эмоутов.")
        except requests.RequestException as e:
            logger.error(f"Ошибка загрузки эмоутов: {e}")

    async def periodic_emote_update(self):
        while True:
            await asyncio.sleep(600)  # Каждые 10 минут
            if emotes_list:
                random_emote = random.choice(emotes_list)
                channel = self.get_channel(OWNER_CHANNEL)
                if channel:
                    await channel.send(random_emote)
                    logger.info(f"Отправлен эмоут: {random_emote}")


while True:
    try:
        bot = TwitchBot()
        bot.run()
    except (aiohttp.ClientConnectionError, ConnectionResetError, asyncio.CancelledError) as e:
        logger.warning(f"🔌 Потеря соединения с Twitch: {e}. Перезапуск через 10 секунд...")
        time.sleep(10)
    except Exception as e:
        logger.exception("❌ Неизвестная ошибка, бот будет перезапущен через 30 секунд")
        time.sleep(30)
