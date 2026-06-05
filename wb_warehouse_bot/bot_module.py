import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile
from aiogram.client.session.aiohttp import AiohttpSession
from config_loader import config
from aiohttp_socks import ProxyConnector

class TelegramBot:
    def __init__(self, on_file_received_callback):
        self.on_file_received_callback = on_file_received_callback
        self.loop = None

        if config.proxy_url:
            connector = ProxyConnector.from_url(config.proxy_url)
            session = AiohttpSession(connector=connector)
            self.bot = Bot(token=config.api_token, session=session)
        else:
            self.bot = Bot(token=config.api_token)

        self.dp = Dispatcher()
        self.setup_handlers()

    def setup_handlers(self):
        @self.dp.message(F.document, F.chat.id == config.admin_chat_id)
        async def handle_document(message: types.Message):
            if message.document.file_name.lower().endswith('.xlsx'):
                file_id = message.document.file_id
                file = await self.bot.get_file(file_id)

                os.makedirs(config.temp_dir, exist_ok=True)
                file_path = os.path.join(config.temp_dir, message.document.file_name)

                await self.bot.download_file(file.file_path, file_path)

                await message.answer(f"Файл {message.document.file_name} получен и готов к сборке.")

                if self.on_file_received_callback:
                    self.on_file_received_callback(file_path)
            else:
                await message.answer("Пожалуйста, отправьте файл в формате .xlsx")

    async def send_result(self, file_path, caption):
        if config.receiver_chat_id:
            try:
                document = FSInputFile(file_path)
                await self.bot.send_document(config.receiver_chat_id, document, caption=caption)
                return True
            except Exception as e:
                logging.error(f"Error sending file: {e}")
                return False
        return False

    async def start(self):
        if not config.api_token:
            logging.error("API Token is not set in config.ini")
            return
        self.loop = asyncio.get_running_loop()
        await self.dp.start_polling(self.bot)

async def run_bot(bot_instance):
    await bot_instance.start()
