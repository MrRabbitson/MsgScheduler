import asyncio
from aiogram import html
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.formatting import Text, Bold, Italic, Code, Underline, Spoiler
import aiohttp
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.enums import ParseMode
import config
from base import SQL
import logging
from datetime import datetime
import re
import subprocess
from aiogram.filters import Command
from colorama import just_fix_windows_console
import sys
from threading import Thread
import os
from pathlib import Path
import json

just_fix_windows_console()

SUPPORT_CHAT_ID = config.chat_id
db = SQL('db.db')
logger = logging.getLogger(__name__)
bot = Bot(token=config.TOKEN)
dp = Dispatcher()

images_dir = Path("images")
images_dir.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)

# Discord Proxy
discord_proxy_path = r"discord-proxy\discord.bat"
if config.USE_PROXY == True:
    print('\033[35m[discord-proxy] [INIT]\033[0m Loading proxies...')


def log_output(pipe, prefix, color_code):
    for line in iter(pipe.readline, ''):
        print(f"\033[{color_code}m{prefix}\033[0m {line.strip()}")
    pipe.close()


def run_with_logging(bat_file):
    process = subprocess.Popen(
        bat_file,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding='cp866'
    )

    Thread(target=log_output, args=(process.stdout, "[discord-proxy] [INFO]", "36")).start()
    Thread(target=log_output, args=(process.stderr, "[discord-proxy] [ERROR]", "31")).start()

    return process

if config.USE_PROXY == True:
    proxy_process = run_with_logging(discord_proxy_path)

# Клавиатуры
kb_main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📅 Создать рассылку", callback_data="new_message")],
    [InlineKeyboardButton(text="📋 Мои рассылки", callback_data="my_messages")],
    [InlineKeyboardButton(text="🤷‍♀️ Тех.поддержка", callback_data="support")]
])

platform_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Telegram", callback_data="platform_telegram")],
    [InlineKeyboardButton(text="Discord", callback_data="platform_discord")]
])

message_type_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔄 Регулярное", callback_data="message_type_recurring")],
    [InlineKeyboardButton(text="⏰ Одноразовое", callback_data="message_type_one_time")]
])

image_confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Да", callback_data="add_image_yes")],
    [InlineKeyboardButton(text="❌ Нет", callback_data="add_image_no")]
])

buttons_confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Да", callback_data="add_buttons_yes")],
    [InlineKeyboardButton(text="❌ Нет", callback_data="add_buttons_no")]
])

feedback_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Да", callback_data="feedback_yes")],
    [InlineKeyboardButton(text="❌ Нет", callback_data="feedback_no")]
])

feedback_reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✉️ Ответить", callback_data="reply_feedback")]
])


def get_days_keyboard(selected_days=None):
    if selected_days is None:
        selected_days = {}

    days = [
        ("Понедельник", "monday"),
        ("Вторник", "tuesday"),
        ("Среда", "wednesday"),
        ("Четверг", "thursday"),
        ("Пятница", "friday"),
        ("Суббота", "saturday"),
        ("Воскресенье", "sunday")
    ]

    keyboard = []
    row = []

    for day_name, day_code in days:
        if selected_days.get(day_code, False):
            emoji = "✅"
        else:
            emoji = "❌"

        button = InlineKeyboardButton(
            text=f"{emoji} {day_name}",
            callback_data=f"toggle_{day_code}"
        )
        row.append(button)

        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="🔹 Подтвердить выбор", callback_data="confirm_days")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def check_bot_access(bot: Bot, chat_id: int) -> bool:
    try:
        await bot.send_chat_action(chat_id, 'typing')
        return True
    except Exception as e:
        return False


@dp.message(Command("start"))
async def start(message: Message):
    # Обработка параметра feedback в команде /start
    if len(message.text.split()) > 1 and message.text.split()[1].startswith('feedback_'):
        creator_id = int(message.text.split('_')[1])
        db.update_user_data(
            user_id=message.from_user.id,
            current_state="feedback_message_input",
            feedback_creator_id=creator_id
        )
        await message.answer("✍️ Напишите ваш отзыв или вопрос:")
        return

    if not db.user_exists(message.from_user.id):
        db.add_user(message.from_user.id, message.from_user.full_name)
        db.update_field('users', message.from_user.id, 'support_status', 0)
        db.update_field('users', message.from_user.id, 'support_target_user', None)

    db.update_user_data(
        user_id=message.from_user.id,
        current_state="main_menu",
        platform=None,
        message_type=None,
        text=None,
        original_text=None,
        time=None,
        date=None,
        chat_id=None,
        webhook=None,
        image_file_id=None,
        feedback=None,
        feedback_button_text=None,
        feedback_creator_id=None,
        feedback_reply_user_id=None,
        buttons=None,
        selected_days=None
    )

    await message.answer(
        "📨 Бот для управления рассылками\n\n"
        "Вы можете создавать регулярные и одноразовые рассылки в Telegram и Discord",
        reply_markup=kb_main
    )


@dp.message(Command("id"))
async def get_chat_id(message: Message):
    await message.reply(f'Вот ID этого чата: `{message.chat.id}`', parse_mode=ParseMode.MARKDOWN_V2)


