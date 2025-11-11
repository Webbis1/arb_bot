import logging
import sys
from dotenv import load_dotenv
import os

load_dotenv()



def setup_logging():
    """Настройка логирования один раз при старте приложения"""
    root_logger = logging.getLogger()
    
    root_logger.handlers.clear()
    
    class ColorFormatter(logging.Formatter):
        # Более тонкая настройка цветов
        TIME_COLOR = "\033[38;5;245m"      # Светло-серый
        NAME_COLOR = "\033[38;5;39m"       # Яркий синий
        LEVEL_COLORS = {
            logging.DEBUG: "\033[38;5;51m",    # Яркий голубой
            logging.INFO: "\033[38;5;46m",     # Яркий зеленый
            logging.WARNING: "\033[38;5;226m", # Яркий желтый
            logging.ERROR: "\033[38;5;196m",   # Яркий красный
            logging.CRITICAL: "\033[38;5;201m", # Яркий фиолетовый
        }
        MESSAGE_COLOR = "\033[97m"         # Ярко-белый
        RESET = "\033[0m"
        
        def format(self, record):
            level_color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
            
            time_part = f"{self.TIME_COLOR}{self.formatTime(record, self.datefmt)}{self.RESET}"
            name_part = f"{self.NAME_COLOR}{record.name}{self.RESET}"
            level_part = f"{level_color}{record.levelname}{self.RESET}"
            message_part = f"{self.MESSAGE_COLOR}{record.getMessage()}{self.RESET}"
            
            return f"{time_part} - {name_part} - {level_part} - {message_part}"
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = ColorFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    
setup_logging()



api_keys = {
    'binance': {
        'api_key': os.getenv('BINANCE_API_KEY'),
        'api_secret': os.getenv('BINANCE_API_SECRET'),
    },
    'okx': {
        'api_key': os.getenv('OKX_API_KEY'),
        'api_secret': os.getenv('OKX_API_SECRET'),
        'password': os.getenv('OKX_PASSWORD'),
    },
    'bitget': {
        'api_key': os.getenv('BITGET_API_KEY'),
        'api_secret': os.getenv('BITGET_API_SECRET'),
        'password': os.getenv('BITGET_PASSWORD'),
        'options': {
            'createMarketBuyOrderRequiresPrice': False,
        },
    },
    'kucoin': {
        'api_key': os.getenv('KUCOIN_API_KEY'),
        'api_secret': os.getenv('KUCOIN_API_SECRET'),
        'password': os.getenv('KUCOIN_PASSWORD'),
    },
    'htx': {
        'api_key': os.getenv('HTX_API_KEY'),
        'api_secret': os.getenv('HTX_API_SECRET'),
    }
}