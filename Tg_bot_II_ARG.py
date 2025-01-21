import aiosqlite
import logging
import asyncio
import uuid
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aiogram.filters.state import StateFilter
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from typing import Callable, Any, Awaitable
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup
from aiogram.types import KeyboardButtonPollType, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup, ReplyKeyboardBuilder
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import json
import os
from aiogram import types
import urllib3
from urllib3.exceptions import InsecureRequestWarning
# Отключаем предупреждения
urllib3.disable_warnings(InsecureRequestWarning)


# Логирование
logging.basicConfig(force=True, level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Токен бота и инициализация
token = '7620230370:AAF8yX-XKHErApGkWg8eWpUxY7E9ShEfhSg'
bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Настройки GigaChat
GIGACHAT_TOKEN = "MWI4YmEzOTAtYTQwMS00OGM5LTk3ODYtNDFlNjg1MTg1NTIzOjY2YmEyZjY4LWM3NDAtNGU4Mi04NGQ2LWNlZmZkZTk4NzViOQ=="

def get_gigachat_access_token():
    """Получение токена доступа для GigaChat."""
    rq_uid = str(uuid.uuid4())
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    payload = {
        'scope': 'GIGACHAT_API_PERS'
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': rq_uid,
        'Authorization': f'Basic {GIGACHAT_TOKEN}'
    }

    try:
        response = requests.post(url, headers=headers, data=payload, verify=False)
        response.raise_for_status()
        return response.json()['access_token']
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе к GigaChat API: {e}")
        return None


def generate_motivation(category: str) -> str:
    """Генерация мотивационной цитаты с использованием GigaChat."""
    try:
        giga_token = get_gigachat_access_token()
        if not giga_token:
            return "Не удалось получить токен для GigaChat. Проверьте настройки API."

        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        payload = json.dumps({
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "Ты - бот для поддержания мотивации. Ты присылаешь позитивные цитаты."},
                {"role": "user", "content": f"Сгенерируй мотивационную цитату на тему: {category}."}
            ],
            "temperature": 1.0,  # Увеличить температуру для большего разнообразия
            "top_p": 0.8,  # увеличить top_p для большего разнообразия
            "n": 1,
            "stream": False,
            "max_tokens": 90,
            "repetition_penalty": 2.5,  # Увеличить штраф за повторение
            "update_interval": 0
        })
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {giga_token}'
        }

        response = requests.post(url, headers=headers, data=payload, verify=False)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе к GigaChat: {e}")
        return "Не удалось получить мотивационную фразу. Попробуйте позже."
    except Exception as e:
        logging.error(f"Неизвестная ошибка при генерации мотивации: {e}")
        return "Не удалось получить мотивационную фразу. Попробуйте позже."

