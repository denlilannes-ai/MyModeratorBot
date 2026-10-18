import os
import asyncio
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv

# ТВОЙ ТОКЕН ПРЯМО В КОДЕ (для теста)
# Скопируй сюда тот длинный набор символов, что дал BotFather
TOKEN = "8840934718:AAHQBUWtrHnlRKy7Tj0U3to89eXCbGXgBco" 

if not TOKEN or "тут_токен" in TOKEN:
    print("ОШИБКА: Не заменен токен в коде!")
else:
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    @dp.message()
    async def handle_msg(message: types.Message):
        # Просто пишем в консоль, что сообщение получено
        print(f"[{message.from_user.username}] {message.text}")
        
        # Пример фильтрации без AI (просто проверка слов)
        bad_words = ["спам", "реклама"]
        if any(word in message.text.lower() for word in bad_words):
             await message.delete()
             print("Сообщение удалено (фильтр)")

    async def main():
        print("Бот запускается...")
        await dp.start_polling(bot)

    if __name__ == "__main__":
        try:
            asyncio.run(main())
        except Exception as e:
            print(f"Ошибка запуска: {e}")