@dp.callback_query(F.data == "my_messages")
async def show_my_messages(callback: CallbackQuery):
    user_id = callback.from_user.id

    tg_messages = db.get_user_telegram_messages(user_id)
    discord_messages = db.get_user_discord_messages(user_id)

    if not tg_messages and not discord_messages:
        await callback.answer("У вас пока нет созданных рассылок")
        return

    await callback.message.answer("📋 Ваши рассылки:")

    for msg in tg_messages:
        text = format_message_info(msg, "Telegram")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_tg_{msg['id']}")]
        ])
        try:
            if msg.get('image'):
                image_path = images_dir / msg['image']
                with open(image_path, 'rb') as photo:
                    await callback.message.answer_photo(
                        photo=types.BufferedInputFile(photo.read(), filename=msg['image']),
                        caption=text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard
                    )
            else:
                await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception as e:
            print(f"Ошибка при показе сообщения: {e}")
            await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    for msg in discord_messages:
        text = format_message_info(msg, "Discord")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_discord_{msg['id']}")]
        ])
        await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    await callback.answer()


def format_message_info(msg, platform):
    text = f"<b>Платформа:</b> {platform}\n"
    text += f"<b>Тип:</b> {'Регулярное' if not msg['date'] else 'Одноразовое'}\n"
    text += f"<b>Время:</b> {msg['time']}\n"

    if msg['date']:
        text += f"<b>Дата:</b> {msg['date']}\n"
    else:
        active_days = []
        if msg['onMondays']: active_days.append("Понедельник")
        if msg['onTuesdays']: active_days.append("Вторник")
        if msg['onWednesdays']: active_days.append("Среда")
        if msg['onThursdays']: active_days.append("Четверг")
        if msg['onFridays']: active_days.append("Пятница")
        if msg['onSaturdays']: active_days.append("Суббота")
        if msg['onSundays']: active_days.append("Воскресенье")
        if active_days:
            text += f"<b>Дни недели:</b> {', '.join(active_days)}\n"

    if platform == "Telegram":
        preview_chat_id = str(msg['chat_id'])
        text += f"<b>ID чата:</b> {html.quote(preview_chat_id)}\n"
    else:
        text += f"<b>Webhook:</b> {msg['webhook'][:20]}...\n"

    preview_length = 100
    message_text = re.sub(r'<[^>]+>', '', msg['text'])
    if len(message_text) > preview_length:
        preview_text = f'{message_text[:preview_length]}...'
    else:
        preview_text = message_text

    text += f"<b>Текст:</b>\n<code>{html.quote(preview_text)}</code>"

    if msg.get('buttons'):
        buttons = msg['buttons']
        if isinstance(buttons, str):
            try:
                buttons = json.loads(buttons)
            except json.JSONDecodeError:
                buttons = None

        if buttons and isinstance(buttons, list):
            buttons_preview = []
            for btn in buttons:
                if isinstance(btn, dict):
                    btn_text = btn.get('text', '')
                    btn_url = btn.get('url', 'кнопка обратной связи')
                    buttons_preview.append(f"{btn_text} - {btn_url}")

            if buttons_preview:
                text += f"\n<b>Кнопки:</b>\n<code>{html.quote('\n'.join(buttons_preview))}</code>"

    return text


