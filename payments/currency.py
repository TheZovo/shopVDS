import requests
from config import config


EXCHANGE_API_KEY = config.EXCHANGE_API_KEY

def get_usd_exchange_rate():
    """Получает актуальный курс USD/RUB."""
    try:
        response = requests.get(f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/latest/RUB")
        data = response.json()
        return 1 / data["conversion_rates"]["USD"]  # RUB → USD
    except Exception as e:
        print(f"Ошибка получения курса валют: {e}")
        return 0.011
