
import asyncio
import json
import logging
import os
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatAction

# --- Конфігурація ---
# Настійно рекомендується використовувати змінні середовища для конфіденційних даних.
# Ви можете отримати токен від BotFather в Telegram.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8221223031:AAH1d3CIYyWmRrFQnq6dRc47oeq-Xl-30aw")

# Ваш ключ API OpenRouter. Також завантажується зі змінних середовища.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

# Налаштування логування, щоб бачити активність бота та потенційні помилки.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Ініціалізація та перевірка конфігурації ---
if not TELEGRAM_BOT_TOKEN:
    # Вийти, якщо токен Telegram не надано.
    raise ValueError("Не знайдено TELEGRAM_BOT_TOKEN у змінних середовища. Будь ласка, встановіть його.")

if not OPENROUTER_API_KEY:
    # Вийти, якщо ключ OpenRouter не надано.
    raise ValueError("Не знайдено OPENROUTER_API_KEY у змінних середовища. Будь ласка, встановіть його.")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
conversation_history = {} # Сховище в пам'яті для історії розмов {chat_id: [повідомлення]}
MESSAGE_HISTORY_LIMIT = 25


def get_ai_response(messages: list[dict[str, str]]) -> str:
    """
    Надсилає повідомлення до OpenRouter API та отримує відповідь.

    Args:
        messages: Список словників повідомлень, що представляють історію розмови.

    Returns:
        Вміст повідомлення-відповіді від AI.
    """
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": "deepseek/deepseek-r1-0528:free", # Вказана вами модель
                "messages": messages,
            })
        )

        # Raise an exception for bad status codes (e.g., 4xx or 5xx)
        response.raise_for_status()

        response_data = response.json()
        ai_message = response_data['choices'][0]['message']['content']
        return ai_message.strip()

    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling OpenRouter API: {e}")
        return "Вибачте, сталася помилка під час звернення до сервісу AI."
    except (KeyError, IndexError) as e:
        logging.error(f"Error parsing API response: {e}\nResponse data: {response.text}")
        return "Вибачте, я отримав неочікувану відповідь від сервісу AI."


# --- Обробники бота ---

@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    """
    Цей обробник буде викликаний, коли користувач надішле команду `/start`.
    """
    await message.reply("Привіт!\nЯ ваш простий AI-асистент. Я можу пам'ятати наші останні повідомлення. Надішліть мені повідомлення, щоб почати, або використайте /clear, щоб скинути нашу розмову.")


@dp.message(Command("clear"))
async def clear_history(message: types.Message):
    """
    Очищує історію розмови для користувача.
    """
    chat_id = message.chat.id
    if chat_id in conversation_history:
        del conversation_history[chat_id]
        await message.reply("Вашу історію розмов було очищено.")
    else:
        await message.reply("У вас немає історії розмов для очищення.")


@dp.message()
async def handle_message(message: types.Message):
    """
    Цей обробник буде обробляти будь-яке текстове повідомлення користувача.
    """
    if not message.text:
        await message.reply("Будь ласка, надішліть текстове повідомлення.")
        return

    chat_id = message.chat.id

    # Показати користувачеві статус "друкує...", щоб покращити взаємодію
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # Отримати поточну історію для цього чату або порожній список, якщо це нова розмова
    chat_history = conversation_history.get(chat_id, [])

    # Додати нове повідомлення користувача до історії
    chat_history.append({"role": "user", "content": message.text})

    # Обрізати історію до вказаного ліміту, щоб зберегти контекст релевантним
    chat_history = chat_history[-MESSAGE_HISTORY_LIMIT:]

    # Бібліотека `requests` є синхронною. Щоб уникнути блокування бота,
    # ми запускаємо виклик API в окремому потоці.
    ai_response_text = await asyncio.to_thread(get_ai_response, chat_history)

    # Додати відповідь AI до історії для майбутнього контексту
    chat_history.append({"role": "assistant", "content": ai_response_text})
    conversation_history[chat_id] = chat_history

    # Надіслати відповідь AI користувачеві
    await message.reply(ai_response_text)


async def main() -> None:
    """Запускає опитування бота."""
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())