@dp.callback_query(F.data.startswith("close_"))
async def close_support(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    db.update_field('users', user_id, 'support_status', 0)
    await callback.message.delete()
    await callback.answer()


@dp.callback_query(F.data.startswith("answer_"))
async def reply_to_user(callback: CallbackQuery):
    admin_id = callback.from_user.id
    user_id = int(callback.data.split("_")[1])

    db.update_field('users', admin_id, 'support_status', 2)
    db.update_field('users', admin_id, 'support_target_user', user_id)

    await callback.message.answer(f"✍️ Введите ответ для пользователя (ID: {user_id}):")
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_tg_"))
async def delete_telegram_message(callback: CallbackQuery):
    message_id = int(callback.data.split("_")[2])
    db.delete_telegram_message(message_id)
    await callback.message.delete()
    await callback.answer("Рассылка удалена!")


@dp.callback_query(F.data.startswith("delete_discord_"))
async def delete_discord_message(callback: CallbackQuery):
    message_id = int(callback.data.split("_")[2])
    db.delete_discord_message(message_id)
    await callback.message.delete()
    await callback.answer("Рассылка удалена!")


@dp.callback_query(F.data == "new_message")
async def new_message(callback: CallbackQuery):
    db.update_user_data(
        user_id=callback.from_user.id,
        current_state="platform_selection"
    )
    await callback.message.edit_text("Выберите платформу для рассылки:", reply_markup=platform_keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("platform_"))
async def process_platform(callback: CallbackQuery):
    platform = callback.data.split("_")[1]
    db.update_user_data(
        user_id=callback.from_user.id,
        current_state="message_type_selection",
        platform=platform
    )
    await callback.message.edit_text("Выберите тип сообщения:", reply_markup=message_type_keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("message_type_"))
async def process_message_type(callback: CallbackQuery):
    message_type = callback.data.split("_")[2]
    db.update_user_data(
        user_id=callback.from_user.id,
        current_state="text_input",
        message_type=message_type
    )
    await callback.message.edit_text(
        "✍️ <b>Введите текст сообщения</b>\n\n"
        "<b>Поддерживается форматирование:</b>\n\n"
        "<b>Жирный текст</b> - **текст**\n"
        "<i>Наклонный текст</i> - _текст_\n"
        "<u>Подчёркнутый текст</u> - __текст__\n"
        "<s>Зачёркнутый текст</s> - ~текст~\n"
        "<code>Моноширинный текст</code> - `текст`\n"
        "<pre>Блок кода</pre> - ```код```\n"
        "Спойлер - ||текст||\n\n"
        "Или используйте HTML теги: &lt;b&gt;, &lt;i&gt;, &lt;u&gt;, &lt;s&gt;, &lt;code&gt;, &lt;pre&gt;\n\n"
        "Просто напишите сообщение с нужным форматированием:",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.message(F.text)
async def handle_text(message: Message):
    user_data = db.get_user_data(message.from_user.id)
    user_id = message.from_user.id
    support_status = db.get_field('users', user_id, 'support_status')

    # Режим поддержки
    if support_status == 1:
        kb_admin = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Ответить", callback_data=f"answer_{user_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"close_{user_id}")]
        ])
        await bot.send_message(
            chat_id=SUPPORT_CHAT_ID,
            text=f"👤 <b>Сообщение от {message.from_user.full_name} (ID: {user_id}):</b>\n\n{message.text}",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_admin
        )
        await message.answer("✅ Ваше сообщение отправлено. Ожидайте ответа!")
        db.update_field('users', user_id, 'support_status', 0)
        return
    elif support_status == 2:
        target_user_id = db.get_field('users', user_id, 'support_target_user')
        if target_user_id:
            try:
                kb_answer = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💬 Ответить", callback_data="support")]
                ])
                await bot.send_message(
                    chat_id=target_user_id,
                    text=f"📩 <b>Ответ поддержки:</b>\n\n{message.text}",
                    parse_mode=ParseMode.HTML, reply_markup=kb_answer
                )
                await message.answer(f"✅ Ответ отправлен пользователю (ID: {target_user_id})")
            except Exception as e:
                await message.answer(f"❌ Ошибка: пользователь заблокировал бота.")
        db.update_field('users', user_id, 'support_status', 0)
        db.update_field('users', target_user_id, 'support_status', 0)
        return

    if not user_data:
        await start(message)
        return

    current_state = user_data.get('current_state')
    if current_state == "feedback_message_input":
        await process_feedback_message(message)
        return
    elif current_state == "feedback_reply_input":
        await process_feedback_reply(message)
        return
    elif current_state == "text_input":
        await process_text(message)
    elif current_state == "feedback_text_input":
        await process_feedback_button_text(message)
    elif current_state == "time_input":
        await process_time(message)
    elif current_state == "date_input":
        await process_date(message)
    elif current_state == "chat_link_input":
        await process_chat_link(message)
    elif current_state == "webhook_input":
        await process_webhook(message)
    elif current_state == "buttons_input":
        await process_buttons_text(message)
    else:
        await message.answer("Пожалуйста, выберите действие из меню:", reply_markup=kb_main)


async def process_text(message: Message):
    original_text = message.text if message.content_type == types.ContentType.TEXT else message.caption or ""
    html_text = message.html_text if message.content_type == types.ContentType.TEXT else message.html_caption or original_text

    db.update_user_data(
        user_id=message.from_user.id,
        current_state="image_choice",
        text=html_text,
        original_text=original_text
    )
    await message.answer("Хотите добавить изображение к сообщению?", reply_markup=image_confirm_keyboard)


@dp.callback_query(F.data.startswith("add_image_"))
async def process_image_choice(callback: CallbackQuery):
    user_data = db.get_user_data(callback.from_user.id)
    if not user_data or user_data['current_state'] != "image_choice":
        await callback.answer("Сессия устарела. Начните заново.")
        return

    if callback.data == "add_image_yes":
        db.update_user_data(
            user_id=callback.from_user.id,
            current_state="image_upload"
        )
        await callback.message.edit_text("Пожалуйста, отправьте изображение (максимум 1):")
    else:
        db.update_user_data(
            user_id=callback.from_user.id,
            current_state="buttons_choice"
        )
        await callback.message.edit_text("👀 <b>Предпросмотр вашего сообщения:</b>\n\n" + user_data['text'],
                                         parse_mode=ParseMode.HTML)
        await process_buttons_after_image(callback.message, callback.from_user.id)
    await callback.answer()


async def process_buttons_after_image(message: Message, user_id: int):
    db.update_user_data(
        user_id=user_id,
        current_state="buttons_choice"
    )
    await message.answer("Хотите добавить кнопки к сообщению? (максимум 5)",
                         reply_markup=buttons_confirm_keyboard)


@dp.message(F.photo)
async def process_image(message: Message):
    user_data = db.get_user_data(message.from_user.id)
    if not user_data or user_data['current_state'] != "image_upload":
        return

    photo = message.photo[-1]
    file_id = photo.file_id

    db.update_user_data(
        user_id=message.from_user.id,
        current_state="buttons_choice",
        image_file_id=file_id
    )

    preview_text = "👀 <b>Предпросмотр вашего сообщения:</b>\n\n" + user_data['text']

    try:
        await message.answer_photo(photo.file_id, caption=preview_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"Ошибка при показе предпросмотра: {e}")
        await message.answer("✅ Ваше сообщение с изображением принято.")

    await process_buttons_after_image(message, message.from_user.id)


