import argparse
import asyncio
import gc
import logging
from typing import ValuesView

from bidict import bidict

from core.interfaces import ExFactory, Exchange
from core.interfaces.Dto import BuyCommission, ExchangeDict, Recommendation, SellCommission
from core.interfaces.Dto.Asset import Asset
from core.interfaces.Exceptions import ExchangeConnectionError
from core.models import Coin, CoinPair, Commission, Deal
from core.models.types import COIN_ID
from core.services.Analytics.Analyst import Analyst
from core.services.Analytics.Brain import Brain
from core.services.Mapper import Mapper
from infrastructure.ExFactory import ExFactory as ExFactoryImpl
from .config import api_keys as API
# from core import ExFactory, ExchangeConnectionError, Coin
from core.services.Execution.Manager import Manager

import sys

logger = logging.getLogger(__name__)

async def printAnal(analyst: Analyst):
    while True:
        deal: Deal | None = await analyst.get_best_deal()
        if deal is not None:
            string: str = str(deal) + "\t" + analyst.mapper.get_coin_name_id_for_ex(deal.departure.name).inverse[deal.coin_id] + f" - coin in dict {len(analyst.coin_list)}"
            logger.info(string)
        
        await asyncio.sleep(2)


async def BrainTest(brain: Brain, exchanges: ValuesView[Exchange], usdt_id: COIN_ID):
    logger.info(f"USDT_ID is {usdt_id}")
    while True:
        for ex in exchanges:
            rec: Recommendation = await brain.analyse(ex, Asset(usdt_id, 100))
            logger.info(f"Recomendation for {ex.name} is {str(rec)}")
            
        await asyncio.sleep(2)

async def main():
    try:
        async with ExFactoryImpl(API) as factory:
            logger.info("ExFactory successfully initialized, exchanges connected, and balances checked.")
            
            
            # exchenges: ExchangeDict = factory.items() #type: ignore 
            
            
            
            mapper: Mapper = Mapper() 
            
            await mapper.generate_data(factory.values())
            
            for ex in factory.values():
                ex.set_coins_by_mapper(mapper.get_coin_name_id_for_ex(ex.name))
            
            tasks = [asyncio.create_task(ex.start(mapper.get_coin_name_id_for_ex(ex.name))) for ex in factory.values()]
            
            analyst: Analyst = Analyst(mapper)
            
            await analyst.start()
            
            brain: Brain = Brain(analyst, mapper)
            
            
            managers: list[Manager] = [Manager(brain, ex) for ex in factory.values()]
            
            manager_tasks = [asyncio.create_task(manager.start()) for manager in managers]
            
            tasks.extend(manager_tasks)
            
            # tasks.append(asyncio.create_task(printAnal(analyst)))
            # tasks.append(asyncio.create_task(BrainTest(brain, factory.values(), mapper.usdt)))
            
            try:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
                
                for task in done:
                    if task.exception():
                        logger.error(f"Task failed: {task.exception()}")
                        

                for task in pending:
                    task.cancel()
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
                
                # Отменяем все задачи
                for task in tasks:
                    task.cancel()
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
                logger.info("Shutdown complete")
            
            # analyst: Analyst = Analyst( exchenges, _coin_list, sell_commissions, buy_commissions)
            # brain: Brain = Brain(analyst, _commission, _coin_list)
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
            
            await asyncio.sleep(5)

    except ExchangeConnectionError as e:
        logger.error(f"Ошибка подключения к биржам: {e}")
    except KeyboardInterrupt:
        logger.info("Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"Другая ошибка: {e}")

if __name__ == "__main__":
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped manually.")
    finally: ...
        # Добавляем небольшой таймаут и запускаем сборщик мусора
        # Это помогает aiohttp закрыть соединения, которые могли быть
        # оставлены в ожидании из-за внутренних механизмов
        # logger.info("Performing final cleanup of asyncio resources...")
        # loop = asyncio.get_event_loop() # Здесь уже будет запущенный цикл, если asyncio.run() завершился
        
        # # Завершаем асинхронные генераторы/итераторы
        # if hasattr(loop, 'shutdown_asyncgens'):
        #     try:
        #         loop.run_until_complete(loop.shutdown_asyncgens())
        #     except Exception as e:
        #         logger.warning(f"Error during shutdown_asyncgens: {e}")

        # # Даем планировщику последний шанс выполнить незавершенные задачи
        # loop.run_until_complete(asyncio.sleep(0.1)) 
        
        # # Принудительная отмена оставшихся задач и небольшой таймаут
        # # Это более мягкий подход, чем в предыдущем варианте, 
        # # но может быть полезен, если остаются висячие задачи.
        # pending_tasks = asyncio.all_tasks(loop=loop)
        # for task in pending_tasks:
        #     if not task.done():
        #         task.cancel()
        # try:
        #     loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
        # except asyncio.CancelledError:
        #     pass # Ожидаемо
        
        # # Последний таймаут перед полным закрытием
        # loop.run_until_complete(asyncio.sleep(0.5)) 
        
        # gc.collect() # Дополнительный сбор мусора

        # logger.info("Application shutdown complete.")