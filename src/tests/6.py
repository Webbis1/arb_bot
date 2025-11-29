import asyncio
import ccxt.async_support as ccxt
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def get_required_env(key: str) -> str:
    """Получить переменную окружения или выбросить исключение"""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value

async def test_htx_connection():
    """Тестируем подключение к HTX"""
    
    config = {
        'apiKey': get_required_env('HTX_API_KEY'),
        'secret': get_required_env('HTX_API_SECRET'),
        'sandbox': False,
        'enableRateLimit': True,
        'options': {
            'createMarketBuyOrderRequiresPrice': False,
            'defaultType': 'spot',
        },
    }
    
    exchange = None
    try:
        # Создаем экземпляр биржи
        exchange = ccxt.htx(config)
        
        print("🔄 Подключаемся к HTX...")
        
        # Загружаем рынки
        markets = await exchange.load_markets()
        print(f"✅ Успешно загружено {len(markets)} торговых пар")
        
        # Пробуем получить баланс
        print("🔄 Получаем баланс...")
        balance = await exchange.fetch_balance()
        total_balance = {k: v for k, v in balance['total'].items() if v > 0}
        print(f"💰 Баланс: {total_balance}")
        
        # Пробуем получить тикер для BTC/USDT
        print("🔄 Получаем тикер BTC/USDT...")
        ticker = await exchange.fetch_ticker('BTC/USDT')
        print(f"📊 BTC/USDT: {ticker['last']} USDT")
        
        # Пробуем получить адрес депозита для USDT
        print("🔄 Получаем адрес депозита USDT...")
        try:
            deposit_address = await exchange.fetch_deposit_address('USDT')
            print(f"🏦 Адрес депозита USDT: {deposit_address}")
        except Exception as e:
            print(f"⚠️ Ошибка получения адреса: {e}")
            
        print("✅ Все тесты пройдены успешно!")
        
    except ccxt.AuthenticationError as e:
        print(f"❌ Ошибка аутентификации: {e}")
    except ccxt.ExchangeNotAvailable as e:
        print(f"🔧 Биржа недоступна: {e}")
    except ccxt.NetworkError as e:
        print(f"🌐 Сетевая ошибка: {e}")
    except ccxt.ExchangeError as e:
        print(f"💢 Ошибка биржи: {e}")
    except Exception as e:
        print(f"💥 Неизвестная ошибка: {e}")
        
    finally:
        # Всегда закрываем соединение
        if exchange:
            print("🔄 Закрываем соединение...")
            await exchange.close()
            print("✅ Соединение закрыто")

async def main():
    """Основная функция"""
    print("🚀 Запуск теста подключения к HTX")
    print("=" * 50)
    
    await test_htx_connection()
    
    print("=" * 50)
    print("🏁 Тест завершен")

if __name__ == "__main__":
    # Запускаем тест
    asyncio.run(main())