@dp.callback_query(F.data.startswith("add_buttons_"))
async def process_buttons_choice(callback: CallbackQuery):
    user_data = db.get_user_data(callback.from_user.id)
    if not user_data or user_data['current_state'] != "buttons_choice":
        await callback.answer("Сессия устарела. Начните заново.")
        return

    if callback.data == "add_buttons_yes":
        db.update_user_data(
            user_id=callback.from_user.id,
            current_state="buttons_input"
        )
        await callback.message.edit_text(
            "Введите кнопки в формате:\n\n"
            "Текст кнопки1 - URL1\n"
            "Текст кнопки2 - URL2\n\n"
            "Максимум 5 кнопок. Пример:\n"
            "Наш сайт - https://example.com\n"
            "Документация - https://example.com/docs"
        )
    else:
        if user_data['message_type'] == "recurring":
            db.update_user_data(
                user_id=callback.from_user.id,
                current_state="days_selection",
                selected_days=json.dumps({})
            )
            await callback.message.edit_text(
                "Выберите дни недели, когда должно отправляться сообщение:",
                reply_markup=get_days_keyboard()
            )
        else:
            db.update_user_data(
                user_id=callback.from_user.id,
                current_state="feedback_choice"
            )
            await callback.message.edit_text("Хотите включить возможность обратной связи?",
                                             reply_markup=feedback_keyboard)
    await callback.answer()


async def process_buttons_text(message: Message):
    user_data = db.get_user_data(message.from_user.id)
    if not user_data or user_data['current_state'] != "buttons_input":
        return

    buttons_text = message.text.strip()
    buttons = []
    errors = []

    for line in buttons_text.split('\n'):
        if '-' in line:
            text, url = line.split('-', 1)
            text = text.strip()
            url = url.strip()

            if not text or not url:
                errors.append(f"Пустой текст или URL в строке: {line}")
                continue

            if not url.startswith(('http://', 'https://')):
                errors.append(f"URL должен начинаться с http:// или https:// в строке: {line}")
                continue

            buttons.append({'text': text, 'url': url})

            if len(buttons) >= 5:
                break

    if errors:
        error_msg = "Обнаружены ошибки:\n\n" + "\n".join(errors)
        await message.answer(error_msg + "\n\nПожалуйста, исправьте ошибки и отправьте кнопки снова:")
        return

    db.update_user_data(
        user_id=message.from_user.id,
        buttons=json.dumps(buttons) if buttons else None
    )

    if buttons:
        buttons_preview = "\n".join([f"{btn['text']} - {btn['url']}" for btn in buttons])
        if user_data['message_type'] == "recurring":
            db.update_user_data(
                user_id=message.from_user.id,
                current_state="days_selection",
                selected_days=json.dumps({})
            )
            await message.answer(f"✅ Кнопки добавлены:\n\n{buttons_preview}\n\n"
                                 "Выберите дни недели, когда должно отправляться сообщение:",
                                 reply_markup=get_days_keyboard())
        else:
            db.update_user_data(
                user_id=message.from_user.id,
                current_state="feedback_choice"
            )
            await message.answer(f"✅ Кнопки добавлены:\n\n{buttons_preview}\n\n"
                                 "Хотите включить возможность обратной связи?",
                                 reply_markup=feedback_keyboard)
    else:
        if user_data['message_type'] == "recurring":
            db.update_user_data(
                user_id=message.from_user.id,
                current_state="days_selection",
                selected_days=json.dumps({})
            )
            await message.answer("Кнопки не добавлены. Выберите дни недели, когда должно отправляться сообщение:",
                                 reply_markup=get_days_keyboard())
        else:
            db.update_user_data(
                user_id=message.from_user.id,
                current_state="feedback_choice"
            )
            await message.answer("Кнопки не добавлены. Хотите включить возможность обратной связи?",
                                 reply_markup=feedback_keyboard)


@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_day_selection(callback: CallbackQuery):
    user_data = db.get_user_data(callback.from_user.id)
    if not user_data or user_data['current_state'] != "days_selection":
        await callback.answer("Сессия устарела. Начните заново.")
        return

    selected_days = json.loads(user_data['selected_days']) if user_data['selected_days'] else {}
    day_code = callback.data.split("_")[1]

    selected_days[day_code] = not selected_days.get(day_code, False)

    db.update_user_data(
        user_id=callback.from_user.id,
        selected_days=json.dumps(selected_days)
    )

    await callback.message.edit_reply_markup(
        reply_markup=get_days_keyboard(selected_days)
    )
    await callback.answer()


@dp.callback_query(F.data == "confirm_days")
async def confirm_days_selection(callback: CallbackQuery):
    user_data = db.get_user_data(callback.from_user.id)
    if not user_data or user_data['current_state'] != "days_selection":
        await callback.answer("Сессия устарела. Начните заново.")
        return

    selected_days = json.loads(user_data['selected_days']) if user_data['selected_days'] else {}

    if not any(selected_days.values()):
        await callback.answer("Выберите хотя бы один день!", show_alert=True)
        return

    db.update_user_data(
        user_id=callback.from_user.id,
        current_state="feedback_choice"
    )
    await callback.message.edit_text("Хотите включить возможность обратной связи?",
                                     reply_markup=feedback_keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("feedback_"))
