import asyncio
import json
import time

import redis
import aioschedule
import telebot
from telebot import types
from telebot.async_telebot import AsyncTeleBot
import req
from datetime import datetime

with open("/data/secret.txt") as file:
    lines = [line.rstrip() for line in file]
    TOKEN = lines[0]
bot = AsyncTeleBot(TOKEN)

r = redis.Redis(host='redis', port=6379)


@bot.message_handler(commands=['help', 'start'])
async def send_welcome(message):
    t = '''
    Доступные команды:
    /student имя - после этого бот присылает информацию по указаному студенту
    /schedule yyyy.mm.dd посмотреть расписание студента в выбранную дату, без аргумента выбирается сегодня
    /link n yyyy.mm.dd присылает ссылку на пару № n, без аргументов выбирается текущая пара текущего дня
    /where n yyyy.mm.dd где проходит пара, без аргументов выбирается текущая пара текущего дня
    /help показать этот текст
    '''
    await bot.send_message(message.chat.id, t)


def valid(date_text):
    try:
        datetime.strptime(date_text, '%Y.%m.%d')
        return True
    except ValueError:
        return False


@bot.message_handler(commands=['student'])
async def set_student(message):
    name = telebot.util.extract_arguments(message.text)
    if not name:
        await bot.reply_to(message, "мне нужно имя...")
        return
    students = req.get_student(name)
    if not students:
        await bot.reply_to(message, "не нашел такого студента :(")
        return
    if len(students) == 1:
        await bot.reply_to(message, f"Я вас запомнил, {students[0]['label']}")
        r.delete(message.chat.id)
        r.hset(message.chat.id, 'student_id', students[0]['id'])
        r.hset(message.chat.id, 'student_info',
               f"{students[0]['label']}, {students[0]['description']}")
        print(r.hgetall(message.chat.id))
        return

    markup = types.InlineKeyboardMarkup()
    for i, s in enumerate(students[:5]):
        markup.add(types.InlineKeyboardButton(
            text=f"{s['label']}, {s['description'].split()[-1]}",
            callback_data=f"student {i} {s['id']}"))
    await bot.send_message(chat_id=message.chat.id,
                           text=f"нашел несколько студентов, выберите из предложенных или уточните поиск",
                           reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('student'))
async def choose_student(call):
    student_id = call.data.split()[2]
    button = int(call.data.split()[1])
    r.delete(call.message.chat.id)
    r.hset(call.message.chat.id, 'student_id', student_id)
    info = call.message.reply_markup.keyboard[button][0].text
    r.hset(call.message.chat.id, 'student_info', info)
    name = info.split(',')[0]
    print(name)
    await bot.send_message(call.message.chat.id, f"Я вас запомнил, {name}")


def get_lesson(date):
    for i in range(9):
        les_end = datetime.strptime(r.get(f"lesson{i}").decode('utf-8'),
                                    '%H:%M')
        if date.time() < les_end.time():
            return i


@bot.message_handler(commands=['link'])
async def send_schedule(message):
    if not r.exists(message.chat.id):
        await bot.reply_to(message,
                           'нужно указать имя студента с помощью /student')
        return

    date = datetime.today().strftime('%Y.%m.%d')
    lesson = get_lesson(datetime.now())
    args = telebot.util.extract_arguments(message.text).split()
    if len(args) > 0:
        if not args[0].isdigit():
            await bot.reply_to(message, 'неподходящий номер пары')
            return
        lesson = int(args[0])

    if len(args) > 1:
        date = args[1]

    if not valid(date):
        await bot.reply_to(message,
                           'неподходящий формат даты (нужен %Y.%m.%d)')
        return

    key = f"schedule-{date}"

    if not r.hexists(message.chat.id, key):
        res = req.get_schedule(r.hget(message.chat.id, 'student_id'), date)
        r.hset(message.chat.id, key, res)
    else:
        res = r.hget(message.chat.id, key).decode('utf-8')

    for el in json.loads(res):
        if int(el['lessonNumberStart']) <= lesson <= int(
                el['lessonNumberEnd']):
            if el['url1']:
                await bot.reply_to(message, el['url1'])
                return
            await bot.reply_to(message, 'на пару нет ссылки')
            return

    await bot.reply_to(message, 'нет пары')


