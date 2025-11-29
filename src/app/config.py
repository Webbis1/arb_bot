import logging
import sys
from dotenv import load_dotenv
import os




load_dotenv()



def get_required_env(key: str) -> str:
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable {key} is not set")
    return value

api_keys: dict[str, dict] = {
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
            # 'createMarketBuyOrderRequiresPrice': False,
            # 'defaultType': 'spot',
        },
        'hostname': 'api-aws.huobi.pro' 
    }
}