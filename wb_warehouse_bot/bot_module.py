import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile
from aiogram.client.session.aiohttp import AiohttpSession
from config_loader import config
from aiohttp_socks import ProxyConnector
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

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
        @self.dp.message(F.document, lambda m: m.chat.id in config.admin_chat_ids)
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
        receivers = config.receiver_chat_ids
        if not receivers:
            logging.error("No receiver Chat IDs set.")
            return False

        success = False
        for chat_id in receivers:
            try:
                document = FSInputFile(file_path)
                await self.bot.send_document(chat_id, document, caption=caption)
                success = True
                logging.info(f"Result sent to {chat_id}")
            except TelegramBadRequest as e:
                logging.error(f"Telegram Bad Request for {chat_id}: {e}")
            except TelegramForbiddenError as e:
                logging.error(f"Telegram Forbidden for {chat_id}: {e}")
            except Exception as e:
                logging.error(f"Error sending file to {chat_id}: {e}")
        return success

    async def start(self):
        if not config.api_token:
            logging.error("API Token is not set in config.ini")
            return
        self.loop = asyncio.get_running_loop()
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logging.error(f"Bot polling error: {e}")

async def run_bot(bot_instance):
    await bot_instance.start()