def send_to_gigachat(user_message: str) -> str:
    """Отправка сообщения пользователем в GigaChat и получение ответа."""
    try:
        giga_token = get_gigachat_access_token()
        if not giga_token:
            return "Не удалось получить токен для GigaChat. Проверьте настройки API."

        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        payload = json.dumps({
            "model": "GigaChat",
            "messages": [
                {"role": "system", "content": "Ты - бот-психолог, который внимательно выслушивает пользователя и помогает ему, задавая наводящие вопросы."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 1.2,
            "top_p": 1.0,
            "n": 1,
            "stream": False,
            "max_tokens": 200,
            "repetition_penalty": 2.5,
            "update_interval": 0
        })
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {giga_token}'
        }

        response = requests.post(url, headers=headers, data=payload, verify=False)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе к GigaChat: {e}")
        return "Не удалось получить ответ от GigaChat. Попробуйте позже."
    except Exception as e:
        logging.error(f"Неизвестная ошибка при отправке сообщения в GigaChat: {e}")
        return "Не удалось получить ответ от GigaChat. Попробуйте позже."


# Определение состояний формы
class Form(StatesGroup):
    name = State() # Состояние для ввода ФИО
    age = State() # Состояние для ввода номера возраста
# Словарь для хранения задач (чтобы их можно было завершить при необходимости)
active_tasks = {}

async def create_db():
    """Создание таблицы в базе данных для пользователей, если она еще не существует."""
    async with aiosqlite.connect("users.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                last_name TEXT,
                first_name TEXT,
                age_number TEXT
            )
        """)
        await db.commit()

async def add_user_to_db(user_id, last_name, first_name, age_number):
    """Добавление или обновление пользователя в базе данных."""
    async with aiosqlite.connect("users.db") as db:
        # Проверка на существование пользователя по user_id
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if user:
            print(f"User {user_id} already exists. Updating info.")
            await db.execute("UPDATE users SET last_name = ?, first_name = ?, age_number = ? WHERE user_id = ?",
                             (last_name, first_name, age_number, user_id))
        else:
            print(f"Adding new user {user_id} to the database.")
            await db.execute("INSERT INTO users (user_id, last_name, first_name, age_number) VALUES (?, ?, ?, ?)",
                             (user_id, last_name, first_name, age_number))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if user:
                print(f"User {user_id} found: {user}")
            else:
                print(f"User {user_id} not found.")
            return user

# Middleware для проверки зарегистрированности пользователя
class RegistrationMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[Any], Awaitable[Any]], event: Message | CallbackQuery, data: dict):
        user_id = event.from_user.id

        # Пропускаем команду /start без проверки регистрации
        if isinstance(event, Message) and event.text == "/start":
            return await handler(event, data)

        # Проверка состояния пользователя
        fsm_context = data.get('state', None)
        if fsm_context:
            state = await fsm_context.get_state()
            if state in [Form.name.state, Form.age.state]:
                # Если пользователь в процессе регистрации, пропускаем Middleware
                return await handler(event, data)

        # Проверка регистрации пользователя в базе данных
        async with aiosqlite.connect("users.db") as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user = await cursor.fetchone()

        if not user:  # Если пользователь не найден в базе данных
            if isinstance(event, Message):
                await event.answer("Вы не зарегистрированы! Пожалуйста, начните с команды /start для регистрации.")
            elif isinstance(event, CallbackQuery):
                await event.message.answer("Вы не зарегистрированы! Пожалуйста, начните с команды /start для регистрации.")
            return  # Прерываем обработку события
        return await handler(event, data)


# Регистрируем Middleware в диспетчере
dp.message.middleware(RegistrationMiddleware())
dp.callback_query.middleware(RegistrationMiddleware())

"""
@dp.message(CommandStart(), State(None))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if user:  # Если пользователь найден в базе, то он уже зарегистрирован
        await message.answer(f'Привет, {user[1]} {user[2]}! Ваш id={user_id}')
    else:  # Если пользователь не найден, то начинаем процесс регистрации
        await message.answer(f'Привет, {message.from_user.last_name} {message.from_user.first_name}! Ваш id={message.from_user.id}\nВведите Ваше ФИО:')
        await state.update_data(lastfirstname=f'{message.from_user.last_name} {message.from_user.first_name}')
        await state.set_state(Form.name)
"""
def check_name(name: str):
    return len(name.split()) == 3

def check_age(age: str):
    return age.isdigit()

async def get_all_users():
    """Получение списка всех пользователей из базы данных."""
    async with aiosqlite.connect("users.db") as db:
        async with db.execute("SELECT * FROM users") as cursor:
            users = await cursor.fetchall()
            return users

@dp.message(F.text, Form.name)
async def inputfio(message: Message, state: FSMContext):
    if not check_name(message.text):
        await message.answer(f'ФИО введено некорректно. Повторите ввод')
        return
    await message.answer(f'ФИО принято! Теперь введите ваш возраст цифрами:')
    await state.update_data(name=message.text)
    await state.set_state(Form.age)

@dp.message(F.text, Form.age)
async def input_age(message: Message, state: FSMContext):
    if not check_age(message.text):
        await message.answer(f'Возраст введен некорректно. Повторите ввод (только число)')
        return
    data = await state.get_data()
    await add_user_to_db(message.from_user.id, data['name'], message.from_user.first_name, message.text)
    await message.answer(f'Данные сохранены! Ваши данные: \nФИО - {data["name"]} \nвозраст - {message.text} \nваш id = {message.from_user.id}')
    await message.answer(f'✅ Отлично, регистрация завершена! Теперь вы можете начать путешествие к осознанности. \n✨ Нажимайте на кнопку "Меню", чтобы увидеть все доступные возможности: медитации, дыхательные упражнения, дневник и многое другое.')
    await state.clear()  # Обязательно очищаем состояние

'''
# Команда /start для приветствия и ввода данных
@dp.message(CommandStart(), State(None))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start. Запрашивает у пользователя ФИО."""
    await message.answer(f'✨ Добро пожаловать! \nЭтот бот поможет вам развивать осознанность и улучшать качество жизни. Вы сможете медитировать, записывать мысли, получать советы и напоминания для осознанных пауз 🌿 \nДавайте начнем! Для этого нужно сначала пройти регистрацию.')
    await message.answer(f'Итак, {message.from_user.first_name}! Введите ваше ФИО:')
    await state.set_state(Form.name)  # Переход к состоянию ввода ФИО
'''

"""Обработчик команды /start. Запрашивает у пользователя ФИО."""
@dp.message(CommandStart(), State(None))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if user:  # Если пользователь найден в базе, то он уже зарегистрирован
        await message.answer(f"С возвращением, {message.from_user.first_name}! Вы уже зарегистрированы.\n\nРады тебя видеть снова! Мы тут, как и раньше, готовы поддержать тебя на пути осознанности. Иногда важно просто остановиться, вдохнуть и вернуться к себе. Давай снова начнем с чего-то полезного и настроим день на гармонию и вдохновение! ✨")
        await message.answer("Выберите действия, например, /menu1 или /menu2 для начала работы с ботом.")
    else:  # Если пользователь не найден, то начинаем процесс регистрации
        await message.answer(f'✨ Добро пожаловать!\nЭтот бот поможет вам развивать осознанность и улучшать качество жизни. Вы сможете медитировать, записывать свои мысли, получать полезные советы и напоминания для осознанных пауз, что способствует внутреннему гармонии и личному росту 🌿\nДавайте начнем!\nДля этого нужно пройти регистрацию и настроить бота под свои цели.\n\nКогда вы будете готовы, просто выберите одну из опций:\n\n/start — запустите бота и начните свой путь к более осознанной жизни. С этим шагом вы сможете получить доступ ко всем функциям бота.\n/menu1 — откроется список полезных функций, которые помогут в развитии осознанности. Здесь вы найдете инструменты для изучения различных техник медитации, получения вдохновляющих советов и мотивации для поддержания дисциплины.\n/menu2 — откроется ваш личный дневник, в котором вы сможете записывать свой прогресс. Этот дневник поможет отслеживать улучшения, ставить цели и отслеживать свой путь. Помните, что каждый шаг, пусть и маленький, важен! 🌱\nГотовы начать? Просто выберите нужную команду, и давайте двигаться вперед!')
        await message.answer(f'Итак, {message.from_user.first_name}! Для начала зарегистрируемся.\nВведите ваше ФИО:')
        await state.set_state(Form.name)  # Переход к состоянию ввода ФИО

# Обработчик команды для отправки обычной клавиатуры
@dp.message(Command("menu1"), State(None))
async def cmd_menu1(message: Message):
    """Обработчик команды для отправки обычной клавиатуры."""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🧘‍ Медитации"))
    builder.add(KeyboardButton(text="🌟 Мотивирующие цитаты"))
    builder.add(KeyboardButton(text="🌬️ Дыхательные упражнения"))
    builder.add(KeyboardButton(text="🤳 Поговори со мной"))
    builder.add(KeyboardButton(text="💭 Оставить отзыв"))
    builder.add(KeyboardButton(text="ℹ️ О боте"))
    keyboard = builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Главное меню. Выберите действие:", reply_markup=keyboard)

# Командное меню с inline клавиатурой
@dp.message(Command("menu2"))
async def cmd_menu2(message: Message):
    """Обработчик команды для отправки inline клавиатуры."""
    builder = InlineKeyboardBuilder()
    builder.button(text='✍️ Добавить новую запись в дневник', callback_data='content')
    builder.button(text='📓 Просмотр записей', callback_data='all')
    builder.button(text="🌝 Как вести дневник?", web_app=WebAppInfo(
        url="https://psyhologl.store/kak-vesti-dnevnik-osoznannosti-dlya-uluchsheniya-zhizni/"))
    builder.button(text='🍎 Записать цель', callback_data='goal')
    builder.button(text="☄️ Напоминание о цели", callback_data='notion')
    builder.adjust(1, 2, 1, 1)
    await message.answer('Выберите действие:', reply_markup=builder.as_markup())


# КОМАНДЫ С ОБЫЧНОЙ КЛАВИАТУРЫ

# КНОПКА 1 "🧘‍ Медитации"
@dp.message(F.text == "🧘‍ Медитации")
async def meditation_menu(message: Message):
    """Отправка клавиатуры с выбором медитации."""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Короткая (5 мин)"))
    builder.add(KeyboardButton(text="Средняя (10 мин)"))
    builder.add(KeyboardButton(text="Длинная (20 мин)"))
    builder.add(KeyboardButton(text="🔙 Вернуться в меню"))
    keyboard = builder.as_markup(resize_keyboard=True)

    await message.answer("🧘 Выберите медитацию:", reply_markup=keyboard)

# Ответ на выбор медитации
@dp.message(F.text == "Короткая (5 мин)")
async def short_meditation(message: Message):
    """Обработка выбора короткой медитации."""
    await message.answer("Вы выбрали короткую медитацию (5 минут). Давайте начнём медитацию...\n\nКороткая медитация (5 минут) \nЦель: Быстрое расслабление и фокусировка на дыхании для снятия стресса или напряжения. \n\nШаги:\n1. Сесть удобно. Примите удобное положение — можно сидеть с прямой спиной, расслабив плечи, или лечь.\n2. Закрыть глаза. Сделайте несколько глубоких вдохов и выдохов, чтобы расслабиться. \n3. Фокусировка на дыхании. Сосредоточьтесь на своем дыхании. Вдыхайте глубоко через нос, ощущая, как воздух заполняет живот, и выдыхайте через рот, освобождая тело от напряжения.\n4. Осознание каждого вдоха. Вдохните, сосчитайте до 4, задержите дыхание на 4 секунды, затем выдохните на 4 счета. Это поможет замедлить дыхание и успокоить ум. \n5. Повторите цикл. Повторите цикл несколько раз, сосредоточившись только на дыхании.\n6. Заключение. Постепенно вернитесь в осознание окружающего мира. Откройте глаза, сделайте пару глубоких вдохов, и почувствуйте, как ваше тело расслабилось.\n\nПодсказка: Это отличный способ быстро вернуть себе спокойствие и фокус.")

@dp.message(F.text == "Средняя (10 мин)")
async def medium_meditation(message: Message):
    """Обработка выбора средней медитации."""
    await message.answer("Вы выбрали среднюю медитацию (10 минут). Давайте начнём медитацию...\n\nСредняя медитация (10 минут)\nЦель: Более глубокое расслабление и соединение с внутренним состоянием.\n\nШаги:\n1. Найдите спокойное место. Убедитесь, что вас не будут беспокоить. Сядьте или лягте в комфортном положении.\n2. Закройте глаза и расслабьтесь. Сделайте несколько медленных глубоких вдохов, чтобы расслабить тело и освободиться от напряжения.\n3. Сосредоточение на дыхании. Начните следить за дыханием, как в короткой медитации, но теперь позвольте себе быть более внимательным к каждому вдоху и выдоху. Постепенно замедляйте дыхание.\n4. Медитация осознанности. Представьте себе красивое место — лес, пляж, горы — и визуализируйте, как вы находитесь там, ощущая свежий воздух, звуки природы. Сосредоточьтесь на этом ощущении.\n5. Принятие мыслей. Если появляются мысли, не боритесь с ними. Просто наблюдайте за ними, как за облаками, которые проходят мимо.\n6. Тело и расслабление. Пройдитесь вниманием по всему телу, начиная с головы и двигаясь вниз к ногам. Замечайте, где ощущаете напряжение, и постарайтесь расслабить эти участки.\n7. Заключение. Закончите медитацию тем, что возвращаетесь в осознание окружающего мира. Сделайте несколько глубоких вдохов и выдохов, откройте глаза и постарайтесь сохранить ощущение внутреннего спокойствия.\n\nПодсказка: Эта медитация подходит для тех, кто хочет больше времени для расслабления и восстановления.")

@dp.message(F.text == "Длинная (20 мин)")
async def long_meditation(message: Message):
    """Обработка выбора длинной медитации."""
    await message.answer('Вы выбрали длинную медитацию (20 минут). Давайте начнём медитацию...\n\nДлинная медитация (20 минут)\nЦель: Глубокое расслабление и осознанное внимание к своему состоянию для достижения гармонии и баланса.\n\nШаги:\n1. Создайте пространство для медитации. Найдите тихое место, где вас не побеспокоят в течение 20 минут. Сядьте в удобное положение или лягте.\n2. Закройте глаза и расслабьтесь. Сделайте несколько глубоких вдохов, позволяя своему телу постепенно расслабляться.\n3. Осознанное дыхание. Сосредоточьтесь на дыхании, как в короткой медитации. Постепенно сделайте дыхание более глубоким и размеренным.\n4. Дыхание с осознанием. На вдохе думайте "я вдыхаю", на выдохе — "я выдыхаю". Следите за тем, как воздух движется в вашем теле.\n5. Медитация с намерением. Поставьте перед собой намерение на медитацию — это может быть внутренний вопрос или намерение: "Что я хочу понять?" или "Как я могу быть более спокойным?". Дайте себе время, чтобы это намерение сформировалось.\n6. Расслабление каждой части тела. Начните с головы и постепенно двигайтесь вниз. Когда вы осознаете каждый участок своего тела, мысленно посылайте туда расслабление.\n7. Визуализация. Представьте, что вы находитесь в месте покоя и спокойствия — например, в туманном лесу, на пляже или в горах. Вдохните атмосферу этого места и позвольте себе погрузиться в него.\n8. Осознание мыслей. Если ваши мысли отвлекают вас, примите их без осуждения. Скажите себе: "Я наблюдаю эти мысли, но не позволяю им отвлекать меня от настоящего момента".\n9. Принятие текущего состояния. Признайте и примите все свои эмоции, ощущения, мысли, не пытаясь их изменить. Просто наблюдайте.\n10. Заключение. Плавно заканчивайте медитацию, возвращая внимание к дыханию. Медленно откройте глаза, потянитесь и вернитесь в осознанное состояние, сохраняя чувство покоя.\n\nПодсказка: Эта медитация идеально подходит для глубокого расслабления, снятия стресса и обретения внутренней гармонии.')

# Ответ на команду "Вернуться в меню"
@dp.message(F.text == "🔙 Вернуться в меню")
async def return_to_menu(message: Message):
    """Возвращаем пользователя в основное меню."""
    await cmd_menu1(message)
# КОНЕЦ КНОПКИ 1 "🧘‍ Медитации"


# КНОПКА 2 "🌟 Мотивирующие цитаты"
# Словарь для хранения состояния подписки
user_subscriptions = {}
scheduler = AsyncIOScheduler()

# Клавиатура для выбора мотивационных цитат
category_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Успех")],
        [KeyboardButton(text="Мотивация")],
        [KeyboardButton(text="Саморазвитие")],
        [KeyboardButton(text="Позитивное мышление")],
        [KeyboardButton(text="❌ Отменить подписку")],
        [KeyboardButton(text="🔙 Вернуться в меню")]
    ],
    resize_keyboard=True
)

# Клавиатура для выбора периодичности
periodicity_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="10 секунд")],
        [KeyboardButton(text="30 секунд")],
        [KeyboardButton(text="1 минута")],
        [KeyboardButton(text="1 раз в день")],
        [KeyboardButton(text="❌ Отменить подписку")],
        [KeyboardButton(text="🔙 Вернуться в меню")]
    ],
    resize_keyboard=True
)

# Функция для отправки мотивационных цитат пользователю
async def send_motivation(user_id: int, category: str):
    """Функция для отправки мотивационной цитаты пользователю."""
    motivation_text = generate_motivation(category)
    await bot.send_message(user_id, motivation_text)

# Функция для запуска планировщика (с проверкой)
def start_scheduler():
    """Запускаем планировщик только если он еще не запущен."""
    if not scheduler.running:
        scheduler.start()

# Функция для отправки цитат с периодичностью (если нужно, можно использовать asyncio.sleep())
async def start_sending_motivation(user_id, category, interval):
    """Отправка мотивационных цитат через заданный интервал."""
    while True:
        # Получаем мотивационную цитату
        motivation = generate_motivation(category)
        # Отправляем цитату пользователю
        await bot.send_message(user_id, motivation)

        # Ждем заданный интервал, прежде чем отправить следующую цитату
        await asyncio.sleep(interval)

# Обработчик кнопки для начала подписки
@dp.message(lambda message: message.text == "🌟 Мотивирующие цитаты")
async def handle_motivation_button(message: types.Message):
    # Предложим пользователю выбрать категорию мотивации
    await message.answer("Выберите категорию для мотивационных цитат:", reply_markup=category_keyboard)

# Обработчик выбора категории
@dp.message(lambda message: message.text in ["Успех", "Мотивация", "Саморазвитие", "Позитивное мышление"])
async def handle_category_selection(message: types.Message):
    # Сохраняем выбранную категорию
    selected_category = message.text
    await message.answer(
        f"Вы выбрали категорию: {selected_category}. Теперь выберите, как часто вы хотите получать цитаты.",
        reply_markup=periodicity_keyboard)
    # Сохраняем категорию для дальнейшего использования
    user_subscriptions[message.from_user.id] = {"category": selected_category}

# Обработчик выбора периодичности
@dp.message(lambda message: message.text in ["10 секунд", "30 секунд", "1 минута", "1 раз в день"])
async def handle_periodicity_selection(message: types.Message):
    # Карта периодичности
    frequency_map = {
        "10 секунд": 10,  # 10 секунд
        "30 секунд": 30,  # 30 секунд
        "1 минута": 60,  # 1 минута
        "1 раз в день": 86400  # 1 раз в день (секунды в сутки)
    }
    # Извлекаем периодичность
    selected_period = frequency_map[message.text]
    # Извлекаем категорию из словаря подписок
    if message.from_user.id not in user_subscriptions:
        await message.answer("Сначала выберите категорию.")
        return
    category = user_subscriptions[message.from_user.id]["category"]
    # Сохраняем частоту в словарь, чтобы потом использовать (если потребуется)
    user_subscriptions[message.from_user.id]["periodicity"] = selected_period
    # Информируем пользователя
    await message.answer(
        f"Вы выбрали частоту: {message.text}. Цитаты на тему '{category}' будут отправляться с выбранной периодичностью.")
    # Запускаем задачу по отправке цитат с нужной периодичностью
    job_id = f"motivation_{message.from_user.id}"
    scheduler.add_job(
        send_motivation,
        IntervalTrigger(seconds=selected_period),
        args=[message.from_user.id, category],  # Передаем ID пользователя и выбранную категорию
        id=job_id,
        replace_existing=True
    )
    # Проверяем и запускаем планировщик только если он еще не запущен
    start_scheduler()

@dp.message(lambda message: message.text == "🔙 Вернуться в меню")
async def return_to_menu(message: Message):
    """Возвращаем пользователя в основное меню."""
    await cmd_menu1(message)

# Для кнопки отмены подписки
@dp.message(lambda message: message.text == "❌ Отменить подписку")
async def cancel_subscription(message: Message):
    """Отмена подписки на цитаты."""
    if message.from_user.id in user_subscriptions:
        job_id = f"motivation_{message.from_user.id}"
        job = scheduler.get_job(job_id)
        if job:
            job.remove()  # Удаляем задачу
        del user_subscriptions[message.from_user.id]
        await message.answer("Подписка на мотивационные цитаты отменена.")
        await cmd_menu1(message)
    else:
        await message.answer("У вас нет активной подписки.")
        await cmd_menu1(message)
# КОНЕЦ КНОПКИ 2 "🌟 Мотивирующие цитаты"


# КНОПКА 3 "🌬️ Дыхательные упражнения"
@dp.message(F.text == "🌬️ Дыхательные упражнения")
async def meditation_menu(message: Message):
    """Отправка клавиатуры с выбором медитации."""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Расслабляющее дыхание (3 мин)"))
    builder.add(KeyboardButton(text="Энергетическое дыхание (5 мин)"))
    builder.add(KeyboardButton(text="Глубокая релаксация (7 мин)"))
    builder.add(KeyboardButton(text="🔙 Вернуться в меню"))
    keyboard = builder.as_markup(resize_keyboard=True)
    await message.answer("🌬️ Выберите упражнение для дыхания и релаксации:", reply_markup=keyboard)

# Ответ на выбор медитации
@dp.message(F.text == "Расслабляющее дыхание (3 мин)")
async def short_meditation(message: Message):
    await message.answer("🌬️ Расслабляющее дыхание (3 минуты)\n\nПростое, но эффективное упражнение для снятия напряжения и расслабления всего тела.\n\n1. Найдите удобное место, где вас никто не будет отвлекать. Сядьте или лягте в спокойной позе.\n2. Закройте глаза и сосредоточьтесь на своем дыхании.\n3. Сделайте глубокий вдох через нос на 4 счета, представьте, как воздух наполняет ваши легкие.\n4. Задержите дыхание на 2 счета.\n5. Медленно выдохните через рот на 6 счетов, представляя, как ваше тело расслабляется с каждым выдохом.\n6. Повторяйте цикл дыхания (вдох 4, задержка 2, выдох 6) в течение 3 минут.\n\n7.Совет: если чувствуете, что ваше внимание отвлекается, мягко возвращайте его к дыханию, без осуждения.")

@dp.message(F.text == "Энергетическое дыхание (5 мин)")
async def medium_meditation(message: Message):
    await message.answer("🌬️ Энергетическое дыхание (5 минут)\n\nУпражнение, которое помогает зарядиться энергией и улучшить концентрацию.\n\n1. Сядьте прямо, спина прямая, плечи расслаблены.\n2. Глубоко вдохните через нос на 3 счета.\n3. Задержите дыхание на 1 счет.\n4. Резко выдохните через рот на 4 счета, представляя, как все усталость и напряжение покидают ваше тело.\n5. Повторяйте это дыхание в течение 5 минут.\n\nСовет: почувствуйте, как с каждым выдохом вы освобождаетесь от накопленного стресса и напряжения.")

@dp.message(F.text == "Глубокая релаксация (7 мин)")
async def long_meditation(message: Message):
    await message.answer("🌬️ Глубокая релаксация (7 минут)\n\nДлительное дыхательное упражнение для полной релаксации и гармонизации внутреннего состояния.\n\n1. Лягте на спину, руки расслабленно положите вдоль тела.\n2. Закройте глаза и начните дышать глубоко и спокойно.\n3. Вдохните через нос на 4 счета, представляя, как воздух наполняет каждый уголок вашего тела.\n4. Задержите дыхание на 4 счета.\n5. Медленно выдохните через рот на 6 счетов, представляя, как с каждым выдохом ваше тело становится все более расслабленным.\n6. Продолжайте цикл дыхания в течение 7 минут. Постепенно углубляйте дыхание и ощущение расслабления.\n\nСовет: во время упражнения сосредоточьтесь на своем теле и ощущениях. Почувствуйте, как каждая часть тела расслабляется.")

# Ответ на команду "Вернуться в меню"
@dp.message(F.text == "🔙 Вернуться в меню")
async def return_to_menu(message: Message):
    await cmd_menu1(message)
# КОНЕЦ КНОПКИ 3 "🌬️ Дыхательные упражнения"


# КНОПКА 5 "ℹ️ О боте"
@dp.message(F.text == "ℹ️ О боте")
async def question(message: Message):
    """Обработка вопроса пользователя."""
    await message.answer("ℹ️ О боте:\nЭтот бот создан, чтобы помочь вам развивать осознанность и улучшать качество жизни. С его помощью вы сможете:\n\nМедитировать и заниматься дыхательными практиками для успокоения ума и восстановления внутренней гармонии 🧘‍♀️\nПолучать мотивирующие цитаты, которые будут вдохновлять вас на личностный рост и позитивные изменения ✨\nВести личный дневник, где вы сможете отслеживать свой прогресс, записывать мысли и цели 📝\nСоздано с любовью и заботой о вашем внутреннем мире 💌\n\n🔧 Основные команды:\n\n/start — начните свое путешествие с ботом. Запустите его и настройте под свои цели.\n/menu1 — откроются различные функции, которые помогут вам развивать осознанность. Здесь вы найдете медитации, дыхательные практики, а также советы, которые помогут сохранить мотивацию и удерживать фокус на процессе.\n/menu2 — откроется ваш персональный дневник, где вы сможете записывать свой прогресс, ставить цели и фиксировать важные моменты на пути к гармонии.")
# КОНЕЦ КНОПКИ 5 "ℹ️ О боте"

# ОТЗЫВ
# Путь к файлу для хранения отзывов
FEEDBACK_FILE = 'feedbacks.json'
class UserStates(StatesGroup):
    leaving_feedback = State()  # Состояние для оставления отзыва
# Функция для добавления отзыва в JSON
def add_to_json(file_path, data):
    """Добавить отзыв в JSON файл"""
    try:
        # Проверка, существует ли файл
        if os.path.exists(file_path):
            # Если файл существует, загружаем старые отзывы
            with open(file_path, 'r', encoding='utf-8') as file:
                feedbacks = json.load(file)
        else:
            # Если файла нет, создаем новый список для отзывов
            feedbacks = []
        # Добавляем новый отзыв
        feedbacks.append(data)
        # Записываем обновленные данные обратно в файл
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(feedbacks, file, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Error while saving feedback to JSON: {e}")
        raise

# Обработчик кнопки "Оставить отзыв"
@dp.message(F.text == "💭 Оставить отзыв")
async def feedback_prompt(message: types.Message, state: FSMContext):
    await state.set_state(UserStates.leaving_feedback)
    await message.answer(
        "Пожалуйста, напишите ваш отзыв или предложение:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="Отмена")]],
            resize_keyboard=True
        )
    )

# Обработчик для получения отзыва
@dp.message(UserStates.leaving_feedback)
async def process_feedback(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Отправка отзыва отменена.")
        await cmd_menu1(message)
        return

    try:
        feedback = message.text
        # Формируем данные для сохранения
        data = {"user_id": str(message.from_user.id), "feedback": feedback}

        # Добавляем отзыв в JSON
        add_to_json(FEEDBACK_FILE, data)

        await message.answer(
            "Спасибо большое за ваш отзыв! 🫶\n"
            "Мы ценим ваше мнение и постараемся стать лучше!",
        )
        # Возвращаем пользователя в главное меню
        await cmd_menu1(message)

    except Exception as e:
        logging.error(f"Error saving feedback: {e}")
        await message.answer(
            "Произошла ошибка при сохранении отзыва. Пожалуйста, попробуйте позже.",
            await cmd_menu1(message)
        )
    finally:
        await state.clear()

# КОНЕЦ ОТЗЫВА


# ДНЕВНИК + ЦЕЛИ -- МЕНЮ
# Путь к файлам (пользовательский ID будет использоваться для создания уникальных файлов)
user_diary_file = 'diary_{}.txt'
user_goals_file = 'goals_{}.json'

# ДНЕВНИК
# Функция для создания новой записи в дневник
async def create_diary_entry(user_id: int, date: str, entry: str, micro_output: str):
    file_name = user_diary_file.format(user_id)
    entry_data = f"{date}\n{entry}\nМини-вывод: {micro_output}\n\n"
    with open(file_name, 'a', encoding='utf-8') as file:
        file.write(entry_data)

def is_valid_date(date: str) -> bool:
    """
    Функция для проверки корректности даты (YYYY-MM-DD) с учетом существующих дней в месяце.
    """
    try:
        # Преобразуем строку в объект datetime, если дата существует
        datetime.strptime(date, '%Y-%m-%d')
        return True
    except ValueError:
        # Если возникает ошибка, значит дата некорректна
        return False

class Form1(StatesGroup):
    waiting_for_date = State()  # Ожидание ввода даты
    waiting_for_entry = State()  # Ожидание записи
    waiting_for_micro_output = State()  # Ожидание микро-вывода

# Обработчик для кнопки "Добавить новую запись"
@dp.callback_query(F.data == 'content')
async def send_content(call: CallbackQuery, state: FSMContext):
    # Начинаем разговор с пользователем
    await call.message.answer("Ведя свой дневник, ты можешь записывать дату, описание ситуаций, свои мысли, чувства и эмоции, которые возникли в этот момент. Это поможет тебе лучше понять себя и то, что происходит вокруг. В конце каждого записи оставляй мини-вывод — подытожив, что ты почувствовал или понял. Конечно, если выводов нет, можно просто поставить прочерк. Но помни, что анализ этих записей в будущем будет полезен для твоего личного роста и осознанности. Мы стремимся к лучшему пониманию себя, и даже самые маленькие выводы могут стать ключом к важным инсайтам 🌱\n\n📆 Введите дату записи (например, 2025-01-20):")
    await state.set_state(Form1.waiting_for_date)

# Обработчик для ввода даты записи
@dp.message(State("waiting_for_date"))
async def process_date(message: Message, state: FSMContext):
    date = message.text

    # Проверка на корректность даты
    if is_valid_date(date):
        await state.update_data(date=date)
        # Переходим к вводу записи
        await message.answer("📝 Введите вашу запись для дневника:")
        await state.set_state(Form1.waiting_for_entry)
    else:
        # Если дата некорректная, запрашиваем ввод снова
        await message.answer(
            "❌ Некорректный формат даты. Пожалуйста, введите дату в формате 'YYYY-MM-DD', например, '2025-01-20'. Попробуйте снова:"
        )

# Обработчик для ввода самой записи
@dp.message(State("waiting_for_entry"))
async def process_entry(message: Message, state: FSMContext):
    entry = message.text
    data = await state.get_data()
    date = data.get("date")
    await state.update_data(entry=entry)
    # Переходим к вводу микро-вывода
    await message.answer("🔻 Введите ваш мини-вывод для записи:")
    await state.set_state(Form1.waiting_for_micro_output)

# Обработчик для ввода мини-вывода
@dp.message(State("waiting_for_micro_output"))
async def process_micro_output(message: Message, state: FSMContext):
    micro_output = message.text
    data = await state.get_data()
    date = data.get("date")
    entry = data.get("entry")

    # Сохраняем запись в дневник
    await create_diary_entry(message.from_user.id, date, entry, micro_output)
    await message.answer("Ваша запись успешно добавлена! 💌")
    await state.clear()

# Обработчик для кнопки "Просмотр предыдущих записей"
@dp.callback_query(F.data == 'all')
async def view_previous_entries(call: CallbackQuery):
    user_id = call.from_user.id
    file_name = user_diary_file.format(user_id)

    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as file:
            content = file.read()
            if content:
                await call.message.answer(content)
            else:
                await call.message.answer("У вас нет записей в дневнике.")
    else:
        await call.message.answer("У вас еще нет записей в дневнике.")

dp.message.register(process_date, StateFilter(Form1.waiting_for_date))
dp.message.register(process_entry, StateFilter(Form1.waiting_for_entry))
dp.message.register(process_micro_output, StateFilter(Form1.waiting_for_micro_output))
# КОНЕЦ ДНЕВНИКА

# ЦЕЛИ
class Form2(StatesGroup):
    waiting_for_date = State()
    waiting_for_goal = State()
    waiting_for_goal_description = State()
    waiting_for_end_date = State()

# Функция для записи цели
async def create_goal(user_id: int, start_date: str, goal: str, description: str, end_date: str):
    file_name = user_goals_file.format(user_id)
    goal_data = {
        'start_date': start_date,
        'name': goal,
        'description': description,
        'end_date': end_date,
        'status': 'не выполнено'  # поле для отслеживания статуса цели
    }
    if os.path.exists(file_name):
        with open(file_name, 'r+', encoding='utf-8') as file:
            goals = json.load(file)
            goals.append(goal_data)
            file.seek(0)
            json.dump(goals, file, ensure_ascii=False, indent=4)
    else:
        with open(file_name, 'w', encoding='utf-8') as file:
            json.dump([goal_data], file, ensure_ascii=False, indent=4)

# Обработчик для кнопки "Записать цель"
@dp.callback_query(F.data == 'goal')
async def add_goal(call: CallbackQuery, state: FSMContext):
    """Запросить информацию для добавления цели"""
    await call.message.answer("Цели фиксируются в формате: дата начала, название цели, описание цели и дата завершения (или бессрочно). Такой подход помогает ясно видеть свои намерения и шаги на пути к ним. Ставя перед собой цели, ты не только становишься более осознанным, но и начинаешь отслеживать свой прогресс. Это важная часть взросления — учиться планировать свою жизнь, ставить амбициозные задачи и уверенно двигаться к ним. И пусть каждая цель, даже самая маленькая, будет твоим шагом к небу! 🌟\n\n🗓 Введите дату начала цели (например, 2025-01-20):")
    await state.set_state(Form2.waiting_for_date)

# Обработчик для ввода даты начала цели
@dp.message(State("waiting_for_goal_start_date"))
async def process_goal_start_date(message: Message, state: FSMContext):
    start_date = message.text

    # Проверка на корректность даты
    if is_valid_date(start_date):
        await state.update_data(start_date=start_date)
        await message.answer("Дата начала цели установлена.")

        # Переходим к вводу цели
        await message.answer("🎯 Введите название вашей цели:")
        await state.set_state(Form2.waiting_for_goal)
    else:
        # Если дата некорректная, запрашиваем ввод снова
        await message.answer(
            "❌ Некорректный формат даты. Пожалуйста, введите дату в формате 'YYYY-MM-DD', например, '2025-01-20'. Попробуйте снова:"
        )

# Обработчик для ввода цели
@dp.message(State("waiting_for_goal"))
async def process_goal(message: Message, state: FSMContext):
    goal = message.text
    await state.update_data(name=goal)

    # Переходим к вводу описания цели
    await message.answer("📖 Введите описание вашей цели:")
    await state.set_state(Form2.waiting_for_goal_description)

# Обработчик для ввода описания цели
@dp.message(State("waiting_for_goal_description"))
async def process_goal_description(message: Message, state: FSMContext):
    description = message.text
    await state.update_data(description=description)

    # Переходим к вводу даты завершения
    await message.answer("\n📆 Введите дату завершения цели (например, 2025-12-31), или напишите 'бессрочно':")
    await state.set_state(Form2.waiting_for_end_date)

# Обработчик для ввода даты завершения цели
@dp.message(State("waiting_for_goal_end_date"))
async def process_goal_end_date(message: Message, state: FSMContext):
    end_date = message.text
    # Проверка на "бессрочно"
    if end_date.lower() == "бессрочно":
        await state.update_data(end_date=end_date)
        await message.answer("Цель будет бессрочной.")
        end_date = 'Бессрочно'
    # Проверка на правильность формата даты
    elif is_valid_date(end_date):
        await state.update_data(end_date=end_date)
        await message.answer(f"Дата завершения цели установлена на {end_date}.")
    else:
        await message.answer(
            "❌ Некорректный формат даты. Пожалуйста, введите дату в формате 'YYYY-MM-DD' или напишите 'бессрочно'.")
        return

    # Получаем все данные, собранные ранее
    data = await state.get_data()
    start_date = data.get("start_date")
    goal = data.get("name")
    description = data.get("description")

    # Сохраняем цель
    await create_goal(message.from_user.id, start_date, goal, description, end_date)
    await message.answer("Ваша цель успешно записана! 💌")
    await state.clear()

dp.message.register(process_goal_start_date, StateFilter(Form2.waiting_for_date))
dp.message.register(process_goal, StateFilter(Form2.waiting_for_goal))
dp.message.register(process_goal_description, StateFilter(Form2.waiting_for_goal_description))
dp.message.register(process_goal_end_date, StateFilter(Form2.waiting_for_end_date))


# Загрузить цели из файла
def load_goals_from_file(user_id):
    """Загрузка целей пользователя из файла"""
    file_name = f'goals_{user_id}.json'  # Имя файла с целями
    if os.path.exists(file_name):
        with open(file_name, 'r', encoding='utf-8') as file:
            try:
                goals = json.load(file)
                # Проверка, что каждый элемент списка целей имеет ключ 'name'
                for goal in goals:
                    if 'name' not in goal:
                        raise ValueError(f"Цель {goal} не содержит ключа 'name'.")
                return goals
            except json.JSONDecodeError:
                print(f"Ошибка при чтении JSON из файла {file_name}.")
            except ValueError as e:
                print(e)
    return []  # Если файл не существует или произошла ошибка, возвращаем пустой список

# Стейты FSM
class GoalStates(StatesGroup):
    waiting_for_goal = State()  # Ожидание выбора цели
    waiting_for_time = State()  # Ожидание времени напоминания

# Обработчик кнопки "☄️ Напоминание о цели"
@dp.message(lambda message: message.text == "☄️ Напоминание о цели")
async def set_reminder_prompt(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    goals = load_goals_from_file(user_id)
    if not goals:
        await message.answer("У вас пока нет целей для напоминания.", reply_markup=get_main_keyboard())
        return
    # Создаем клавиатуру с целями
    builder = ReplyKeyboardBuilder()
    for goal in goals:
        goal_name = goal.get("name") or "Без названия"
        builder.add(KeyboardButton(text=goal_name))
    builder.add(KeyboardButton(text="Отмена"))
    keyboard = builder.as_markup(resize_keyboard=True)
    await message.answer("Выберите цель для установки напоминания:", reply_markup=keyboard)
    await state.set_state(GoalStates.waiting_for_goal)


# Обработчик времени напоминания
@dp.message(StateFilter(GoalStates.waiting_for_time))
async def process_reminder_time(message: types.Message, state: FSMContext):
    try:
        # Получаем данные из FSM
        data = await state.get_data()
        goal = data.get("goal")
        user_id = str(message.from_user.id)

        # Проверяем ввод пользователя
        if message.text.isdigit():
            # Установка времени в минутах
            n = int(message.text)
            if n <= 0 or n > 100:
                await message.answer("Введите число минут от 1 до 100.")
                return
            reminder_time = datetime.now() + timedelta(minutes=n)
        else:
            # Установка конкретной даты и времени
            reminder_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
            if reminder_time <= datetime.now():
                await message.answer("Вы не можете установить напоминание на прошедшее время.")
                return

        # Планируем напоминание
        await schedule_reminder(user_id, goal, reminder_time)

        # Сохраняем напоминание
        add_reminder_to_file(user_id, goal, reminder_time)
        await message.answer(
            f"Напоминание для цели \"{goal['name']}\" установлено на {reminder_time.strftime('%Y-%m-%d %H:%M')} ⏰",
            reply_markup=get_main_keyboard()
        )
    except ValueError:
        await message.answer("Пожалуйста, введите корректное время в формате '10' или '2025-01-21 12:30'.")
        return
    finally:
        await state.clear()


# Асинхронный метод для планирования напоминания
async def schedule_reminder(user_id, goal, reminder_time):
    delay = (reminder_time - datetime.now()).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)  # Ожидаем до времени напоминания
        await send_reminder(user_id, goal)


# Функция для отправки напоминания
async def send_reminder(user_id, goal):
    await bot.send_message(user_id, f"Напоминание: достигайте вашу цель '{goal['name']}'!")


# Обработчик кнопки "Напоминания о целях"
@dp.callback_query(lambda c: c.data == 'notion')
async def show_goals_for_reminders(call: CallbackQuery):
    user_id = call.from_user.id
    goals = load_goals_from_file(user_id)
    if not goals:
        await call.message.answer("У вас нет целей, добавьте цель через команду 'Записать цель'.")
        return
    # Создаем меню с целями
    builder = ReplyKeyboardBuilder()
    for goal in goals:
        goal_name = goal.get("name") or "Без названия"
        builder.add(KeyboardButton(text=goal_name))
    builder.add(KeyboardButton(text="🔙 Вернуться в меню"))
    keyboard = builder.as_markup(resize_keyboard=True)
    await call.message.answer("Выберите цель для установки напоминания:", reply_markup=keyboard)

# Обработчик для выбора цели (только когда в состоянии ожидания цели)
@dp.message(StateFilter(GoalStates.waiting_for_goal))
async def process_reminder_goal(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Установка напоминания отменена.", reply_markup=get_main_keyboard())
        return
    # Загружаем цели из файла и находим выбранную цель
    user_id = str(message.from_user.id)
    goals = load_goals_from_file(user_id)
    selected_goal = next((goal for goal in goals if goal.get("name") == message.text), None)
    if not selected_goal:
        await message.answer("Цель не найдена. Попробуйте снова.")
        return
    # Сохраняем выбранную цель
    await state.update_data(goal=selected_goal)
    await message.answer(
        "Вы хотите установить напоминание через определённое время (в минутах) или на конкретную дату и время?\n"
        "Напишите, например:\n"
        "1. '10' (через 10 минут)\n"
        "2. '2025-01-21 12:30' (на конкретную дату и время)"
    )
    await state.set_state(GoalStates.waiting_for_time)


# Функция для добавления напоминаний в файл
def add_reminder_to_file(user_id, selected_goal, reminder_time):
    file_name = f'reminders_{user_id}.json'
    reminder_data = {
        "goal_name": selected_goal["name"],  # Используем поле "name"
        "reminder_time": reminder_time.strftime("%Y-%m-%d %H:%M"),
    }
    if os.path.exists(file_name):
        with open(file_name, 'r+', encoding='utf-8') as file:
            reminders = json.load(file)
            reminders.append(reminder_data)
            file.seek(0)
            json.dump(reminders, file, ensure_ascii=False, indent=4)
    else:
        with open(file_name, 'w', encoding='utf-8') as file:
            json.dump([reminder_data], file, ensure_ascii=False, indent=4)
# КОНЕЦ ЦЕЛИ


# КНОПКА 4 "🤳 Поговори со мной"
# Создание глобального словаря или использование FSM
class ConversationStates(StatesGroup):
    chatting = State()

# КНОПКА 4 "🤳 Поговори со мной"
from aiogram.types import ReplyKeyboardRemove  # Для скрытия клавиатуры

@dp.message(lambda message: "🤳 Поговори со мной" in message.text)  # Фильтр по тексту кнопки
async def start_conversation(message: types.Message, state: FSMContext):
    """Инициализация диалога с GigaChat."""
    # Создание клавиатуры с кнопкой "Закончить разговор"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Закончить разговор")]],  # Кнопка для завершения диалога
        resize_keyboard=True
    )
    # Устанавливаем состояние "chatting"
    await state.set_state(ConversationStates.chatting)
    await message.answer("Привет! Я твой помощник и всегда рад поболтать) О чём ты хочешь поговорить?", reply_markup=keyboard)


@dp.message(lambda message: "Закончить разговор" in message.text)
async def end_conversation(message: types.Message, state: FSMContext):
    """Обработка завершения разговора."""
    # Завершаем состояние пользователя
    await state.clear()  # Очистка состояния FSM
    # Возвращаем пользователя в главное меню
    await message.answer(
        "Прощай! Надеюсь, тебе стало легче. Если захочешь поговорить снова, я всегда здесь. Возвращайся в главное меню.",
        reply_markup=ReplyKeyboardRemove()  # Скрытие клавиатуры
    )
    await cmd_menu1(message)  # Возврат в главное меню


# Обработка сообщений в рамках разговора
@dp.message(StateFilter(ConversationStates.chatting))
async def handle_chat_message(message: types.Message, state: FSMContext):
    """Обработка сообщений в режиме активного разговора."""
    # Отправляем сообщение в GigaChat и получаем ответ
    response_from_gigachat = send_to_gigachat(message.text)
    # Отправляем ответ пользователю
    await message.answer(response_from_gigachat)


# Обработка сообщений вне активного разговора
@dp.message(StateFilter(None))  # Срабатывает только если пользователь не находится ни в одном состоянии
async def handle_message_outside_conversation(message: types.Message):
    """Ответ на сообщения вне активного диалога."""
    # Сообщаем пользователю, что чат неактивен
    await message.answer(f"Уважаемый {message.from_user.first_name}, нельзя писать произвольный текст! Для начала разговора нажмите кнопку '🤳 Поговори со мной'.")
# КОНЕЦ КНОПКИ 4 "🤳 Поговори со мной"


# Обработчик произвольного текста
@dp.message()
async def handle_message(message: Message, state: FSMContext):
    """Ответ на произвольный текст от пользователя."""

    # Получаем данные из состояния
    user_data = await state.get_data()

    # Проверяем, завершён ли разговор
    if user_data.get("conversation_ended"):
        # Если разговор завершён, игнорируем произвольные сообщения
        await message.answer(f"Уважаемый {message.from_user.first_name}, нельзя писать произвольный текст! Если хотите поболтать с помощником, напишите 'Закончить разговор', чтобы начать заново.")
    else:
        # Проверяем, есть ли активное состояние у пользователя
        current_state = await state.get_state()

        # Если состояние пустое, это значит, что бот не ожидает ввода данных
        if current_state is None:
            await message.answer(f"Уважаемый {message.from_user.first_name}, нельзя писать произвольный текст!")
        else:
            # Если состояние активно, значит, бот ожидает конкретный ответ
            return

# Запуск бота и настройка команд
async def start_bot():
    """Настройка команд для бота."""
    commands = [
        BotCommand(command='menu1', description='Доп. функции'),
        BotCommand(command='menu2', description='Твой дневник и цели')
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())

# Основная асинхронная функция
async def main():
    """Запуск бота."""
    await create_db()  # Создаем таблицу при запуске
    dp.startup.register(start_bot)
    try:
        print("Бот запущен...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())  # Запуск бота в режиме опроса
    except asyncio.CancelledError:
        print("Задача была отменена. Завершаем работу бота...")
    finally:
        await bot.session.close()
        print("Бот остановлен")

# Запуск основной асинхронной функции
asyncio.run(main())