@bot.message_handler(commands=['where'])
async def send_schedule(message):
    if not r.exists(message.chat.id):
        await bot.reply_to(message,
                           'нужно указать имя студента с помощью /student')
        return

    date = datetime.today().strftime('%Y.%m.%d')
    lesson = get_lesson(datetime.now())
    args = telebot.util.extract_arguments(message.text).split()
    if len(args) > 0:
        if not args[0].isdigit():
            await bot.reply_to(message, 'неподходящий номер пары')
            return
        lesson = int(args[0])

    if len(args) > 1:
        date = args[1]
    if not valid(date):
        await bot.reply_to(message,
                           'неподходящий формат даты (нужен %Y.%m.%d)')
        return

    key = f"schedule-{date}"
    if not r.hexists(message.chat.id, key):
        res = req.get_schedule(r.hget(message.chat.id, 'student_id'), date)
        r.hset(message.chat.id, key, res)
    else:
        res = r.hget(message.chat.id, key).decode('utf-8')

    for el in json.loads(res):
        if int(el['lessonNumberStart']) <= lesson <= int(
                el['lessonNumberEnd']):
            await bot.reply_to(message,
                               f"{el['building']}, {el['auditorium']}")
            return
    await bot.reply_to(message, 'в настоящее время нет пар')


@bot.message_handler(commands=['schedule'])
async def send_schedule(message):
    if not r.exists(message.chat.id):
        await bot.reply_to(message,
                           'нужно указать имя студента с помощью /student')
        return
    date = telebot.util.extract_arguments(message.text)
    if not date:
        date = datetime.today().strftime('%Y.%m.%d')

    if not valid(date):
        await bot.reply_to(message,
                           'неподходящий формат даты (нужен %Y.%m.%d)')
        return
    key = f"schedule-{date}"
    if not r.hexists(message.chat.id, key):
        print('does not exist')
        res = req.get_schedule(r.hget(message.chat.id, 'student_id'), date)
        r.hset(message.chat.id, key, res)
    else:
        print('exists')
        print(r.hget(message.chat.id, key).decode('utf-8'))
        res = r.hget(message.chat.id, key).decode('utf-8')
    text = ''
    for el in json.loads(res):
        text += f"{el['beginLesson']} - {el['endLesson']} {el['discipline']}\n"
    if not text:
        text = 'пар нет'
    await bot.reply_to(message, text)


@bot.message_handler(commands=['info'])
async def get_student(message):
    if not r.exists(message.chat.id):
        await bot.reply_to(message,
                           'сначала нужно указать имя студента с помощью /student')
        return

    await bot.send_message(message.chat.id,
                           r.hget(message.chat.id, 'student_info').decode(
                               'utf-8'))


async def scheduler():
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)


async def main():
    await bot.set_my_commands([
        telebot.types.BotCommand("/help", "bot info"),
        telebot.types.BotCommand("/student", "set student"),
        telebot.types.BotCommand("/schedule", "show todays schedule"),
        telebot.types.BotCommand("/link",
                                 "get link to ongoing lesson"),
        telebot.types.BotCommand("/where",
                                 "get address of upcoming lesson"),
        telebot.types.BotCommand("/info",
                                 "see your info")])
    r.set('lesson0', '9:30')
    r.set('lesson1', '10:50')
    r.set('lesson2', '12:30')
    r.set('lesson3', '14:20')
    r.set('lesson4', '16:00')
    r.set('lesson5', '17:40')
    r.set('lesson6', '19:30')
    r.set('lesson7', '21:00')
    r.set('lesson8', '23:59')
    await asyncio.gather(bot.infinity_polling(), scheduler())


if __name__ == '__main__':
    asyncio.run(main())