async def process_feedback_choice(callback: CallbackQuery):
    user_data = db.get_user_data(callback.from_user.id)

    if not user_data:
        await callback.answer("Сессия устарела. Начните заново.")
        return

    if callback.data == "feedback_yes":
        db.update_user_data(
            user_id=callback.from_user.id,
            current_state="feedback_text_input",
            feedback=True
        )
        await callback.message.edit_text('Введите текст для кнопки обратной связи (например, "Оставить отзыв"):')
    else:
        db.update_user_data(
            user_id=callback.from_user.id,
            current_state="time_input",
            feedback=False
        )
        ctime = datetime.now().strftime('%H:%M')
        await callback.message.edit_text(f"Укажите время отправки в формате ЧЧ:ММ\n(текущее время — {ctime}):")
    await callback.answer()


async def process_feedback_button_text(message: Message):
    db.update_user_data(
        user_id=message.from_user.id,
        current_state="time_input",
        feedback_button_text=message.text
    )
    ctime = datetime.now().strftime('%H:%M')
    await message.answer(f"Укажите время отправки в формате ЧЧ:ММ\n(текущее время — {ctime}):")


async def process_time(message: Message):
    if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', message.text):
        await message.answer("Неверный формат времени. Укажите время в формате ЧЧ:ММ")
        return

    user_data = db.get_user_data(message.from_user.id)
    db.update_user_data(
        user_id=message.from_user.id,
        time=message.text
    )
    if user_data['message_type'].startswith('one'):
        db.update_user_data(
            user_id=message.from_user.id,
            current_state="date_input"
        )
        cdate = datetime.now().strftime('%d.%m.%Y')
        await message.answer(f"Укажите дату отправки в формате ДД.ММ.ГГГГ\n(текущая дата — {cdate}):")
        return
    else:
        if user_data['platform'] == "telegram":
            db.update_user_data(
                user_id=message.from_user.id,
                current_state="chat_link_input"
            )
            await message.answer(
                f"Введите:\n"
                f"- Числовой ID чата (начинается с -)\n"
                f"- Имя канала (начинается с @, например @mychannel)\n\n"
                f"Как получить ID:\n"
                f"1. Добавьте бота в чат/канал\n"
                f"2. Для чатов: используйте команду /id в чате\n"
                f"3. Для каналов: укажите @username канала",
                parse_mode=ParseMode.HTML
            )
        else:
            db.update_user_data(
                user_id=message.from_user.id,
                current_state="webhook_input"
            )
            await message.answer("Введите URL вебхука Discord:")


async def process_date(message: Message):
    try:
        # Проверяем, что дата парсится
        datetime.strptime(message.text, "%d.%m.%Y")
        db.update_user_data(
            user_id=message.from_user.id,
            date=message.text
        )
    except ValueError:
        await message.answer("❌ Неверный формат даты. Укажите дату в формате ДД.ММ.ГГГГ")
        return

    user_data = db.get_user_data(message.from_user.id)
    db.update_user_data(
        user_id=message.from_user.id,
        date=message.text
    )

    if user_data['platform'] == "telegram":
        db.update_user_data(
            user_id=message.from_user.id,
            current_state="chat_link_input"
        )
        await message.answer(
            f"Введите:\n"
            f"- Числовой ID чата (начинается с -)\n"
            f"- Имя канала (начинается с @, например @mychannel)\n\n"
            f"Как получить ID:\n"
            f"1. Добавьте бота в чат/канал\n"
            f"2. Для чатов: используйте команду /id в чате\n"
            f"3. Для каналов: укажите @username канала",
            parse_mode=ParseMode.HTML
        )
    else:
        db.update_user_data(
            user_id=message.from_user.id,
            current_state="webhook_input"
        )
        await message.answer("Введите URL вебхука Discord:")


async def process_chat_link(message: Message):
    user_data = db.get_user_data(message.from_user.id)
    if not user_data or user_data['current_state'] != "chat_link_input":
        return

    input_text = message.text.strip()
    chat_id = None

    # Проверка формата ввода
    if input_text.startswith('-') and input_text[1:].isdigit():
        chat_id = input_text
    elif input_text.startswith('@'):
        try:
            chat = await bot.get_chat(input_text)
            chat_id = str(chat.id)
        except Exception as e:
            await message.answer(f"❌ Не удалось найти канал {input_text}. Убедитесь, что:\n"
                                 "1. Бот добавлен в канал как администратор\n"
                                 "2. Вы указали правильное имя канала")
            return
    else:
        await message.answer(
            "Неверный формат! Введите:\n"
            "- Числовой ID чата (начинается с -)\n"
            "- Имя канала (начинается с @)\n\n"
            "Как получить ID:\n"
            "1. Добавьте бота в чат/канал\n"
            "2. Для чатов: используйте команду /id",
            parse_mode=ParseMode.HTML
        )
        return

    # Проверка прав бота
    try:
        chat = await bot.get_chat(chat_id)
        member = await bot.get_chat_member(chat_id, bot.id)

        if chat.type == 'channel':
            # Для каналов бот должен быть администратором
            if member.status != 'administrator':
                await message.answer("❌ Бот должен быть администратором канала!")
                return

        elif chat.type in ['group', 'supergroup']:
            # Для групп достаточно, чтобы бот был участником и не был ограничен
            if member.status == 'restricted':
                await message.answer("❌ У бота ограничены права в этом чате!")
                return
            elif member.status in ['left', 'kicked']:
                await message.answer("❌ Бот не состоит в этом чате или был исключен!")
                return

        elif chat.type == 'private':
            # Для личных сообщений всегда можно отправлять
            pass

    except Exception as e:
        await message.answer(
            f"❌ Ошибка доступа: {str(e)}\n"
            "Убедитесь, что:\n"
            "1. Бот добавлен в чат/канал\n"
            "2. Для каналов - бот является администратором"
        )
        return

    # Если все проверки пройдены
    db.update_user_data(
        user_id=message.from_user.id,
        chat_id=chat_id
    )
    await save_message(message)


