#ИМПОРТЫ
import telebot
from telebot import types
import sqlite3
import os
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

#ТАБЛИЦА МЫСЛЕЙ
conn = sqlite3.connect("notes.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    remind_time TEXT
)
""")
conn.commit()

#ТАБЛИЦА НАПОМИНАНИЙ
cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text TEXT,
    remind_time TEXT
)
""")

conn.commit()

#ПЛАНИРОВЩИК
scheduler = BackgroundScheduler(timezone = 'Europe/Moscow')
scheduler.start()
def load_reminders():
    cursor.execute("SELECT id, user_id, text, remind_time FROM reminders")
    reminders = cursor.fetchall()

    for reminder in reminders:
        reminder_id, chat_id, text, remind_time = reminder
        remind_dt = datetime.strptime(remind_time, "%Y-%m-%d %H:%M")

        if remind_dt > datetime.now():
            scheduler.add_job(
                send_reminder,
                trigger='date',
                run_date=remind_dt,
                args=[chat_id, text],
                id=str(reminder_id),
                replace_existing=True
            )

load_reminders()

#ОТПРАВКА НАПОМИНАНИЯ
def send_reminder(chat_id, text):
    bot.send_message(chat_id, f" Напоминание: {text}")
    cursor.execute('DELETE FROM reminders WHERE user_id = ? AND text = ?', (chat_id,text))
    conn.commit()


#ТОКЕН
bot = telebot.TeleBot(os.getenv("TOKEN"))

#КОМАНДА /START И КНОПКИ
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('Добавить мысль')
    btn2 = types.KeyboardButton('Добавить напоминание')
    btn3 = types.KeyboardButton('Удалить мысль')
    btn4 = types.KeyboardButton('Удалить напоминание')
    btn5 = types.KeyboardButton('Мои мысли')
    btn6 = types.KeyboardButton('Мои напоминания')
    markup.add(btn1, btn2, btn3, btn4)
    markup.add(btn5, btn6)

    bot.send_message(message.chat.id,'Добро пожаловать в бота! Здесь, вы можете запомнить все!', reply_markup=markup)

#КОМАНДА ДОБАВИТЬ МЫСЛЬ
@bot.message_handler(func=lambda message: message.text == 'Добавить мысль')
def add(message):
    msg = bot.send_message(message.chat.id,'Введите мысль, которую хотите добавить: ')
    bot.register_next_step_handler(msg, thought)

def thought(message):

    cursor.execute("INSERT INTO notes (user_id, text) VALUES (?, ?)", (message.from_user.id, message.text))
    conn.commit()

    bot.send_message(message.chat.id, "Мысль сохранена!")


#КОМАНДА ДОБАВИТЬ НАПОМИНАНИЕ
@bot.message_handler(func=lambda message: message.text == 'Добавить напоминание')
def remind(message):
    msg = bot.send_message(message.chat.id,'Введи дату и время:\n\nФормат: YYYY-MM-DD HH:MM\nПример: 2026-03-25 18:30 ')
    bot.register_next_step_handler(msg, get_time)

def get_time(message):
    try:
        try:
            remind_time = datetime.strptime(message.text, '%Y-%m-%d %H:%M')
        except ValueError:
            remind_time = datetime.strptime(message.text, '%Y-%m-%d %H:%M:%S')

        msg = bot.send_message(message.chat.id, 'Что вам напомнить?')
        bot.register_next_step_handler(msg, lambda m: save_reminder(m, remind_time))

    except ValueError:
        msg = bot.send_message(message.chat.id, "Неверный формат. Попробуйте ещё раз")
        bot.register_next_step_handler(msg, get_time)

        return

def save_reminder(message, remind_time):
    text = message.text
    user_id = message.from_user.id
    chat_id = message.chat.id

    cursor.execute("INSERT INTO reminders (user_id, text, remind_time) VALUES (?, ?, ?)",
                   (user_id, text, remind_time.strftime("%Y-%m-%d %H:%M")))

    conn.commit()

    scheduler.add_job(
        send_reminder,
        'date',
        run_date=remind_time,
        args=[chat_id, text]
    )

    bot.send_message(chat_id, "Напоминание установлено!")

def send_remind(chat_id, text):
    bot.send_message(chat_id,f'Напоминание: {text}')


#КОМАНДА МОИ МЫСЛИ
@bot.message_handler(func=lambda message: message.text == 'Мои мысли')
def my_thoughts(message):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute('SELECT text FROM notes WHERE user_id=?', (message.from_user.id,))
    thoughts = cursor.fetchall()

    if thoughts:
        text = "Ваши мысли:\n"
        for idx, thought in enumerate(thoughts, start=1):
            text += f"{idx}. {thought[0]}\n"
    else:
        text = "Нет мыслей в базе данных."

    bot.send_message(message.chat.id, text)

    conn.close()


