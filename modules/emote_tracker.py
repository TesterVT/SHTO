import aiohttp
import sqlite3
from twitchio.ext import commands
import logging
from modules.profiles import get_mention

logger = logging.getLogger(__name__)

EMOTE_SET_IDS = {
    "PWGood": "01FQTMFVT00000QXHG0DRS80W1",
    "TesterVT": "01G5KVDE480009C64PMWP6XMRR",
    "sillybreadb": "01HVJ758VG000C7ZERGBMEE3Z1",
    "neyrixd": "01HGSNG9C00002PKGXVQTEJ7AM",
    "fELuGOz": "01HV1MRA30000EAQ2CEPNFQQWM"
}

DB_PATH = "emote_usage.db"

class EmoteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_emotes = {}
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emote_usage (
                    channel TEXT,
                    emote TEXT,
                    count INTEGER,
                    PRIMARY KEY(channel, emote)
                )
            """)
            conn.commit()

    @commands.Cog.event("event_ready")
    async def event_ready(self):
        logger.info("EmoteTracker готов, загружаем эмоуты...")
        await self._fetch_all_emotes()

    async def _fetch_all_emotes(self):
        for channel, set_id in EMOTE_SET_IDS.items():
            url = f"https://7tv.io/v3/emote-sets/{set_id}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            emotes = [e["name"] for e in data.get("emotes", [])]
                            self.channel_emotes[channel.lower()] = emotes
                            logger.info(f"Загружено {len(emotes)} эмоутов для канала {channel}")
                        else:
                            logger.warning(f"Не удалось загрузить эмоуты для {channel}: {resp.status}")
            except Exception as e:
                logger.error(f"Ошибка при загрузке эмоутов для {channel}: {e}")

    @commands.Cog.event()
    async def event_message(self, message):
        if message.echo or message.author is None:
            return

        channel = message.channel.name.lower()
        content = message.content

        emotes = self.channel_emotes.get(channel, [])
        words = content.split()
        found = [emote for emote in emotes if emote in words]

        if found:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                for emote in found:
                    cursor.execute("""
                        INSERT INTO emote_usage (channel, emote, count)
                        VALUES (?, ?, 1)
                        ON CONFLICT(channel, emote) DO UPDATE SET count = count + 1
                    """, (channel, emote))
                conn.commit()

    @commands.command(name="estat")
    async def estat_command(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "emote"):
            await ctx.send("❌ Использование: !estat запрещенно на данном канале.")
            return
        parts = ctx.message.content.split(" ", 1)
        if len(parts) < 2:
            await ctx.send(get_mention(ctx) + "❌ Укажи эмоут: !estat <эмоут>")
            return

        emote = parts[1].strip()
        channel = ctx.channel.name

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Получаем количество использований
            cursor.execute("SELECT count FROM emote_usage WHERE channel = ? AND emote = ?", (channel, emote))
            row = cursor.fetchone()

            if not row:
                await ctx.send(get_mention(ctx) + f"ℹ️ Эмоут {emote} ещё не использовался на этом канале.")
                return

            count = row[0]

            # Получаем топ эмоутов
            cursor.execute("""
                SELECT emote, count FROM emote_usage
                WHERE channel = ?
                ORDER BY count DESC
            """, (channel,))
            ranked = cursor.fetchall()

        total = len(ranked)
        position = next((i + 1 for i, (e, _) in enumerate(ranked) if e == emote), None)

        await ctx.send(get_mention(ctx) + f"📊 Эмоут {emote} использовался {count} раз(а) на этом канале. Место: {position}/{total}")

    @commands.command(name="etop")
    async def etop_command(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "emote"):
            await ctx.send("❌ Использование: !etop запрещенно на данном канале.")
            return
        channel = ctx.channel.name

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT emote, count FROM emote_usage
                WHERE channel = ?
                ORDER BY count DESC
                LIMIT 5
            """, (channel,))
            top_emotes = cursor.fetchall()

        if not top_emotes:
            await ctx.send(get_mention(ctx) + "📉 На этом канале пока нет данных об эмоутах.")
            return

        msg = "🔥 Топ 5 эмоутов: " + ", ".join(
            f"{i + 1}. {emote} ({count})" for i, (emote, count) in enumerate(top_emotes)
        )
        await ctx.send(get_mention(ctx) + msg)