async def process_webhook(message: Message):
    user_data = db.get_user_data(message.from_user.id)
    if not user_data or user_data['current_state'] != "webhook_input":
        return

    webhook = message.text.strip()
    if not (webhook.startswith("https://") and "discord.com/api/webhooks" in webhook):
        await message.answer("Неверный формат вебхука. Введите корректный URL")
        return

    db.update_user_data(
        user_id=message.from_user.id,
        webhook=webhook
    )
    await save_message(message)


async def save_message(message: Message):
    user_data = db.get_user_data(message.from_user.id)
    if not user_data:
        await message.answer("Ошибка: данные сессии не найдены. Начните заново.")
        return

    html_text = user_data['text']
    original_text = user_data.get('original_text', html_text)
    buttons = json.loads(user_data['buttons']) if user_data['buttons'] else []

    if user_data.get('feedback', False):
        feedback_button_text = user_data.get('feedback_button_text', "💬 Обратная связь")
        if user_data['platform'] == "telegram":
            buttons.append({
                "text": feedback_button_text,
                "url": f"https://t.me/{config.BOT_USERNAME}?start=feedback_{message.from_user.id}"
            })
        else:
            buttons.append({
                "text": feedback_button_text,
                "callback_data": f"user_feedback_{message.from_user.id}"
            })

    if user_data['platform'] == "telegram":
        formatted_text = html_text
    else:
        formatted_text = original_text

    # Обработка даты для одноразовых сообщений
    if user_data['message_type'] == "one_time" and user_data.get("date"):
        try:
            date_obj = datetime.strptime(user_data["date"], "%d.%m.%Y")
            days_params = {
                'onMondays': 0,
                'onTuesdays': 0,
                'onWednesdays': 0,
                'onThursdays': 0,
                'onFridays': 0,
                'onSaturdays': 0,
                'onSundays': 0,
            }
        except:
            await message.answer("❌ Ошибка формата даты. Создайте рассылку заново.")
            db.clear_user_data(message.from_user.id)
            return
    else:
        days_params = {
            'onMondays': 0,
            'onTuesdays': 0,
            'onWednesdays': 0,
            'onThursdays': 0,
            'onFridays': 0,
            'onSaturdays': 0,
            'onSundays': 0,
        }

    common_data = {
        "id_user": message.from_user.id,
        "msg": formatted_text,
        "name_user": message.from_user.full_name,
        "time": user_data["time"],
        "date": user_data.get("date", ""),
        "buttons": buttons if buttons else None,
        **days_params
    }

    if user_data["platform"] == "telegram":
        db.add_msg_telegram(
            id_user=common_data["id_user"],
            id_chat=user_data["chat_id"],
            msg=common_data["msg"],
            name_user=common_data["name_user"],
            time=common_data["time"],
            date=common_data["date"],
            buttons=common_data["buttons"],
            onMondays=common_data["onMondays"],
            onTuesdays=common_data["onTuesdays"],
            onWednesdays=common_data["onWednesdays"],
            onThursdays=common_data["onThursdays"],
            onFridays=common_data["onFridays"],
            onSaturdays=common_data["onSaturdays"],
            onSundays=common_data["onSundays"]
        )
        message_id = db.cursor.lastrowid
    else:
        db.add_msg_discord(
            id_user=common_data["id_user"],
            webhook=user_data["webhook"],
            msg=common_data["msg"],
            name_user=common_data["name_user"],
            time=common_data["time"],
            date=common_data["date"],
            buttons=common_data["buttons"],
            onMondays=common_data["onMondays"],
            onTuesdays=common_data["onTuesdays"],
            onWednesdays=common_data["onWednesdays"],
            onThursdays=common_data["onThursdays"],
            onFridays=common_data["onFridays"],
            onSaturdays=common_data["onSaturdays"],
            onSundays=common_data["onSundays"]
        )
        message_id = db.cursor.lastrowid

    if "image_file_id" in user_data:
        try:
            file = await bot.get_file(user_data["image_file_id"])
            file_path = file.file_path
            image_filename = f"{message_id}.png"
            image_path = images_dir / image_filename

            await bot.download_file(file_path, destination=image_path)

            if user_data["platform"] == "telegram":
                db.update_field("telegram", message_id, "image", image_filename)
            else:
                db.update_field("discord", message_id, "image", image_filename)
        except:
            print('нет изображения')

    response_text = (
        "✅ <b>Рассылка успешно создана!</b>\n\n"
        f"<b>Платформа:</b> {user_data['platform'].capitalize()}\n"
        f"<b>Тип:</b> {'Регулярное' if user_data['message_type'] == 'recurring' else 'Одноразовое'}\n"
        f"<b>Время:</b> {user_data['time']}\n"
    )

    if user_data.get("date"):
        response_text += f"<b>Дата:</b> {user_data['date']}\n"
    is_recurring = user_data['message_type'] == 'recurring'
    if is_recurring:
        selected_days = json.loads(user_data['selected_days']) if user_data['selected_days'] else {}
        days_names = {
            "monday": "Понедельник",
            "tuesday": "Вторник",
            "wednesday": "Среда",
            "thursday": "Четверг",
            "friday": "Пятница",
            "saturday": "Суббота",
            "sunday": "Воскресенье"
        }
        active_days = [days_names[day] for day, active in selected_days.items() if active]
        if active_days:
            response_text += f"<b>Дни недели:</b> {', '.join(active_days)}\n"

    preview_length = 100
    if len(original_text) > preview_length:
        preview_text = f'{original_text[:preview_length]}...'
    else:
        preview_text = original_text

    response_text += f"<b>Текст:</b>\n<code>{html.quote(preview_text)}</code>"

    if buttons:
        buttons_preview = "\n".join([f"{btn['text']} - {btn.get('url', 'кнопка обратной связи')}" for btn in buttons])
        response_text += f"\n<b>Кнопки:</b>\n<code>{html.quote(buttons_preview)}</code>"

    await message.answer(response_text, reply_markup=kb_main, parse_mode=ParseMode.HTML)
    db.clear_user_data(message.from_user.id)


