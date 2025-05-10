import aiohttp
import datetime
from twitchio.ext import commands
import logging
from modules.profiles import get_mention, get_country

logger = logging.getLogger(__name__)

class HolidayCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="holiday")
    async def holiday(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "holiday"):
            await ctx.send("❌ Использование: !holiday запрещенно на данном канале.")
            return
        parts = ctx.message.content.strip().split()
        country_code = get_country(ctx)  # Код страны по умолчанию

        if len(parts) > 1:
            input_code = parts[1].upper()
            if len(input_code) == 2:
                country_code = input_code
            else:
                await ctx.send("❌ Пожалуйста, укажи корректный ISO-код страны (например, US, DE, FR). Или задайте его через !set country (Код)")
                return

        today = datetime.date.today()
        url = f"https://date.nager.at/api/v3/PublicHolidays/{today.year}/{country_code}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await ctx.send(get_mention(ctx) + f"❌ Не удалось получить информацию о праздниках для страны {country_code}.")
                        return

                    holidays = await resp.json()

            today_str = today.isoformat()
            today_holidays = [h for h in holidays if h["date"] == today_str]

            if today_holidays:
                holiday_names = ", ".join(h["localName"] for h in today_holidays)
                await ctx.send(get_mention(ctx) + f"🎉 Сегодня в стране {country_code} праздник: {holiday_names}")
            else:
                await ctx.send(get_mention(ctx) + f"📅 Сегодня в стране {country_code} нет официальных праздников.")

        except Exception as e:
            logger.error(f"Ошибка при получении праздников: {e}")
            await ctx.send(get_mention(ctx) + "⚠️ Произошла ошибка при получении данных о праздниках.")
