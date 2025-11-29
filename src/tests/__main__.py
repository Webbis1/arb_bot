from abc import abstractmethod
from typing import Optional, Any

from core.interfaces import Exchange
from core.models import Coin
from core.protocols import BalanceSubscriber, PriceSubscriber
from core.models.types import COIN_ID, DESTINATION, COIN_NAME, AMOUNT
from core.interfaces.Exceptions import ExchangeConnectionError
from core.interfaces import ExFactory
from infrastructure.ExFactory import ExFactory as ExFactoryImpl
import asyncio
from asyncio import Condition
import ccxt.pro as ccxtpro
import logging
import traceback

from app.config import api_keys as API

from core.services.Mapper import Mapper
from infrastructure.Exchenges.kucoin import KucoinExchange

logger = logging.getLogger(__name__)

class ExchangeService(BalanceSubscriber, PriceSubscriber):
    def __init__(self, ex: Exchange):
        self.ex = ex
        self.logger = logging.getLogger(f'ExchangeService.{ex.name}')
        
    def __hash__(self) -> int:
        hash_str = 'ExchangeService' + str(self.ex.name)
        return hash(hash_str)
        
    async def on_balance_update(self, coin: COIN_ID, balance: float) -> None:
        coin_name = self.ex.coins.inverse.get(coin)
        self.logger.info(f"Balance was updated: Exchange = {self.ex.name}, Coin ID = {coin}, Coin Name = {coin_name}, Balance = {balance}")
        
    async def start_balance_observe(self):
        await self.ex.subscribe_balance(self)
        self.logger.info(f'Balance observe was started: Exchange = {self.ex.name}')
        
    async def stop_balance_observe(self):
        await self.ex.unsubscribe_balance(self)
        self.logger.info(f'Balance observe was stoped: Exchange = {self.ex.name}')
        
    async def on_price_update(self, coin: int, value: float) -> None:
        pass
        #self.logger.info(f'Price was updated: Exchange = {self.ex.name}, Coin ID = {coin}, Value = {value}')
        
    async def start_price_observe(self):
        await self.ex.subscribe_price(self)
        self.logger.info(f'Price observe was started: Exchange = {self.ex.name}')
        
    async def stop_price_observe(self):
        await self.ex.unsubscribe_price(self)
        self.logger.info(f'Price observe was stoped: Exchange = {self.ex.name}')
        
    async def sell(self, coin_id: COIN_ID, quantity: float, usdt_name: str = 'USDT'):
        self.logger.info(f'Selling Coin Id = {coin_id} on Exchange = {self.ex.name} is started')
        
        try:
            await self.ex.sell(coin_id, quantity)
        except Exception as e:
            self.logger.error(f'Selling Coin Id = {coin_id} on Exchange = {self.ex.name} error: {e} ')
        
    async def buy(self, coin_id: COIN_ID, quantity: float, usdt_name: COIN_NAME = 'USDT'):
        self.logger.info(f'Buying Coin Id = {coin_id} on Exchange = {self.ex.name} is started')   
        
        try:     
            await self.ex.buy(coin_id, quantity)
        except Exception as e:
            self.logger.error(f'Buying Coin Id = {coin_id} on Exchange = {self.ex.name} error: {e} ')
        
    async def withdraw(self, coin_name: str, chain: str, amount: float, ex_destination: DESTINATION , tag: str = ''):
        self.logger.info(f'Withdraw from Exchange {self.ex.name} to Exchange {ex_destination.name} is started')
        
        try:
            await self.ex.withdraw(coin_name, chain, amount, ex_destination, tag)
        except Exception as e:
            self.logger.error(f'Withdraw from Exchange {self.ex.name} to Exchange {ex_destination.name} error: {e}')
        
        
async def main():
    try:
        async with ExFactoryImpl(API) as factory:
            print("ExFactory successfully initialized, exchanges connected, and balances checked.")
            
            mapper: Mapper = Mapper() 
            
            await mapper.generate_data(factory.values())
            
            for ex in factory.values():
                ex.set_coins_by_mapper(mapper.get_coin_name_id_for_ex(ex.name))
            
            tasks = [asyncio.create_task(ex.start(mapper.get_coin_name_id_for_ex(ex.name))) for ex in factory.values()]
            
            
            ### Подписка ###
            balance_subscribers_tasks = []
            price_subscribers_tasks = []
            
            for ex in factory.values():                
                ex_service = ExchangeService(ex)
                                
                balance_subscribers_tasks.append(asyncio.create_task(ex_service.start_balance_observe()))
                price_subscribers_tasks.append(asyncio.create_task(ex_service.start_price_observe()))                 
            
                
            await asyncio.gather(*balance_subscribers_tasks, *price_subscribers_tasks)
            
            #await asyncio.sleep(10)            
            
            ### Продажа (Bitget - БВ, Okx - БВ, Kucoin - БВ, HTX - БВ) ###    
            # for ex in factory.values():
            #     if (ex.name == 'htx'):                
            #         ex_service = ExchangeService(ex)                    
            #         coin_name = 'BTC'
                    
            #         if (coin_id := mapper.get_coinId_by_name_for_ex(ex.name, coin_name)):    
            #             await ex_service.sell(coin_id, 0.00004776)
            #         else:
            #             print(f'Монета {coin_name} не найдена в mapper для биржы {ex.name}')
            
            
            ### Покупка (Bitget - в USDT, Okx - в USDT, Kucoin - БВ, Htx - USDT) ###
            # for ex in factory.values():
            #     if (ex.name == 'htx'):
            #         ex_service = ExchangeService(ex)
            #         coin_name = 'BTC'
            #         if coin_id := mapper.get_coinId_by_name_for_ex(ex.name, coin_name):
            #             await ex_service.buy(coin_id, 5.0)
            #         else:
            #             print(f'Монета {coin_name} не найдена в mapper для биржы {ex.name}')
            
            
            ### Перевод ###
            for ex in factory.values():
                if (ex.name == 'bitget'):
                    ex_service = ExchangeService(ex)
                    ex_destination_name = 'kucoin'    
                    
                    coin_name = 'USDT'                
                    
                    if (ex_destination := factory.get_exchange_obj_by_name(ex_destination_name)):      
                        if coin_id := mapper.get_coinId_by_name_for_ex(ex.name, coin_name):
                            if coin := mapper.get_best_coin_transfer(ex.name, ex_destination_name, coin_id):                                
                                if coin_data := mapper.get_coin_name_chain_from_ex_by_address(coin.address, ex_destination): 
                                    print(f'COIN DATA FROM MAPPER: {coin_data} Address: {coin.address}')                         
                                    await ex_service.withdraw(coin_data[0], coin_data[1], 12, ex_destination)
                                
                            else: 
                                print(f'Невозможно перевести монету {coin_id} из биржы {ex.name} на биржу {ex_destination_name}')
                                
                        else:
                            print(f'Не удалось получить монету {coin_name} на бирже {ex.name}')
                            
                    else:
                        print(f"Неизвестная биржа назначения перевода: {ex_destination_name}")    
            
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
            
            
            
    except ExchangeConnectionError as e:
        print(f"Ошибка подключения к биржам: {e}")
    except KeyboardInterrupt:
        print("Программа остановлена пользователем")
    except Exception as e:
        traceback.print_exc()

        print(f"Другая ошибка: {e}")
    
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(e)