@dp.callback_query(F.data.startswith("user_feedback_"))
async def handle_feedback(callback: CallbackQuery):
    creator_id = int(callback.data.split("_")[2])

    db.update_user_data(
        user_id=callback.from_user.id,
        current_state="feedback_message_input",
        feedback_creator_id=creator_id
    )

    await callback.message.answer("✍️ Напишите ваш отзыв или вопрос:")
    await callback.answer()


async def process_feedback_message(message: Message):
    user_data = db.get_user_data(message.from_user.id)
    creator_id = user_data.get("feedback_creator_id")

    if creator_id:
        try:
            await bot.send_message(
                chat_id=creator_id,
                text=f"📨 Новый отзыв от {message.from_user.full_name} (ID: {message.from_user.id}):\n\n{message.text}",
                reply_markup=feedback_reply_keyboard
            )
            await message.answer("✅ Ваш отзыв отправлен создателю рассылки!")
        except Exception:
            await message.answer("❌ Не удалось отправить отзыв. Создатель рассылки, возможно, заблокировал бота.")

    db.update_user_data(
        user_id=message.from_user.id,
        current_state=None,
        feedback_creator_id=None
    )


@dp.callback_query(F.data == "reply_feedback")
async def reply_to_feedback(callback: CallbackQuery):
    text = callback.message.text
    user_id = int(re.search(r"ID: (\d+)", text).group(1))

    db.update_user_data(
        user_id=callback.from_user.id,
        current_state="feedback_reply_input",
        feedback_reply_user_id=user_id
    )

    await callback.message.answer("Введите ваш ответ на отзыв:")
    await callback.answer()


async def process_feedback_reply(message: Message):
    user_data = db.get_user_data(message.from_user.id)
    if not user_data or user_data['current_state'] != "feedback_reply_input":
        return

    target_user_id = user_data.get("feedback_reply_user_id")

    if target_user_id:
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=f"📩 Ответ на ваш отзыв:\n\n{message.text}"
            )
            await message.answer("✅ Ваш ответ отправлен пользователю!")
        except Exception as e:
            await message.answer("❌ Не удалось отправить ответ. Пользователь, возможно, заблокировал бота.")

    db.update_user_data(
        user_id=message.from_user.id,
        current_state=None,
        feedback_reply_user_id=None
    )


@dp.message()
async def support_handler(message: Message):
    id_user = message.from_user.id
    support_status = db.get_field('users', id_user, 'support_status')
    if support_status == 1:
        try:
            kb_admin = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Ответить", callback_data=f"answer_{message.from_user.id}")],
                [InlineKeyboardButton(text="❌ Удалить", callback_data=f"close_{message.from_user.id}")]
            ])
            await bot.send_message(chat_id=SUPPORT_CHAT_ID,
                                   text=f"Сообщение от пользователя {message.from_user.full_name} (ID: {message.from_user.id}):\n\n{message.text}\n",
                                   reply_markup=kb_admin)
            await message.answer("Ваше сообщение отправлено в поддержку. Ожидайте ответа!")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")
    elif support_status == 2:
        try:
            kb_answer = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Ответить", callback_data="support")]
            ])
            await bot.send_message(chat_id=support_id_user, text=f"Ответ от поддержки:\n\n{message.text}",
                                   reply_markup=kb_answer)
            await message.answer(f"Сообщение отправлено пользователю с ID {support_id_user}.")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")
    db.update_field('users', id_user, 'support_status', 0)


