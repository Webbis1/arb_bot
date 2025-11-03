from dotenv import load_dotenv
import os

load_dotenv()

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