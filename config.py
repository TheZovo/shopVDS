from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
import logging


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


load_dotenv()
logger.debug(f"Переменные окружения: {os.environ.get('BOT_TOKEN')=}, {os.environ.get('RETURN_URL')=}")

class Config(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    ADMIN_IDS: str = os.getenv("ADMIN_IDS")
    YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID")
    YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY")
    RETURN_URL: str = os.getenv("RETURN_URL", "https://t.me/thezovotestbot")
    EXCHANGE_API_KEY : str = os.getenv("EXCHANGE_API_KEY")
    CRYPTO_API_KEY : str = os.getenv("CRYPTO_API_KEY")

    @property
    def admin_ids(self):
        """separator is comma by default"""
        if not self.ADMIN_IDS or self.ADMIN_IDS.strip() == "":
            return []
        admin_ids = [x.strip() for x in self.ADMIN_IDS.split(',') if x.strip()]
        return list(map(int, admin_ids))

config = Config()