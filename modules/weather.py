import aiohttp
import logging
from twitchio.ext import commands
from modules.profiles import get_mention, get_location

logger = logging.getLogger(__name__)

API_KEY = "16bbbd7e4298dfc2e0e6c39b11ff5741"  # Заменить на свой ключ
API_URL = "http://api.openweathermap.org/data/2.5/weather"

class WeatherCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="weather")
    async def weather_command(self, ctx: commands.Context):
        if hasattr(self.bot, "admin") and self.bot.admin.is_module_disabled(ctx.channel.name, "weather"):
            await ctx.send("❌ Использование: !weather запрещенно на данном канале.")
            return
        args = ctx.message.content.strip().split(" ", 1)
        city = args[1].strip() if len(args) > 1 else None

        if not city:
            city = get_location(ctx)

        if not city:
            await ctx.send(get_mention(ctx) + "❌ Укажите город. Пример: !weather Казань. Или задайте его через !set location (город)")
            return

        logger.info(f"Запрос погоды для города: {city}")

        async with aiohttp.ClientSession() as session:
            try:
                params = {
                    "q": city,
                    "appid": API_KEY,
                    "units": "metric",
                    "lang": "ru"
                }
                async with session.get(API_URL, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        name = data["name"]
                        temp = data["main"]["temp"]
                        weather_desc = data["weather"][0]["description"]
                        humidity = data["main"]["humidity"]
                        wind = data["wind"]["speed"]

                        response = (f"🌦 Погода в {name}: {weather_desc.capitalize()}, 🌡 {temp}°C, "
                                    f"💧 Влажность: {humidity}%, 💨 Ветер: {wind} м/с.")
                        await ctx.send(get_mention(ctx) + response)
                    else:
                        await ctx.send(get_mention(ctx) + f"❌ Не удалось получить погоду для '{city}'.")
            except Exception as e:
                logger.error(get_mention(ctx) + f"Ошибка при получении погоды: {e}")
                await ctx.send(get_mention(ctx) + "❌ Произошла ошибка при получении погоды.")