@dp.callback_query()
async def start_call(callback: CallbackQuery):
    id_user = callback.from_user.id
    if callback.data == 'new_message':
        db.clear_user_data(callback.from_user.id)
        db.update_user_data(
            user_id=callback.from_user.id,
            current_state="platform_selection"
        )
        await callback.message.edit_text("Выберите платформу для рассылки:", reply_markup=platform_keyboard)
    if callback.data == 'support':
        db.update_field('users', id_user, 'support_status', 1)
        await callback.answer('Введите сообщение для поддержки')
        db.update_user_data(
            user_id=callback.from_user.id,
            current_state="support_answer_input"
        )
    if callback.data == 'clear':
        db.clear_user_data(callback.from_user.id)
        await callback.message.edit_text("Главное меню:", reply_markup=kb_main)
    if callback.data == 'back_to_platform':
        db.update_user_data(
            user_id=callback.from_user.id,
            current_state="platform_selection"
        )
        await callback.message.edit_text("Выберите платформу для рассылки:", reply_markup=platform_keyboard)
    if callback.data.startswith('answer_'):
        support_id_user = callback.data.split('_')[1]
        await callback.answer('Введите ответ пользователю')
        db.update_field('users', id_user, 'support_status', 2)
    if callback.data == 'delete_msg':
        await callback.message.delete()
    await bot.answer_callback_query(callback.id)


async def send_scheduled_messages():
    while True:
        try:
            # Отправка сообщений в Telegram (остается без изменений)
            tg_messages = db.get_telegram_messages_to_send()
            for msg in tg_messages:
                try:
                    reply_markup = None
                    if msg.get('buttons'):
                        keyboard = []
                        for btn in msg['buttons']:
                            if 'url' in btn:
                                keyboard.append([InlineKeyboardButton(text=btn['text'], url=btn['url'])])
                            elif 'callback_data' in btn:
                                keyboard.append(
                                    [InlineKeyboardButton(text=btn['text'], callback_data=btn['callback_data'])])
                        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

                    if msg.get('image'):
                        image_path = images_dir / msg['image']
                        with open(image_path, 'rb') as photo:
                            try:
                                await bot.send_photo(
                                    chat_id=msg['chat_id'],
                                    photo=types.BufferedInputFile(photo.read(), filename=msg['image']),
                                    caption=msg['text'],
                                    parse_mode=ParseMode.HTML,
                                    reply_markup=reply_markup
                                )
                            except Exception as e:
                                print(f"Ошибка отправки фото в Telegram: {e}")
                                photo.seek(0)
                                await bot.send_photo(
                                    chat_id=msg['chat_id'],
                                    photo=types.BufferedInputFile(photo.read(), filename=msg['image']),
                                    caption=msg['text'],
                                    reply_markup=reply_markup
                                )
                    else:
                        try:
                            await bot.send_message(
                                chat_id=msg['chat_id'],
                                text=msg['text'],
                                parse_mode=ParseMode.HTML,
                                reply_markup=reply_markup
                            )
                        except:
                            await bot.send_message(
                                chat_id=msg['chat_id'],
                                text=msg['text'],
                                reply_markup=reply_markup
                            )
                except Exception as e:
                    print(f"Ошибка отправки сообщения в Telegram: {e}")

            # Отправка сообщений в Discord с кнопками
            discord_messages = db.get_discord_messages_to_send()
            async with aiohttp.ClientSession() as session:
                for msg in discord_messages:
                    try:
                        content = re.sub(r'<[^>]+>', '', msg['text'])

                        # Формируем текстовые ссылки для всех кнопок
                        if msg.get('buttons'):
                            links = []
                            for btn in msg['buttons']:
                                if 'url' in btn:
                                    links.append(f"[{btn['text']}]({btn['url']})")
                                elif 'callback_data' in btn and btn['callback_data'].startswith('user_feedback_'):
                                    user_id = btn['callback_data'].split('_')[2]
                                    links.append(
                                        f"[{btn['text']}](https://t.me/TimerSendMsgBot?start=feedback_{user_id})")

                            if links:
                                content += "\n\n" + " | ".join(links)

                        # Отправка сообщения
                        if msg.get('image'):
                            image_path = images_dir / msg['image']
                            with open(image_path, 'rb') as f:
                                form_data = aiohttp.FormData()
                                form_data.add_field('content', content)
                                form_data.add_field('file', f, filename=msg['image'])
                                await session.post(msg['webhook'], data=form_data)
                        else:
                            await session.post(msg['webhook'], json={"content": content})

                    except Exception as e:
                        print(f"Ошибка отправки в Discord: {e}")

        except Exception as e:
            print(f"Ошибка в расписании: {e}")

        await asyncio.sleep(60)


async def on_startup(dispatcher: Dispatcher):
    await restore_user_sessions()
    print("Бот успешно запущен!")


async def restore_user_sessions():
    try:
        active_users = db.get_active_sessions()
        for user_id, state in active_users:
            try:
                print(f'Восстановлен пользователь: {user_id}')
            except Exception as e:
                print(f"Не удалось уведомить пользователя {user_id}: {e}")
    except Exception as e:
        print(f"Ошибка при восстановлении сессий: {e}")


async def main():
    asyncio.create_task(send_scheduled_messages())
    dp.startup.register(on_startup)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())