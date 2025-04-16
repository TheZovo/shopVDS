from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram import F
import sqlite3

from config import config
from keyboards.keyboards import main_keyboard, profile_inline_keyboard, create_products_keyboard, get_admin_keyboard, back_to_main
from functions.functions import get_user_balance, create_user, get_user_purchase_count
from states.states import FSMStates

main_router = Router()


@main_router.message(Command("start"))
async def start_handler(message: Message):
    create_user(message.from_user.id)
    await message.answer("Приветсутсвую в VDS Market! Выберите действие:", reply_markup=main_keyboard(message.from_user.id))

@main_router.message(F.text == "Профиль")
async def profile_handler(message: Message):
    balance = get_user_balance(message.from_user.id)
    purchase_count = get_user_purchase_count(message.from_user.id)

    text = (f"👤 <b>Ваш профиль</b>\n"
        f"🆔 ID: <i>{message.from_user.id}</i>\n"
        f"💰 Баланс: <i>{balance:.2f}$</i>\n"
        f"🛒 Куплено товаров: <i>{purchase_count}</i>")
    await message.answer(text, reply_markup=profile_inline_keyboard)


@main_router.message(F.text == "📜 Товары")
async def products_handler(message: Message):
    page = 0
    keyboard = create_products_keyboard(page)
    await message.answer("""🖥 Дедики в наличии

⚡️ Для покупки выберите интересующий дедик и удобный вам способ оплаты. После оплаты вы мгновенно получаете данные от дедика.

🔥 Срок гарантии - 25 Дней (Ежедневный биллинг)

🛍 Пополнения ежедневно, ориентировочно в 21:00
""", reply_markup=keyboard)


@main_router.message(F.text == "Информация")
async def products_handler(message: Message):
    await message.answer("По любым вопросам писать - @romauuka")


@main_router.message(F.text == "Мои VDS")
async def my_vds_handler(message: Message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect("vds_shop.db")
    cursor = conn.cursor()

    cursor.execute("SELECT ip, login, password, cores, ram, ssd, geo, price FROM purchases WHERE telegram_id = ?", (user_id,))
    purchases = cursor.fetchall()



    if purchases:
        purchase_list = "\n\n".join([
            f"🔹 <b>IP:</b> {ip}\n"
            f"🔹 <b>Логин:</b> {login}\n"
            f"🔹 <b>Пароль:</b> {password}\n"
            f"🔹 <b>{cores} Ядер | {ram}GB RAM | {ssd}GB SSD</b>\n"
            f"💰 <b>Цена:</b> {price}$"
            for ip, login, password, cores, ram, ssd, geo, price in purchases
        ])
        
        await message.answer(f"🖥 <b>Ваши купленные VDS:</b>\n\n{purchase_list}")
    else:
        await message.answer("❌ У вас нет купленных VDS.")

@main_router.message(F.text == "Промокод")
async def promo_code_handler(message: Message, state: FSMContext):
    await message.answer("Введите промокод:", reply_markup=back_to_main())
    await state.set_state(FSMStates.waiting_for_promo_code)



@main_router.message(F.text == "🔧 Админ-панель")
async def admin_panel_handler(message: Message):
    telegram_id = message.from_user.id
    if telegram_id in config.admin_ids:
        keyboard = get_admin_keyboard()
        await message.answer("Добро пожаловать в админ-панель!", reply_markup=keyboard)
    else:
        await message.answer("У вас нет доступа к админ-панели.")