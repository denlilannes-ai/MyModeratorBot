import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv

# ==========================================
#       СЮДА ВСТАВЛЯЕМ НАШИ ТАЙНЫЕ КЛЮЧИ    
# ==========================================

# 1. Токен от BotFather (тот самый 88409...)
BOT_TOKEN = "8840934718:AAHQBUWtrHnlRKy7Tj0U3to89eXCbGXgBco"
# 2. Authorization Key из Сбера (тот самый длинный MD...)
# ВАЖНО: Удали пробелы перед и после кавычек!
AUTH_KEY_SBER = "MDFhMTRmMzMtZTFlNC03ZDc2LTlmNWEtNmRlMTUwMDljNjBmOjlmNThkMTMxLTNhYzYtNGEyOS04N2E4LWY0Y2IxOGQ1MGE4MQ==" 

# ==========================================

if not BOT_TOKEN or "тут_токен" in BOT_TOKEN:
    raise ValueError("❌ Ошибка: Не задан BOT_TOKEN!")

if not AUTH_KEY_SBER or "ВСТАВЬ" in AUTH_KEY_SBER:
    raise ValueError("❌ Ошибка: Ты забыл вставить Authorization Key от Сбера!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

access_token = None
token_expiry = None

async def get_sber_access_token():
    global access_token, token_expiry
    
    # Если токен еще жив, возвращаем его
    if access_token and token_expiry > datetime.now():
        return access_token
    
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        'Authorization': f'Basic {AUTH_KEY_SBER}', # Используем готовый ключ
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {'scope': 'GIGACHAT_API_PERS'}
    
    try:
        async with aiohttp.ClientSession() as session:
            # ssl=False игнорирует проверку сертификатов (важно для некоторых сетей РФ)
            async with session.post(url, headers=headers, data=data, ssl=False) as resp:
                if resp.status == 200:
                    res_json = await resp.json()
                    access_token = res_json['access_token']
                    token_expiry = datetime.now() + timedelta(minutes=55) 
                    print("✅ GigaChat Auth Success")
                    return access_token
                else:
                    err_text = await resp.text()
                    print(f"❌ Auth Error: {resp.status} - {err_text}")
                    return None
    except Exception as e:
        print(f"❌ Exception during auth: {e}")
        return None

SYSTEM_PROMPT = """
Ты - ИИ-модератор Telegram. Анализировать сообщения строго.
Категории:
SPAM (флуд, капс, мусор, пустые символы, спам-стикеры)
ADVERT (реклама каналов, ссылки t.me/vk/youtube, продажа товаров, приглашения)
INSULT (оскорбления, мат, агрессия, угрозы, токсичность)
OK (нормальное общение, вопросы, эмоции, юмор без оскорблений)

Ответь ТОЛЬКО одним словом категории. Без знаков препинания.
"""

async def check_message_ai(text: str) -> str:
    token = await get_sber_access_token()
    if not token:
        return "OK" 
        
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {
        "model": "GigaChat",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
        "temperature": 0.1
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, ssl=False) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ans = data['choices'][0]['message']['content'].strip().upper()
                    clean_ans = "".join(c for c in ans if c.isalpha())
                    
                    if clean_ans in ["SPAM", "ADVERT", "INSULT", "OK"]:
                        return clean_ans
                    
                    # Fallback logic
                    if "СПАМ" in ans or "ФЛУД" in ans: return "SPAM"
                    if "РЕКЛАМА" in ans or "ССЫЛКА" in ans: return "ADVERT"
                    if "ОСКОРБЛЕНИЕ" in ans or "МАТ" in ans: return "INSULT"
                    return "OK"
                else:
                    print(f"GigaChat Err: {resp.status}")
                    return "OK"
    except Exception as e:
        print(e)
        return "OK"

@dp.message()
async def handle_msg(message: types.Message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    if not message.text:
        return
        
    user_id = message.from_user.id
    chat_id = message.chat.id
    text_lower = message.text.lower()
    
    # Быстрые фильтры (без AI)
    banned_domains = ['t.me/', 'wa.me/', 'vk.com/', 'youtube.com', 'boosty.to', 'discord.gg']
    if any(d in text_lower for d in banned_domains):
         verdict = "ADVERT"
    elif len(message.text.strip()) <= 2: # Очень короткие сообщения часто спам
         verdict = "SPAM"
    else:
         # Тяжелая артиллерия - AI
         verdict = await check_message_ai(message.text)
             
    if verdict != "OK":
        try:
            await bot.delete_message(chat_id, message.message_id)
            print(f"[{verdict}] Deleted from @{message.from_user.username}: '{text_lower[:30]}...'")
        except Exception as e:
            print(f"Delete error: {e}")

async def main():
    print("🤖 Starting PRO AI Moderator...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
