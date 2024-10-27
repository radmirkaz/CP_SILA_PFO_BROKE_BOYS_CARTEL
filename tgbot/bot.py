import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
import message_router
import psycopg2
import logging
import warnings
warnings.simplefilter('ignore')

# Инициализация бота
BOT_TOKEN = "8127208769:AAHTf-K-mCQYRplc7Vs5YkI-ePzEJH_ca2k"
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

# Настройка базы данных
DB_USER = "imagineuser"
DB_PASSWORD = "FT-EB9r2z55622M1b"
DB_NAME = "brokeboyscartel"
DB_HOST = "83.166.236.254"

# Подключение к базе данных
conn = psycopg2.connect(
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST
)
cursor = conn.cursor()

# Создание таблицы 'likes' если не существует
cursor.execute("""
    CREATE TABLE IF NOT EXISTS likes (
        user_id TEXT,
        reaction INT,
        query TEXT,
        answer TEXT,
        history INT)""")
conn.commit()

# Запуск бота и обработка сообщений
async def main() -> None:
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        dp = Dispatcher()
        dp.include_router(message_router.router)
        await dp.start_polling(bot)
    except Exception as e:
        await asyncio.sleep(5)  
        await main()

if __name__ == "__main__":
    asyncio.run(main())
