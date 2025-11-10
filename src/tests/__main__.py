from abc import abstractmethod
from typing import Optional, Any

from core.interfaces import Exchange
from core.models import Coin
from core.protocols import BalanceSubscriber, PriceSubscriber
from core.models.types import COIN_ID, DESTINATION, COIN_NAME, amount
from core.interfaces.Exceptions import ExchangeConnectionError
from core.interfaces import ExFactory
from infrastructure.ExFactory import ExFactory as ExFactoryImpl
import asyncio
from asyncio import Condition
import ccxt.pro as ccxtpro
import logging

from app.config import api_keys as API

from core.services.Mapper import Mapper

class ExchangeService(BalanceSubscriber, PriceSubscriber):
    def __init__(self, ex: Exchange):
        self.ex = ex
        self.logger = logging.getLogger(f'ExchangeService.{ex.name}')
        
    async def on_balance_update(self, coin: Coin, balance: float) -> None:
        print(f"Balance was updated: Exchange = {self.ex.name}, Coin = {coin}, Balance = {balance}")
        
    async def start_balance_observe(self):
        await self.ex.subscribe_balance(self)
        print(f'Balance observe was started: Exchange = {self.ex.name}')
        
    async def stop_balance_observe(self):
        await self.ex.unsubscribe_balance(self)
        print(f'Balance observe was stoped: Exchange = {self.ex.name}')
        
    async def on_price_update(self, coin: int, value: float) -> None:
        print(f'Price was updated: Exchange = {self.ex.name}, Coin ID = {coin}, Value = {value}')
        
    async def start_price_observe(self):
        await self.ex.subscribe_price(self)
        print(f'Price observe was started: Exchange = {self.ex.name}')
        
    async def stop_price_observe(self):
        await self.ex.unsubscribe_price(self)
        print(f'Price observe was stoped: Exchange = {self.ex.name}')
        
    async def sell(self, coin_id: int, quantity: float, usdt_name: str = 'USDT'):
        await self.ex.sell(coin_id, quantity)
        
        
async def main():
    try:
        async with ExFactoryImpl(API) as factory:
            print("ExFactory successfully initialized, exchanges connected, and balances checked.")
            
            mapper: Mapper = Mapper() 
            
            await mapper.generate_data(factory.values())
            
            # balance_subscribers_tasks = []
            # price_subscribers_tasks = []
            
            # for ex in factory.values():
            #     ex_service = ExchangeService(ex)
                                
            #     balance_subscribers_tasks.append(asyncio.create_task(ex_service.start_balance_observe()))
            #     price_subscribers_tasks.append(asyncio.create_task(ex_service.start_price_observe()))                 
            
                
            # await asyncio.gather(*balance_subscribers_tasks, *price_subscribers_tasks)
            
            
            tasks = [asyncio.create_task(ex.start(mapper.get_coin_name_id_for_ex(ex.name))) for ex in factory.values()]
            
            try:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
                
                for task in done:
                    if task.exception():
                        print(f"Task failed: {task.exception()}")
                        

                for task in pending:
                    task.cancel()
                    
            except KeyboardInterrupt:
                print("Received interrupt signal, shutting down...")
                
                # Отменяем все задачи
                for task in tasks:
                    task.cancel()
                    
                # for bst in balance_subscribers_tasks:
                #     bst.cancel()
                    
                # for pct in price_subscribers_tasks:
                #     pct.cancel()
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
                print("Shutdown complete")
            
            
    except ExchangeConnectionError as e:
        print(f"Ошибка подключения к биржам: {e}")
    except KeyboardInterrupt:
        print("Программа остановлена пользователем")
    except Exception as e:
        print(f"Другая ошибка: {e}")
    
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(e)