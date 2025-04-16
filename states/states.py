from aiogram.fsm.state import StatesGroup, State

class FSMStates(StatesGroup):
    waiting_for_product_data = State()  # Ожидание ввода данных о товаре
    waiting_for_balance_update = State()  # Ожидание ввода нового баланса пользователя
    waiting_for_product_data = State()  # Ожидание ввода данных о товаре
    waiting_for_balance_update = State()  # Ожидание ввода нового баланса пользователя
    waiting_for_user_id_balance = State()  # Ожидание ввода ID пользователя и баланса
    waiting_for_product_id = State() # Ожидание ввода ID товара
    get_promo = State()
    waiting_for_promo_code = State()
    waiting_for_broadcast = State()

class TopUpStates(StatesGroup):
    waiting_for_rub_amount = State()
    waiting_for_crypto_amount = State()