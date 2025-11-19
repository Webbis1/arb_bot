import logging
import sys
from dotenv import load_dotenv
import os

from core.models.dto.ExchangeParams import ExchangeParams, DEFAULT_PARAMS

load_dotenv()

class TradingLogger(logging.Logger):
    """Кастомный логгер для торговых операций"""
    
    BUY = 24
    SELL = 25
    SUCCESS_LEVEL = 35
    
    def __init__(self, name):
        super().__init__(name)
        
        logging.addLevelName(self.BUY, "BUY")
        logging.addLevelName(self.SELL, "SELL")
        logging.addLevelName(self.SUCCESS_LEVEL, "SUCCESS")
    
    def buy(self, symbol, price, quantity, *args, **kwargs):
        """Логирование покупки с деталями"""
        message = f"BUY ORDER: {symbol} | Price: {price} | Quantity: {quantity}"
        if self.isEnabledFor(self.BUY):
            self._log(self.BUY, message, args, **kwargs)
    
    def sell(self, symbol, price, quantity, *args, **kwargs):
        """Логирование продажи с деталями"""
        message = f"SELL ORDER: {symbol} | Price: {price} | Quantity: {quantity}"
        if self.isEnabledFor(self.SELL):
            self._log(self.SELL, message, args, **kwargs)
    
    def success(self, message, *args, **kwargs):
        """Логирование успешных операций"""
        if self.isEnabledFor(self.SUCCESS_LEVEL):
            self._log(self.SUCCESS_LEVEL, message, args, **kwargs)

# Устанавливаем кастомный логгер
logging.setLoggerClass(TradingLogger)

def setup_trading_logging():
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    class TradingFormatter(logging.Formatter):
        LEVEL_COLORS = {
            logging.DEBUG: "\033[38;5;51m",
            logging.INFO: "\033[38;5;46m",
            TradingLogger.BUY: "\033[38;5;42m",        # Зеленый для BUY
            TradingLogger.SELL: "\033[38;5;208m",      # Оранжевый для SELL
            logging.WARNING: "\033[38;5;226m",
            TradingLogger.SUCCESS_LEVEL: "\033[38;5;82m", # Яркий зеленый для SUCCESS
            logging.ERROR: "\033[38;5;196m",
            logging.CRITICAL: "\033[38;5;201m",
        }
        RESET = "\033[0m"
        
        def format(self, record):
            level_color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
            
            time_part = f"\033[38;5;245m{self.formatTime(record, self.datefmt)}{self.RESET}"
            name_part = f"\033[38;5;39m{record.name}{self.RESET}"
            level_part = f"{level_color}{record.levelname}{self.RESET}"
            message_part = f"\033[97m{record.getMessage()}{self.RESET}"
            
            return f"{time_part} - {name_part} - {level_part} - {message_part}"
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = TradingFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    
setup_trading_logging()


def get_required_env(key: str) -> str:
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable {key} is not set")
    return value

api_keys: dict[str, ExchangeParams] = {
    'okx': {
        'apiKey': get_required_env('OKX_API_KEY'),
        'secret': get_required_env('OKX_API_SECRET'),
        'password': get_required_env('OKX_PASSWORD'),
        'sandbox': False,
        'enableRateLimit': True,
    },
    'bitget': {
        'apiKey': get_required_env('BITGET_API_KEY'),
        'secret': get_required_env('BITGET_API_SECRET'),
        'password': get_required_env('BITGET_PASSWORD'),
        'sandbox': False,
        'enableRateLimit': True,
        'options': {
            'createMarketBuyOrderRequiresPrice': False,
        },
    },
    'kucoin': {
        'apiKey': get_required_env('KUCOIN_API_KEY'),
        'secret': get_required_env('KUCOIN_API_SECRET'),
        'password': get_required_env('KUCOIN_PASSWORD'),
        'sandbox': False,
        'enableRateLimit': True,
    },
    'htx': {
        'apiKey': get_required_env('HTX_API_KEY'),
        'secret': get_required_env('HTX_API_SECRET'),
        'sandbox': False,
        'enableRateLimit': True,
        'options': {
            'createMarketBuyOrderRequiresPrice': False,
        },
    }
}