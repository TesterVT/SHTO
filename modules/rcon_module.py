import asyncio
import logging
import sys
from twitchio.ext import commands
import websockets

logger = logging.getLogger(__name__)


class RconLogHandler(logging.Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        try:
            msg = self.format(record)
            asyncio.get_event_loop().call_soon_threadsafe(self.queue.put_nowait, msg)
        except Exception:
            self.handleError(record)


class RconCommands(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.clients = set()
        self.queue = asyncio.Queue()

        # Перехват stdout
        sys.stdout = self
        sys.stderr = self

        # Подключение логгер-хендлера
        handler = RconLogHandler(self.queue)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self.run_server())
        self.loop.create_task(self.message_dispatcher())

    def write(self, message):
        """Перехватывает stdout и добавляет в очередь"""
        if message.strip():
            self.queue.put_nowait(message.strip())

    def flush(self):
        pass  # для совместимости с sys.stdout

    async def message_dispatcher(self):
        while True:
            msg = await self.queue.get()
            await self.broadcast(msg)

    async def broadcast(self, message):
        for client in list(self.clients):
            try:
                await client.send(message)
            except Exception as e:
                logger.warning(f"Ошибка при отправке клиенту: {e}")
                self.clients.discard(client)

    async def handle_client(self, websocket, path):
        logger.info("📡 Новое подключение RCON-клиента")
        self.clients.add(websocket)
        try:
            async for _ in websocket:
                pass  # Ничего не получаем, только отправляем
        except websockets.exceptions.ConnectionClosed:
            logger.info("🔌 Клиент отключился")
        except Exception as e:
            logger.exception("❌ Ошибка в клиенте RCON")
        finally:
            self.clients.discard(websocket)

    async def run_server(self):
        try:
            server = await websockets.serve(self.handle_client, "0.0.0.0", 8765)
            logger.info("✅ RCON сервер запущен на порту 8765 (без TLS)")
        except Exception as e:
            logger.exception("❌ Не удалось запустить RCON сервер")
