import argparse
import asyncio
import logging

from bidict import bidict

from core.interfaces import ExFactory
from core.interfaces.Dto import BuyCommission, ExchangeDict, SellCommission
from core.interfaces.Exceptions import ExchangeConnectionError
from core.models import Coin, CoinPair, Commission
from core.services.Analytics.Analyst import Analyst
from core.services.Analytics.Brain import Brain
from infrastructure.ExFactory import ExFactory as ExFactoryImpl
from .config import api_keys as API
# from core import ExFactory, ExchangeConnectionError, Coin

logger = logging.getLogger('analyst')
async def main():
    try:
        async with ExFactoryImpl(API) as factory:
            logger.info("ExFactory successfully initialized, exchanges connected, and balances checked.")
            
            
            _commission: Commission = {}
            _coin_list: CoinPair = bidict()
            sell_commissions: SellCommission = {}
            buy_commissions: BuyCommission = {}
            
            exchenges: ExchangeDict = factory.items() # type: ignore
            
            analyst: Analyst = Analyst( exchenges, _coin_list, sell_commissions, buy_commissions)
            brain: Brain = Brain(analyst, _commission, _coin_list)
            # port: Port = Port(factory, ROUTES)


            # observers = []

                    
            # for ex in factory:
            #     if ex.id == 'okx':
            #         observers.append(OkxObserver(ex))
            #     else:
            #         observers.append(RegularObserver(ex)) 
            
            # pr = TestSubscriber(observers)
            
            # observer_task = asyncio.create_task(run_observers_with_graceful_shutdown(observers))

            # await asyncio.sleep(2)  # ждем 2 секунды

            # await observer_task      

    except ExchangeConnectionError as e:
        logger.error(f"Ошибка подключения к биржам: {e}")
    except KeyboardInterrupt:
        logger.info("Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"Другая ошибка: {e}")

if __name__ == "__main__":
    
    asyncio.run(main())