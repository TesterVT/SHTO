import asyncio
import websockets
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] rcon-client: %(message)s",
)

URI = "ws://localhost:8765"

async def main():
    try:
        async with websockets.connect(URI) as websocket:
            logging.info("🔌 Подключено к RCON-серверу. Ожидаем логи...")

            try:
                async for message in websocket:
                    print(message)  # Выводим как есть
            except websockets.exceptions.ConnectionClosed:
                logging.warning("❌ Соединение с сервером закрыто")

    except Exception as e:
        logging.exception("❌ Ошибка подключения к RCON-серверу")

if __name__ == "__main__":
    asyncio.run(main())