#КОМАНДА МОИ НАПОМИНАНИЯ
@bot.message_handler(func=lambda message: message.text == 'Мои напоминания')
def my_reminder(message):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute(
        'SELECT text, remind_time FROM reminders WHERE user_id=?',
        (message.from_user.id,)
    )
    reminders = cursor.fetchall()

    if reminders:
        text = 'Ваши напоминания:\n'
        for idx, (text_remind, remind_time_item) in enumerate(reminders, start=1):
            text += f"{idx}. {text_remind} — {remind_time_item}\n"
    else:
        text = 'Нет напоминаний в базе данных'

    bot.send_message(message.chat.id, text)

    conn.close()


#КОМАНДА УДАЛИТЬ МЫСЛЬ
@bot.message_handler(func=lambda message: message.text == 'Удалить мысль')
def delete_thoughts(message):
    bot.send_message(
        message.chat.id,
        'Напиши:\n1 — Удалить одну мысль\n2 — Удалить все мысли'
    )
    bot.register_next_step_handler(message, delete_choice)


def delete_choice(message):
    if message.text == '1':
        delete_one_thought(message)
    elif message.text == '2':
        delete_all_thoughts(message)
    else:
        bot.send_message(message.chat.id, 'Напиши 1 или 2')


def delete_all_thoughts(message):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute(
        'DELETE FROM notes WHERE user_id=?',
        (message.from_user.id,)
    )
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, 'Все мысли удалены ')



def delete_one_thought(message):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute(
        'SELECT id, text FROM notes WHERE user_id=?',
        (message.from_user.id,)
    )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.send_message(message.chat.id, 'У тебя нет мыслей ')
        return

    text = 'Выбери номер мысли:\n'
    for idx, (rid, txt) in enumerate(rows, start=1):
        text += f"{idx}. {txt}\n"

    msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(msg, process_delete_one, rows)


def process_delete_one(message, rows):
    try:
        number = int(message.text)

        if 0 < number <= len(rows):
            thought_id = rows[number - 1][0]

            conn = sqlite3.connect('notes.db')
            cursor = conn.cursor()

            cursor.execute(
                'DELETE FROM notes WHERE id=?',
                (thought_id,)
            )
            conn.commit()
            conn.close()

            bot.send_message(message.chat.id, 'Мысль удалена ')
        else:
            bot.send_message(message.chat.id, 'Неверный номер ')

    except ValueError:
        bot.send_message(message.chat.id, 'Введи число')



#КОМАНДА УДАЛИТЬ НАПОМИНАНИЯ
@bot.message_handler(func=lambda message: message.text == 'Удалить напоминание')
def remind_me(message):
    bot.send_message(
        message.chat.id,
        'Напиши:\n1 — Удалить одно напоминание\n2 — Удалить все напоминания'
    )
    bot.register_next_step_handler(message, delete_choices)

def delete_choices(message):
    if message.text == '1':
        delete_one_reminder(message)
    elif message.text == '2':
        delete_all_reminder(message)
    else:
        bot.send_message(message.chat.id, 'Напиши 1 или 2')


def delete_all_reminder(message):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute(
        'DELETE FROM reminders WHERE user_id=?',
        (message.from_user.id,)
    )
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, 'Все напоминания удалены ')


def delete_one_reminder(message):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute(
        'SELECT id, text FROM reminders WHERE user_id=?',
        (message.from_user.id,)
    )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        bot.send_message(message.chat.id, 'У тебя нет напоминаний ')
        return

    text = 'Выбери номер напоминания:\n'
    for idx, (rid, txt) in enumerate(rows, start=1):
        text += f"{idx}. {txt}\n"

    msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(msg, process_delete_ones, rows)

def process_delete_ones(message, rows):
    try:
        number = int(message.text)

        if 0 < number <= len(rows):
            thought_id = rows[number - 1][0]

            conn = sqlite3.connect('notes.db')
            cursor = conn.cursor()

            cursor.execute(
                'DELETE FROM reminders WHERE id=?',
                (thought_id,)
            )
            conn.commit()
            conn.close()

            bot.send_message(message.chat.id, 'Напоминание удалено ')
        else:
            bot.send_message(message.chat.id, 'Неверный номер ')

    except ValueError:
        bot.send_message(message.chat.id, 'Введи число')

        
bot.polling(none_stop=True,timeout=60)
