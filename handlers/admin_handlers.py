from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram import F
import logging
import re
import sqlite3
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.bot import DefaultBotProperties 

from states.states import FSMStates
from functions.functions import update_user_balance
from functions.functions import add_product
from keyboards.keyboards import get_admin_keyboard, main_keyboard
from config import config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
admin_router = Router()

# Проверка на администратора
async def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


@admin_router.message(F.text == "🛠 Добавить товар")
async def add_product_handler(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции.")
        return

    logger.info(f"Админ {message.from_user.id} нажал кнопку 'Добавить товар'")
    
    await state.set_state(FSMStates.waiting_for_product_data)
    await message.answer("Введите товар в формате:\n`ip:login:pass:cores:ram:ssd:geo:cost`")


@admin_router.message(FSMStates.waiting_for_product_data)
async def process_product_data(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции.")
        return

    logger.info(f"Админ {message.from_user.id} отправил товар: {message.text}")

    products = message.text.strip().splitlines()

    added_count = 0
    for product in products:
        match = re.match(r"^(.*?):(.*?):(.*?):(\d+):(\d+):(\d+):([A-Za-z]+):([\d.]+)$", product)
        if match:
            ip, login, password, cores, ram, ssd, geo, price = match.groups()

            logger.info(f"Добавление товара: {ip}, {login}, {password}, {cores}, {ram}, {ssd}, {geo}, {price}")

            try:
                add_product(ip, login, password, int(cores), int(ram), int(ssd), geo.upper(), float(price))
                added_count += 1
            except Exception as e:
                logger.error(f"Ошибка при добавлении товара: {e}")
                await message.answer(f"Произошла ошибка при добавлении товара: {e}")
                continue
        else:
            await message.answer(f"Неверный формат товара: {product}")
            logger.warning(f"Неверный формат товара: {product}")

    if added_count > 0:
        await message.answer(f"Добавлено товаров: {added_count}")
    else:
        await message.answer("Не удалось добавить товары. Проверьте формат ввода.")

    await state.clear()


@admin_router.message(F.text == "💳 Изменить баланс пользователя")
async def change_balance_handler(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции.")
        return

    logger.info(f"Админ {message.from_user.id} нажал кнопку 'Изменить баланс'")

    await message.answer("Введите ID пользователя и новый баланс через пробел. Пример: `123456789 100.50`")

    await state.set_state(FSMStates.waiting_for_balance_update)


@admin_router.message(FSMStates.waiting_for_balance_update)
async def process_balance_update(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции.")
        return


    logger.info(f"Админ {message.from_user.id} отправил запрос на изменение баланса: {message.text}")


    try:
        user_id_str, new_balance_str = message.text.split()
        user_id = int(user_id_str)
        new_balance = float(new_balance_str)

        update_user_balance(user_id, new_balance)
        await message.answer(f"Баланс пользователя {user_id} был успешно обновлён на {new_balance}$.")
    except ValueError:
        await message.answer("Неверный формат. Пожалуйста, введите ID пользователя и новый баланс через пробел. Пример: `123456789 100.50`")
    except Exception as e:
        await message.answer(f"Произошла ошибка при обновлении баланса: {e}")

    await state.clear()


@admin_router.message(F.text =="🛠 Удалить товар")
async def delete_product_handler(message: Message, state: FSMContext):
    """Запрос на удаление товара."""
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции.")
        return


    logger.info(f"Админ {message.from_user.id} нажал кнопку 'Удалить товар'")


    await state.set_state(FSMStates.waiting_for_product_id)
    await message.answer("Введите ID товаров через запятую(пример: 1, 2, 3), которые вы хотите удалить: ")


@admin_router.message(FSMStates.waiting_for_product_id)
async def process_deleting_products(message: Message, state: FSMContext):
    """Удаление товаров по ID и перенумерация товаров."""
    ids_text = message.text.strip()

    try:
        product_ids = [int(id.strip()) for id in ids_text.split(',')]

        conn = sqlite3.connect('vds_shop.db')
        cursor = conn.cursor()

        deleted_count = 0
        for product_id in product_ids:
            cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
            product = cursor.fetchone()

            if product:
                cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
                deleted_count += 1

        conn.commit()

        if deleted_count > 0:
            await message.answer(f"Удалено {deleted_count} товара(ов).")
        else:
            await message.answer("Товары с указанными ID не найдены.")



    except ValueError:
        await message.answer("Пожалуйста, введите корректные ID товаров (целые числа, разделенные запятой).")
    except Exception as e:
        await message.answer(f"Произошла ошибка при удалении товаров: {e}")


    await message.answer("Выберите действие:", reply_markup=get_admin_keyboard())

    await state.clear()


@admin_router.message(F.text =="📝 Список товаров")
async def list_products_handler(message: Message):
    """Выводит список всех товаров в базе данных."""
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции.")
        return


    logger.info(f"Админ {message.from_user.id} запросил список товаров")


    conn = sqlite3.connect('vds_shop.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    


    if products:
        product_list = "\n".join([f"{item[0]}:{item[1]}:{item[2]}:{item[3]}:{item[4]}:{item[5]}:{item[6]}:{item[7]}:{item[8]}"
                                for item in products])
        await message.answer(f"Список товаров:\n\n{product_list}")
    else:
        await message.answer("В базе данных нет товаров.")
    
@admin_router.message(F.text == "⬅️ Назад")
async def back_to_main_menu(message: Message, state: FSMContext):
    """Возвращаем пользователя в основное меню."""
    await message.answer("Вы вернулись в основное меню.", reply_markup=main_keyboard(message.from_user.id))
    
    await state.clear()


@admin_router.message(F.text == "➕ Добавить промокод")
async def add_promo_code_handler(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    await message.answer("Введите промокод в формате: `код:скидка:лимит`")

    await state.set_state(FSMStates.get_promo)


@admin_router.message(FSMStates.get_promo)
async def get_promo_code_handler(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции.")
        return

    try:
        code, discount, usage_limit = message.text.split(":")
        conn = sqlite3.connect("vds_shop.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO promo_codes (code, discount, usage_limit) VALUES (?, ?, ?)", (code, float(discount), int(usage_limit)))
        conn.commit()
        await message.answer("Промокод добавлен.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@admin_router.message(F.text == "Рассылка")
async def broadcast_message(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции.")
        return

    await message.answer("Введите текст для рассылки:")

    # Переходим к ожиданию текста рассылки
    await state.set_state(FSMStates.waiting_for_broadcast)


@admin_router.message(FSMStates.waiting_for_broadcast)
async def process_broadcast_message(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    broadcast_message = message.text.strip()
    
    # Сохраняем сообщение в FSMContext
    await state.update_data(broadcast_message=broadcast_message)
    
    # Отправляем сообщение всем пользователям
    # Получаем всех пользователей из базы данных
    conn = sqlite3.connect('vds_shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users")
    users = cursor.fetchall()
    
    if users:
        for user in users:
            user_id = user[0]
            try:
                await message.bot.send_message(user_id, broadcast_message)
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
    
    # Подтверждение администратору
    await message.answer("Рассылка завершена.")
    await state.clear()