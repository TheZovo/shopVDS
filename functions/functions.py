import sqlite3
import logging
import uuid
import requests
from requests.auth import HTTPBasicAuth
from config import config
from payments.currency import get_usd_exchange_rate

YOOKASSA_URL = "https://api.yookassa.ru/v3/payments"

logger = logging.getLogger(__name__)


def create_db():
    conn = sqlite3.connect("vds_shop.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            balance REAL DEFAULT 0,
            promo_code TEXT DEFAULT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT,
            login TEXT,
            password TEXT,
            cores INTEGER,
            ram INTEGER,
            ssd INTEGER,
            geo TEXT,  -- добавлено поле geo
            price REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            ip TEXT,
            login TEXT,
            password TEXT,
            cores INTEGER,
            ram INTEGER,
            ssd INTEGER,
            geo TEXT,
            price REAL,
            purchase_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            discount REAL,
            usage_limit INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            payment_id TEXT UNIQUE,
            amount_rub REAL,
            amount_usd REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crypto_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT UNIQUE,
            telegram_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "geo" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN geo TEXT DEFAULT 'N/A'")  # Добавляем geo, если его нет
    conn.commit()






def create_user(telegram_id):
    conn = sqlite3.connect('vds_shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM users WHERE telegram_id = ?
    ''', (telegram_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute('''
            INSERT INTO users (telegram_id, balance) VALUES (?, 0)
        ''', (telegram_id,))
        conn.commit()




def get_user(telegram_id):
    conn = sqlite3.connect('vds_shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT telegram_id, balance FROM users WHERE telegram_id = ?
    ''', (telegram_id,))
    user = cursor.fetchone()


    if user:
        return {"telegram_id": user[0], "balance": user[1]}
    return None


def get_user_balance(telegram_id):
    conn = sqlite3.connect("vds_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    print(f"Текущий баланс пользователя {telegram_id}: {result[0]}")
    return result[0] if result else 0

def update_user_balance(telegram_id, amount):
    conn = sqlite3.connect("vds_shop.db")
    cursor = conn.cursor()
    
    try:
        with conn:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (amount, telegram_id))
        conn.commit()
        print(f"Баланс пользователя {telegram_id} обновлен на {amount}.")
    except sqlite3.OperationalError as e:
        print(f"Ошибка при обновлении баланса: {e}")
    finally:
        conn.close()





COUNTRY_FLAGS = {
    "US": "🇺🇸", "RU": "🇷🇺", "DE": "🇩🇪", "FR": "🇫🇷",
    "GB": "🇬🇧", "NL": "🇳🇱", "CA": "🇨🇦", "AU": "🇦🇺",
    "IT": "🇮🇹", "ES": "🇪🇸", "PL": "🇵🇱", "BR": "🇧🇷",
    "IN": "🇮🇳", "JP": "🇯🇵", "CN": "🇨🇳", "KR": "🇰🇷",
    "MX": "🇲🇽", "AR": "🇦🇷", "ZA": "🇿🇦", "NG": "🇳🇬",
    "EG": "🇪🇬", "TR": "🇹🇷", "SA": "🇸🇦", "AE": "🇦🇪",
    "ID": "🇮🇩", "TH": "🇹🇭", "PH": "🇵🇭", "SG": "🇸🇬",
    "NZ": "🇳🇿", "FI": "🇫🇮", "SE": "🇸🇪", "NO": "🇳🇴",
    "DK": "🇩🇰", "CH": "🇨🇭", "BE": "🇧🇪", "AT": "🇦🇹",
    "PL": "🇵🇱", "PT": "🇵🇹", "GR": "🇬🇷", "CZ": "🇨🇿",
    "RO": "🇷🇴", "HU": "🇭🇺", "SK": "🇸🇰", "BG": "🇧🇬",
    "UA": "🇺🇦", "KR": "🇰🇷", "MY": "🇲🇾", "VN": "🇻🇳",
    "KW": "🇰🇼", "QA": "🇶🇦", "OM": "🇴🇲", "KW": "🇰🇼",
    "IE": "🇮🇪", "IS": "🇮🇸", "LK": "🇱🇰", "MD": "🇲🇩"
}


def get_flag(geo):
    return COUNTRY_FLAGS.get(geo, "🏳️")


def get_user_purchase_count(user_id: int) -> int:
    conn = sqlite3.connect("vds_shop.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM purchases WHERE telegram_id = ?", (user_id,))
    count = cursor.fetchone()[0]


    return count


def apply_discount(user_id, price):
    conn = sqlite3.connect("vds_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT promo_code FROM users WHERE telegram_id = ?", (user_id,))
    promo_code = cursor.fetchone()
    
    if promo_code and promo_code[0]:
        cursor.execute("SELECT discount FROM promo_codes WHERE code = ?", (promo_code[0],))
        discount = cursor.fetchone()
        if discount:
            price *= (1 - discount[0] / 100)
    
    return round(price, 2)

def apply_promo_code(user_id, price):
    conn = sqlite3.connect('vds_shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT promo_code FROM users WHERE telegram_id = ?", (user_id,))
    promo_code = cursor.fetchone()
    
    if promo_code and promo_code[0]:
        cursor.execute("SELECT discount, usage_limit FROM promo_codes WHERE code = ?", (promo_code[0],))
        promo = cursor.fetchone()
        if promo:
            discount, usage_limit = promo
            new_price = price - (price * discount / 100)
            
            # Уменьшаем количество оставшихся использований
            cursor.execute("UPDATE promo_codes SET usage_limit = usage_limit - 1 WHERE code = ?", (promo_code[0],))
            
            # Если лимит исчерпан, удаляем промокод
            if usage_limit - 1 <= 0:
                cursor.execute("DELETE FROM promo_codes WHERE code = ?", (promo_code[0],))
            
            # Удаляем промокод у пользователя после использования
            cursor.execute("UPDATE users SET promo_code = NULL WHERE telegram_id = ?", (user_id,))
            
            conn.commit()
            print(f"Применен промокод: {promo_code[0]}, новая цена: {new_price}")
            return new_price
    print(f"Промокод не найден или не применим. Цена остается без изменений: {price}")
    return price






def create_payment(amount_rub, user_id):
    """Создает платеж в YooKassa и сохраняет его в БД"""
    idempotence_key = str(uuid.uuid4())
    headers = {
        "Content-Type": "application/json",
        "Idempotence-Key": idempotence_key
    }
    
    usd_rate = get_usd_exchange_rate()
    amount_usd = round(amount_rub / usd_rate, 2)

    data = {
        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": config.RETURN_URL},
        "capture": True,
        "description": f"Пополнение баланса на {amount_usd} USD для @{user_id}",
        "metadata": {
            "telegram_id": str(user_id),
            "amount_usd": f"{amount_usd:.2f}"
        }
    }

    logger.debug(f"Создание платежа: amount_rub={amount_rub}, user_id={user_id}, idempotence_key={idempotence_key}")

    try:
        response = requests.post(
            YOOKASSA_URL,
            json=data,
            headers=headers,
            auth=HTTPBasicAuth(config.YOOKASSA_SHOP_ID, config.YOOKASSA_SECRET_KEY)
        )
        
        logger.debug(f"Статус ответа YooKassa: {response.status_code}")
        logger.debug(f"Ответ YooKassa: {response.text}")

        if response.status_code not in (200, 201):
            error_msg = response.json().get('description', 'Неизвестная ошибка')
            logger.error(f"Ошибка YooKassa: {error_msg}")
            raise Exception(f"Ошибка создания платежа: {error_msg}")

        payment_data = response.json()
        payment_id = payment_data['id']
        
        conn = sqlite3.connect('vds_shop.db')
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO payments (telegram_id, payment_id, amount_rub, amount_usd, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, payment_id, amount_rub, amount_usd, 'pending'))
            conn.commit()
            logger.debug(f"Платеж {payment_id} успешно сохранен в БД")
        except sqlite3.IntegrityError as e:
            logger.error(f"Ошибка при сохранении в БД (вероятно, дубликат payment_id): {e}")
            raise
        except sqlite3.Error as e:
            logger.error(f"Ошибка базы данных: {e}")
            raise
        finally:
            conn.close()

        return payment_data, amount_usd

    except Exception as e:
        logger.error(f"Общая ошибка в create_payment: {e}")
        raise


def check_and_update_payment(payment_id):
    url = f"https://api.yookassa.ru/v3/payments/{payment_id}"
    try:
        response = requests.get(
            url,
            auth=(config.YOOKASSA_SHOP_ID, config.YOOKASSA_SECRET_KEY)
        )
        logger.debug(f"Проверка платежа {payment_id}: статус {response.status_code}, ответ: {response.text}")
        
        if response.status_code == 404:
            logger.error(f"Платеж {payment_id} не найден на сервере YooKassa")
            return False
            
        payment_data = response.json()
    except requests.RequestException as e:
        logger.error(f"Ошибка запроса к YooKassa для платежа {payment_id}: {e}")
        return False
    
    conn = sqlite3.connect('vds_shop.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT telegram_id, amount_usd, status 
        FROM payments 
        WHERE payment_id = ?
    ''', (payment_id,))
    payment = cursor.fetchone()
    
    if not payment:
        logger.error(f"Платеж {payment_id} не найден в локальной БД")
        conn.close()
        return False
    
    telegram_id, amount_usd, current_status = payment
    

    if payment_data.get("status") == "succeeded" and current_status != "succeeded":

        update_user_balance(telegram_id, amount_usd)
        
        cursor.execute('''
            UPDATE payments 
            SET status = ? 
            WHERE payment_id = ?
        ''', ('succeeded', payment_id))
        conn.commit()
        conn.close()
        logger.debug(f"Платеж {payment_id} обновлен до succeeded, баланс пользователя {telegram_id} пополнен на {amount_usd}")
        return True
        
    elif payment_data.get("status") != current_status:
        cursor.execute('''
            UPDATE payments 
            SET status = ? 
            WHERE payment_id = ?
        ''', (payment_data.get("status"), payment_id))
        conn.commit()
        logger.debug(f"Статус платежа {payment_id} обновлен в БД до {payment_data.get('status')}")
    
    conn.close()
    return False

def add_product(ip, login, password, cores, ram, ssd, geo, price):
    try:
        conn = sqlite3.connect("vds_shop.db")
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO products (ip, login, password, cores, ram, ssd, geo, price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ip, login, password, cores, ram, ssd, geo, price))

        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при добавлении товара: {e}")
        raise e



def get_products(offset: int, limit: int):
    conn = sqlite3.connect('vds_shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, cores, ram, ssd, geo, price FROM products LIMIT ? OFFSET ?", (limit, offset))
    products = cursor.fetchall()


    return products
