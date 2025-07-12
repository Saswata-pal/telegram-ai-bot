import asyncio
import os
import nest_asyncio
import base64
import tempfile
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import OpenAI
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

conversation_history = {}

# === Utility ===
def trim_history(user_id):
    if len(conversation_history[user_id]) > 20:
        conversation_history[user_id] = [conversation_history[user_id][0]] + conversation_history[user_id][-20:]

async def gemini_reply(user_message):
    payload = {
        "contents": [
            {
                "parts": [{"text": user_message}]
            }
        ]
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_API_KEY}"
    }
    try:
        response = requests.post(GEMINI_URL, headers=headers, json=payload)
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print("Gemini Error:", e)
        return "⚠️ Gemini API Error. Please try again later."

# === Start ===
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(
        "👋 Hello! I'm *Handle Warrior*, your AI assistant.\n\n"
        "📩 Send me *text*, 🎤 *voice*, or 🖼 *image*, and I’ll reply instantly.\n\n"
        "Powered by OpenAI + Gemini."
    )

# === TEXT ===
@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    user_message = message.text

    if user_id not in conversation_history:
        conversation_history[user_id] = [
            {"role": "system", "content": "You are a helpful assistant named Handle Warrior and developed by Saswata Pal."}
        ]
    conversation_history[user_id].append({"role": "user", "content": user_message})

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=conversation_history[user_id]
        )
        reply = response.choices[0].message.content
        conversation_history[user_id].append({"role": "assistant", "content": reply})
        trim_history(user_id)
    except Exception as e:
        print("OpenAI Error:", e)
        reply = await gemini_reply(user_message)

    await message.answer(reply)

# === VOICE ===
@dp.message(F.voice)
async def handle_voice(message: types.Message):
    user_id = message.from_user.id
    file_info = await bot.get_file(message.voice.file_id)
    voice_data = await bot.download_file(file_info.file_path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_voice:
        temp_voice.write(voice_data.read())
        temp_voice_path = temp_voice.name

    try:
        with open(temp_voice_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        transcribed_text = transcript.text

        if user_id not in conversation_history:
            conversation_history[user_id] = [
                {"role": "system", "content": "You are a helpful assistant named Handle Warrior and developed by Saswata Pal."}
            ]
        conversation_history[user_id].append({"role": "user", "content": transcribed_text})

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=conversation_history[user_id]
        )
        reply = response.choices[0].message.content
        conversation_history[user_id].append({"role": "assistant", "content": reply})
        trim_history(user_id)

        await message.answer(f"🗣 You said: {transcribed_text}\n🤖 Reply: {reply}")
    except Exception as e:
        print("Voice Error:", e)
        await message.answer("⚠️ Voice transcription not available now.")
    finally:
        os.remove(temp_voice_path)

# === IMAGE ===
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    photo_data = await bot.download_file(file_info.file_path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_photo:
        temp_photo.write(photo_data.read())
        photo_path = temp_photo.name

    try:
        with open(photo_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this image and describe it."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )
        reply = response.choices[0].message.content
        await message.answer(f"🖼 Image Analysis:\n{reply}")
    except Exception as e:
        print("Image Error:", e)
        await message.answer("⚠️ Image analysis not available now.")
    finally:
        os.remove(photo_path)

# === MAIN LOOP ===
async def main():
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Start the bot"),
    ])
    print("🤖 Bot is running 24/7...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
