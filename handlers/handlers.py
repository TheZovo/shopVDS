import asyncio
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram import F
import sqlite3
import logging

import requests

from config import config
from states.states import FSMStates, TopUpStates
from handlers.admin_handlers import admin_router
from handlers.main_handlers import main_router
from keyboards.keyboards import get_payment_check_keyboard, main_keyboard, back_to_main, profile_inline_keyboard, product_buy_keyboard, get_payment_inline_keyboard, create_products_keyboard
from functions.functions import apply_promo_code, check_and_update_payment, get_flag, get_user_balance, update_user_balance, create_payment


router = Router()

router.include_routers(admin_router, main_router)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "top_up")
async def topup_handler(callback: CallbackQuery):
    await callback.message.answer("Выберите способ пополнения:", reply_markup=get_payment_inline_keyboard())
    await callback.answer()

@router.callback_query(F.data == "topup_yoo")
async def topup_yoo(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите сумму пополнения в RUB:")
    await state.set_state(TopUpStates.waiting_for_rub_amount)
    await callback.answer()

@router.message(TopUpStates.waiting_for_rub_amount)
async def process_yoo_amount(message: Message, state: FSMContext):
    logger.debug(f"Получено сообщение от пользователя {message.from_user.id}: '{message.text}'")
    
    try:
        if not message.text or message.text.strip() == "":
            logger.warning("Получен пустой ввод")
            await message.answer("Введите корректную сумму (например, 100 или 100.50).")
            return

        amount_str = message.text.strip().replace(',', '.')
        amount_rub = float(amount_str)
        
        if amount_rub < 2:
            await message.answer("Минимальная сумма пополнения — 2 RUB. Введите сумму еще раз.")
            return

        payment_data, amount_usd = create_payment(amount_rub, message.from_user.id)
        
        if "confirmation" not in payment_data or "confirmation_url" not in payment_data["confirmation"]:
            raise Exception("Не удалось получить ссылку для оплаты от YooKassa.")

        payment_url = payment_data["confirmation"]["confirmation_url"]
        payment_id = payment_data["id"]
        
        logger.debug(f"Создан платеж с ID: {payment_id}")
        
        await message.answer(
            f"💵 Сумма: {amount_rub:.2f} RUB ({amount_usd:.2f} USD)\n\n"
            f"🔗{payment_url}\n\n"
            f"После оплаты нажмите 'Проверить оплату'",
            disable_web_page_preview=True,
            reply_markup=get_payment_check_keyboard(payment_id)
        )
    except ValueError as ve:
        logger.error(f"Ошибка преобразования суммы: {ve}")
        await message.answer("Введите корректную сумму (например, 100 или 100.50).")
    except Exception as e:
        logger.error(f"Произошла ошибка при создании платежа: {e}")
        await message.answer(
            f"Произошла ошибка: {str(e)}\nПопробуйте снова.",
            reply_markup=back_to_main()
        )
    finally:
        await state.clear()

@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment(callback: CallbackQuery):
    payment_id = callback.data.split("_")[2]
    
    try:
        payment_updated = check_and_update_payment(payment_id)
        
        conn = sqlite3.connect('vds_shop.db')
        cursor = conn.cursor()
        cursor.execute("SELECT status, telegram_id, amount_usd FROM payments WHERE payment_id = ?", (payment_id,))
        payment = cursor.fetchone()
        conn.close()
        
        if not payment:
            await callback.message.edit_text(
                "❌ Платеж не найден в базе данных.\nПопробуйте создать новый платеж.",
                reply_markup=back_to_main()
            )
            await callback.answer()
            return

        status, telegram_id, amount_usd = payment
        
        if payment_updated:
            balance = get_user_balance(callback.from_user.id)
            await callback.message.edit_text(
                f"✅ Оплата на {amount_usd:.2f} USD успешно подтверждена!\n"
                f"Ваш баланс: {balance:.2f} USD",
                reply_markup=back_to_main()
            )
        elif status == "succeeded":
            balance = get_user_balance(callback.from_user.id)
            await callback.message.edit_text(
                f"✅ Оплата на {amount_usd:.2f} USD уже была подтверждена ранее!\n"
                f"Ваш баланс: {balance:.2f} USD",
                reply_markup=back_to_main()
            )
        elif status == "canceled":
            await callback.message.edit_text(
                "❌ Платеж был отменен.\nПопробуйте создать новый платеж.",
                reply_markup=back_to_main()
            )
        else:
            current_text = callback.message.text
            new_text = f"⏳ Платеж на {amount_usd:.2f} USD еще не подтвержден (статус: {status}).\nПопробуйте проверить позже."
            if current_text != new_text:
                await callback.message.edit_text(
                    new_text,
                    reply_markup=get_payment_check_keyboard(payment_id)
                )
            else:
                await callback.answer("Платеж еще не подтвержден. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Ошибка при проверке платежа: {e}")
        await callback.message.edit_text(
            f"❌ Произошла ошибка при проверке платежа: {str(e)}.\nПопробуйте снова.",
            reply_markup=back_to_main()
        )
    await callback.answer()


@router.callback_query(F.data == "topup_crypto")
async def topup_crypto(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите сумму для пополнения в USD:")
    await state.set_state(TopUpStates.waiting_for_crypto_amount)

@router.message(TopUpStates.waiting_for_crypto_amount)
async def topup_crypto_amount(message: Message, state: FSMContext):
    try:
        amount_usd = float(message.text)
        if amount_usd <= 0:
            await message.answer("Введите верное значение.")
            return
        url = "https://pay.crypt.bot/api/createInvoice"
        headers = {
            "Crypto-Pay-API-Token": config.CRYPTO_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "asset": "USDT",
            "amount": amount_usd,
            "description": "Пополнение баланса",
            "paid_btn_name": "openBot",
            "paid_btn_url": config.RETURN_URL,
            "payload": str(message.from_user.id),
            "allow_anonymous": False
        }
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        if data.get('ok'):
            invoice_id = data["result"]["invoice_id"]
            pay_url = data["result"]["pay_url"]

            conn = sqlite3.connect("vds_shop.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO crypto_payments (invoice_id, telegram_id, amount, status) VALUES (?, ?, ?, ?)", 
                          (invoice_id, message.from_user.id, amount_usd, "pending"))
            conn.commit()
            conn.close()
            
            await message.answer(f"Оплатите по ссылке: {pay_url}", 
                               reply_markup=get_payment_check_keyboard(f"crypto_{invoice_id}"))
        else:
            await message.answer("Ошибка при создании платежа.")
            print(f"Ошибка API: {data}")

    except ValueError:
        await message.answer("Введите корректную сумму.")
    await state.clear()

@router.callback_query(F.data.startswith("check_crypto_payment_"))
async def check_crypto_payment(callback: CallbackQuery):
    print(f"Получен callback_data: {callback.data}")
    invoice_id = callback.data.split("_")[3]
    await callback.message.answer("Проверяем статус платежа...")
    payment_status = await check_crypto_payment_status(invoice_id)
    
    if payment_status == "paid":
        await callback.message.answer("Платеж успешно подтвержден! Баланс пополнен.")
    elif payment_status == "pending":
        await callback.message.answer("Платеж еще не подтвержден. Пожалуйста, подождите.")
    else:
        await callback.message.answer("Ошибка при проверке платежа. Попробуйте позже.")
    await callback.answer()

async def check_crypto_payment_status(invoice_id: str) -> str:
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": config.CRYPTO_API_KEY}
    
    try:
        print(f"Проверка статуса платежа для invoice_id: {invoice_id}")
        response = requests.get(url, headers=headers)
        print(f"Статус код ответа API: {response.status_code}")
        data = response.json()
        print(f"Ответ API: {data}")
        
        if not data.get("ok"):
            logging.error(f"Ошибка API: {data}")
            return "error"
            
        invoices = data.get("result", {}).get("items", [])
        print(f"Получено инвойсов: {len(invoices)}")
        
        for invoice in invoices:
            if str(invoice.get("invoice_id")) == str(invoice_id):
                status = invoice.get("status")
                print(f"Найден инвойс с статусом: {status}")
                if status == "paid":
                    conn = sqlite3.connect("vds_shop.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE crypto_payments SET status = ? WHERE invoice_id = ?", 
                                 ("paid", invoice_id))
                    cursor.execute("SELECT telegram_id, amount FROM crypto_payments WHERE invoice_id = ?", 
                                 (invoice_id,))
                    result = cursor.fetchone()
                    if result:
                        telegram_id, amount = result
                        cursor.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", 
                                     (amount, telegram_id))
                        conn.commit()
                        print(f"Баланс пользователя {telegram_id} пополнен на {amount}")
                    else:
                        logging.error(f"Не найдены данные платежа для invoice_id: {invoice_id}")
                    conn.close()
                return status
        return "pending"
        
    except Exception as e:
        logging.error(f"Ошибка при проверке платежа: {str(e)}")
        return "error"

# Можно оставить старую функцию для периодической проверки всех платежей
async def check_crypto_payments():
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": config.CRYPTO_API_KEY}
    conn = sqlite3.connect("vds_shop.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT invoice_id, telegram_id, amount FROM crypto_payments WHERE status = ?", ("pending",))
        pending_payments = cursor.fetchall()
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if not data.get("ok"):
            logging.error("Ошибка при получении счетов: %s", data)
            return
            
        invoices = data.get("result", [])
        
        if not isinstance(invoices, list):
            logging.error("Непредвиденный формат данных invoices: %s", invoices)
            return
            
        for invoice_id, user_id, amount in pending_payments:
            for invoice in invoices:
                if not isinstance(invoice, dict):
                    continue
                if str(invoice.get("invoice_id")) == str(invoice_id) and invoice.get("status") == "paid":
                    cursor.execute("UPDATE crypto_payments SET status = ? WHERE invoice_id = ?", 
                                 ("paid", invoice_id))
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", 
                                 (amount, user_id))
                    conn.commit()
                    
    except Exception as e:
        logging.error("Ошибка в массовой проверке платежей: %s", str(e))
    finally:
        conn.close()

        



