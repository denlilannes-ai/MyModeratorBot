import os
import asyncio
import base64
import json
import aiohttp
import uuid
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from dotenv import load_dotenv

# Загружаем переменные окружения (из настроек хостинга)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("SBER_CLIENT_ID")
CLIENT_SECRET = os.getenv("SBER_CLIENT_SECRET")

if not all([BOT_TOKEN, CLIENT_ID, CLIENT_SECRET]):
    raise ValueError("Не заданы BOT_TOKEN, SBER_CLIENT_ID или SBER_CLIENT_SECRET в настройках!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

access_token = None
token_expiry = None

# Функция получения токена доступа к API Сбера
async def get_sber_access_token():
    global access_token, token_expiry
    if access_token and token_expiry > datetime.now():
        return access_token
    
    credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_bytes = base64.b64encode(credentials.encode()).decode('ascii')
    
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        'Authorization': f'Basic {auth_bytes}',
        'RqUID': str(uuid.uuid4()),
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {'scope': 'GIGACHAT_API_PERS'}
    
    async with aiohttp.ClientSession() as session:
        try:
            # ВАЖНО: ssl=False игнорирует проверку сертификатов Сбербанка. 
            # Для продакшена лучше скачать их сертификат, но для быстрого старта это работает.
            async with session.post(url, headers=headers, data=data, ssl=False) as resp:
                if resp.status == 200:
                    res_json = await resp.json()
                    access_token = res_json['access_token']
                    # Токен живёт обычно час, ставим запас 5 минут
                    token_expiry = datetime.now() + timedelta(minutes=55) 
                    print("Successfully got new Sber Access Token")
                    return access_token
                else:
                    print(f"Error getting token: {resp.status}, {await resp.text()}")
                    return None
        except Exception as e:
            print(f"Exception during token request: {e}")
            return None

SYSTEM_PROMPT = """
Ты - строгий модератор чата. Проанализируй сообщение пользователя.
Категории нарушений:
1. SPAM (флуд, капс, бессмыслица, повторяющиеся символы)
2. ADVERT (реклама других каналов, ссылки, продажа чего-либо, приглашения в другие группы)
3. INSULT (оскорбления, мат, агрессия, угрозы)
4. OK (обычное общение по теме, вопросы, реакции)

Ответь ТОЛЬКО одним словом категории. Например: ADVERT
"""

async def check_message(text: str) -> str:
    token = await get_sber_access_token()
    if not token:
        return "OK" # Если нет связи с AI, пропускаем, чтобы не банить всех подряд
        
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "temperature": 0.1
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, ssl=False) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    answer = data['choices'][0]['message']['content'].strip().upper()
                    return answer
                else:
                    print(f"GigaChat Error: {resp.status}")
                    return "OK"
        except Exception as e:
            print(e)
            return "OK"

@dp.message()
async def handle_msg(message: types.Message):
    # Работаем только в группах (чатах обсуждений)
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if not message.text:
        return
        
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Быстрая проверка на ссылки до обращения к AI (экономия ресурсов)
    if any(x in message.text.lower() for x in ['t.me/', 'wa.me/', 'vk.com/']):
        verdict = "ADVERT"
    else:
        verdict = await check_message(message.text)
        
    if verdict != "OK":
        try:
            await bot.delete_message(chat_id, message.message_id)
            print(f"Banned/Deleted msg from {user_id}. Reason: {verdict}")
        except Exception as e:
            print(f"Delete error: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
