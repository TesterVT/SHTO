
import aiohttp
from twitchio.ext import commands

class TranslateCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="translate")
    async def translate(self, ctx: commands.Context):
        args = ctx.message.content.split(" ", 3)
        if len(args) < 4:
            await ctx.send("Использование: !translate <from> <to> <текст>")
            return

        source_lang = args[1]
        target_lang = args[2]
        text = args[3]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://ftapi.pythonanywhere.com/translate", json={
                    "text": text,
                    "source": source_lang,
                    "target": target_lang
                }) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        translated = data.get("translated")
                        if translated:
                            await ctx.send(f"🌍 Перевод: {translated}")
                        else:
                            await ctx.send("❌ Не удалось получить перевод.")
                    else:
                        await ctx.send(f"⚠️ Ошибка сервера перевода: {resp.status}")
        except Exception as e:
            await ctx.send(f"❌ Ошибка перевода: {e}")

def setup(bot):
    bot.add_cog(TranslateCommands(bot))
