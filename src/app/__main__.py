import argparse
import asyncio

from .config import api_keys as API
from core import ExFactory, ExchangeConnectionError, Coin


async def main():
    try:
        async with ExFactory(API) as factory:
            logger.info("ExFactory successfully initialized, exchanges connected, and balances checked.")
            port: Port = Port(factory, ROUTES)


            observers = []

                    
            for ex in factory:
                if ex.id == 'okx':
                    observers.append(OkxObserver(ex))
                else:
                    observers.append(RegularObserver(ex)) 
            
            pr = TestSubscriber(observers)
            
            observer_task = asyncio.create_task(run_observers_with_graceful_shutdown(observers))

            await asyncio.sleep(2)  # ждем 2 секунды

            await observer_task      

    except ExchangeConnectionError as e:
        logger.error(f"Ошибка подключения к биржам: {e}")
    except KeyboardInterrupt:
        logger.info("Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"Другая ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())