@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: CallbackQuery, state: FSMContext):
    balance = get_user_balance(callback.from_user.id)
    text = f"Ваш ID: {callback.from_user.id}\nВаш баланс: {balance:.2f} USD"
    await callback.message.edit_text(text, reply_markup=profile_inline_keyboard)
    await callback.answer()
    await state.clear()
    


@router.callback_query(F.data == "products_back")
async def products_back(callback: CallbackQuery, state: FSMContext):
    keyboard = create_products_keyboard(page=0)
    await callback.message.edit_text("Выберите товар:", reply_markup=keyboard)
    await callback.answer()
    await state.clear()


@router.callback_query(F.data.startswith("page_"))
async def page_navigation(callback_query: CallbackQuery):
    page = int(callback_query.data.split("_")[1])
    keyboard = create_products_keyboard(page)
    await callback_query.message.edit_text("Выберите товар:", reply_markup=keyboard)
    await callback_query.answer()


@router.callback_query(F.data.startswith("product_"))
async def product_details(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect('vds_shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ip, login, password, cores, ram, ssd, geo, price FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if product:
        ip, login, password, cores, ram, ssd, geo, price = product
        product_details = (
            f"Товар #{product_id}:\n"
            f"ОЗУ: {ram}GB\n"
            f"SSD: {ssd}GB\n"
            f"Ядра: {cores}\n"
            f"Гео: {geo}\n"
            f"Цена: {price} $"
        )
        await callback.message.edit_text(product_details, reply_markup=product_buy_keyboard(product_id))
    await callback.answer()

@router.callback_query(F.data.startswith("buy_"))
async def buy_product(callback_query: CallbackQuery):
    product_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id
    
    conn = sqlite3.connect('vds_shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT ip, login, password, cores, ram, ssd, geo, price FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    
    if not product:
        await callback_query.message.edit_text("Этот товар уже куплен.")
        return
    
    ip, login, password, cores, ram, ssd, geo, price = product
    price = apply_promo_code(user_id, price)
    balance = get_user_balance(user_id)
    
    if balance >= price:
        update_user_balance(user_id, -price)
        cursor.execute(
            "INSERT INTO purchases (telegram_id, ip, login, password, cores, ram, ssd, geo, price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, ip, login, password, cores, ram, ssd, geo, price)
        )
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        flag = get_flag(geo)
        await callback_query.message.edit_text(
            f"✅ <b>Покупка успешна!</b>\n\n"
            f"🔹 <b>GEO</b> {geo, flag}\n"
            f"🔹 <b>IP:</b> {ip}\n"
            f"🔹 <b>Логин:</b> {login}\n"
            f"🔹 <b>Пароль:</b> {password}\n"
            f"🔹 <b>{cores} Ядер | {ram}GB RAM | {ssd}GB SSD</b>**\n"
            f"💰 <b>Цена:</b> {price}$", reply_markup=back_to_main()
        )
    else:
        await callback_query.message.edit_text(
            "❌ **Недостаточно средств.**\nПополните баланс, чтобы купить этот товар.",
            reply_markup=back_to_main()
        )
    conn.commit()
    await callback_query.answer()

@router.message(FSMStates.waiting_for_promo_code)
async def process_promo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    promo_code = message.text.strip()
    
    conn = sqlite3.connect('vds_shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT discount, usage_limit FROM promo_codes WHERE code = ?", (promo_code,))
    promo = cursor.fetchone()
    
    if promo:
        discount, usage_limit = promo
        if usage_limit > 0:
            cursor.execute("UPDATE users SET promo_code = ? WHERE telegram_id = ?", (promo_code, user_id))
            conn.commit()
            await message.answer(f"✅ Промокод {promo_code} активирован! Скидка: {discount}%.")
        else:
            await message.answer("❌ Этот промокод уже исчерпан.")
    else:
        await message.answer("❌ Промокод недействителен.")
    await state.clear()

@router.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Приветствую в VDS Market! Выберите действие:",
        reply_markup=main_keyboard(callback.from_user.id)
    )
    await callback.answer()
    await state.clear()