import telebot
import requests
import jsons
from Class_ModelResponse import ModelResponse
from environs import Env

env = Env()
env.read_env()
API_TOKEN = env('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

LM_STUDIO_CHAT_URL = 'http://localhost:1234/v1/chat/completions'
LM_STUDIO_MODELS_URL = 'http://localhost:1234/v1/models'

#словарь для хранения контекста
user_contexts = {} 

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """
    /start — приветствие и краткая помощь.
    """
    welcome_text = (
        "Привет! Я Telegram-бот, подключённый к локальной LLM через LM Studio.\n\n"
        "Доступные команды:\n"
        "/start  - показать это сообщение\n"
        "/model  - показать название используемой модели\n"
        "/clear  - очистить контекст диалога (бот забудет прошлый разговор)\n\n"
        "Просто напиши мне любое сообщение — я отвечу с учётом контекста диалога."
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['model'])
def send_model_name(message):
    """
    /model — получаем название модели из LM Studio через GET /v1/models.
    """
    try:
        response = requests.get(LM_STUDIO_MODELS_URL)
    except Exception as e:
        bot.reply_to(message, f'Не удалось подключиться к LM Studio: {e}')
        return

    if response.status_code == 200:
        model_info = response.json()
        # Берём первую модель из списка
        model_name = model_info['data'][0]['id']
        bot.reply_to(message, f"Используемая модель: {model_name}")
    else:
        bot.reply_to(message, 'Не удалось получить информацию о модели.')


@bot.message_handler(commands=['clear'])
def clear_context(message):
    """
    /clear — Шаг 4 задания.
    Очищаем историю диалога для ТЕКУЩЕГО пользователя.
    """
    user_id = message.from_user.id
    # Удаляем контекст, если он есть (если нет — просто игнорируем)
    user_contexts.pop(user_id, None)
    bot.reply_to(message, '🧹 Контекст диалога очищен. Начинаем разговор заново!')


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """
    Основная логика диалога с контекстом (Шаг 3 задания).

    При каждом новом сообщении:
      1) Берём строку истории для данного user_id (или создаём пустую).
      2) Добавляем в историю "user: <текст>".
      3) Отправляем всю строку истории в LM Studio как один большой prompt.
      4) Полученный ответ добавляем в историю как "assistant: <ответ>".
      5) Отправляем ответ пользователю.
    """
    user_id = message.from_user.id
    user_query = message.text

    # 1) История диалога для этого пользователя (если нет — пустая строка)
    history = user_contexts.get(user_id, "")

    # 2) Добавляем текущее сообщение в историю с меткой user
    history += f"user: {user_query}\n"

    # 3) Формируем полный промпт и даем модели небольшую инструкцию
    full_prompt = (
        "Ты — дружелюбный ассистент. Тебе передают историю диалога в формате:\n"
        "user: <сообщение пользователя>\n"
        "assistant: <ответ ассистента>\n"
        "Продолжи диалог и ответь за assistant.\n\n"
        "История диалога:\n"
        f"{history}\n"
        "assistant:"
    )

    request = {
        "messages": [
            {
                "role": "user",
                "content": full_prompt
            }
        ]
    }

    try:
        response = requests.post(
            LM_STUDIO_CHAT_URL,
            json=request
        )
    except Exception as e:
        bot.reply_to(message, f'Ошибка при обращении к модели: {e}')
        return

    if response.status_code == 200:
        
        model_response: ModelResponse = jsons.loads(response.text, ModelResponse)
        answer = model_response.choices[0].message.content.strip()

        # 4) Добавляем ответ ассистента в историю с меткой assistant
        history += f"assistant: {answer}\n"
        user_contexts[user_id] = history  # сохраняем обновлённый контекст

        # 5) Отправляем ответ пользователю
        bot.reply_to(message, answer)
    else:
        bot.reply_to(message, 'Произошла ошибка при обращении к модели.')

if __name__ == '__main__':
    bot.polling(none_stop=True)
