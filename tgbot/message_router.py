from aiogram import Router, types, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import conn, cursor, bot
import os
from pydub import AudioSegment
from whisper import translate_audio
import requests
import warnings
# Игнорировать предупреждения
warnings.filterwarnings('ignore')

# Создать директорию 'voices', если она не существует
if not os.path.exists("voices"):
    os.makedirs("voices")

# Инициализация маршрутизатора
router = Router()
users = {}

def hsh(user_id):
    """Возвращает хеш от ID пользователя."""
    return str(hash(user_id))

def is_first_question(user_id):
    """Проверяет, первый ли это вопрос пользователя."""
    cursor.execute("SELECT COUNT(*) FROM likes WHERE user_id = %s", (str(user_id),))
    result = cursor.fetchone()
    return result[0] == 1

@router.message(Command('start'))
async def start_handler(message: Message):
    """Обрабатывает команду /start."""
    user_hash = hsh(message.from_user.id)
    users[user_hash] = {'query': ".", 'content': ".", 'f': True}
    await message.answer(f"Здравствуйте, {message.chat.username}, я ИИ ассистент компании СИЛА. Чем могу быть полезен?")

@router.message(Command('clear_history'))
async def clear_history_handler(message: Message):
    """Очищает историю общения пользователя."""
    cursor.execute("UPDATE likes SET history = 0 WHERE user_id = %s", (hsh(message.from_user.id),))
    conn.commit()
    await message.reply("История общения очищена")

def get_llm_answer(question, history):
    """Получает ответ от модели LLM."""
    response = requests.post(
        "https://usable-sharp-terrapin.ngrok-free.app/predict",
        json={"query": question, "history": history}
    )
    response_json = response.json()
    return response_json

async def save_voice_message(voice: types.Voice, file_name: str):
    """Сохраняет голосовое сообщение в файл."""
    file = await bot.get_file(voice.file_id)
    await bot.download_file(file.file_path, file_name)
    audio = AudioSegment.from_file(file_name, format="ogg")
    audio.export(file_name, format="mp3")

def process_voice_message_to_text(file_name: str) -> str:
    """Преобразует голосовое сообщение в текст."""
    return translate_audio(file_name)

def get_last_3(user_id):
    """Получает последние 3 успешных запроса пользователя."""
    cursor.execute(
        "SELECT query FROM likes WHERE user_id = %s AND reaction * history = 1 LIMIT 3",
        (user_id,)
    )
    rows = cursor.fetchall()
    if not rows:
        return ""
    his = [row[0] for row in rows]
    return " ".join(his)

async def add_reaction(callback: types.CallbackQuery, reaction: int):
    print(reaction)
    """Добавляет лайк или дизлайк."""
    user_hash = hsh(callback.from_user.id)
    users[user_hash]['f'] = True

    # Удаление разметки кнопок
    await bot.edit_message_reply_markup(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=None
    )

    # Вставка записи в базу данных
    if reaction == 1:
        history_value = 1 
    else:
        history_value = 0
    cursor.execute(
        """INSERT INTO likes(user_id, reaction, query, answer, history)
           VALUES (%s, %s, %s, %s, %s)""",
        (callback.message.chat.id, reaction, users[user_hash]['query'], users[user_hash]['content'], history_value)
    )
    conn.commit()

    # Проверка, первый ли это вопрос
    if is_first_question(callback.message.chat.id):
        if reaction == 1:
            await callback.message.answer(
                'Мы рады, что ваш вопрос решился! Если у вас есть другие вопросы, вы можете задать их мне!')
        else:
            await callback.message.answer(
                'Очень жаль, что мой ответ вас не устроил. Если у вас есть другие вопросы, вы можете задать их мне!')

@router.callback_query(F.data == 'like')
async def like(callback: types.CallbackQuery):
    """Обрабатывает нажатие на кнопку '👍'."""
    await add_reaction(callback, 1)

@router.callback_query(F.data == 'dislike')
async def dislike(callback: types.CallbackQuery):
    """Обрабатывает нажатие на кнопку '👎'."""
    await add_reaction(callback, 0)

@router.message()
async def any_message(message: Message):
    """Обрабатывает любые сообщения от пользователя."""
    user_hash = hsh(message.from_user.id)

    # Обработка неизвестных команд
    if message.text and message.text.startswith('/'):
        await message.answer('Неизвестная команда!')
        return

    # Проверка наличия пользователя в базе данных
    if user_hash not in users:
        await message.answer('Пожалуйста, нажмите /start сначала')
        return

    # Проверка флага готовности пользователя
    if users[user_hash]['f']:
        wait_msg = await message.answer('Пожалуйста, подождите. Генерирую ответ!')
        await bot.send_chat_action(message.chat.id, 'typing')

        # Обработка голосового сообщения
        if message.voice is not None:
            file_name = f"voices/voice_{user_hash}_{message.message_id}.mp3"
            await save_voice_message(message.voice, file_name)
            text = process_voice_message_to_text(file_name)
        else:
            text = message.text

        if text:
            # Получение ответа от модели
            history = get_last_3(user_hash)
            # Получаем ответ и список фотографий
            llm_ans = get_llm_answer(text, history)
            answer, photos_list, titles = llm_ans['answer'], llm_ans['photos'], llm_ans['titles']
            await bot.delete_message(message.chat.id, wait_msg.message_id)

            # Проверка и отправка ответа
            if ('К сожалению, я не могу ответить на ваш вопрос.' not in str(answer)) and  ('К сожалению, на данный момент я не могу ответить' not in str(answer)):
                users[user_hash] = {'query': text, 'content': answer, 'f': False}
                builder = InlineKeyboardBuilder()
                builder.button(text="👍", callback_data="like")
                builder.button(text="👎", callback_data="dislike")

                # Отправляем ответ пользователю, включая названия разделов, на которые ссылается ответ
                if titles == []:
                    await message.answer(answer, reply_markup=builder.as_markup())
                else:
                    answer += f"\n\n*Ответ ссылается на информацию из следующий фрагментов документации:*\n"
                    for i, title in enumerate(titles):
                        answer += f"{i + 1}) {title}\n" 
                    await message.answer(answer, reply_markup=builder.as_markup(), parse_mode= "Markdown")


                # Если список фотографий не пустой, отправляем фотографии
                if photos_list:
                    for photo in photos_list:
                        path = photo['path'].replace('\\', '/')
                        description = photo['description']
                        try:
                            input_file = FSInputFile(path)
                        except:
                            input_file = FSInputFile(path.replace('.png', '.PNG'))

                        await bot.send_photo(message.chat.id, input_file, caption=description)
            else:
                if 'Также вы можете сами ознакомиться с документацией.' in answer:
                    input_file = FSInputFile("data/train/documentation.docx")
                    await bot.send_document(message.chat.id, input_file, caption=answer, parse_mode= "Markdown")
                else:
                    await message.answer(answer, parse_mode= "Markdown")
        else:
            await message.answer("К сожалению, вы ничего не сказали. Пожалуйста, повторите ваш вопрос.")
    else:
        await message.answer("Поставьте реакцию на ответ помощника перед тем, как задавать новый вопрос.")
