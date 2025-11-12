from abc import abstractmethod
from bidict import bidict
from typing import Optional, Any

from core.interfaces import Exchange
# from core.interfaces.Dto import CoinDict, Coins, Destination
from core.models import Coin
from core.protocols import BalanceSubscriber, PriceSubscriber
from core.models.types import COIN_ID, DESTINATION, COIN_NAME, amount


import asyncio
from asyncio import Condition
import ccxt.pro  as ccxtpro
import logging

from core.services.Mapper import Mapper



class CcxtExchange(Exchange):
    
    def __init__(self, name: str, instance: ccxtpro.Exchange):
        super().__init__(name)
        self.__ex: ccxtpro.Exchange = instance
        self._is_running = False
        self.wallet: dict[COIN_ID, amount] = {}
        self.balance_sudscribers: set[BalanceSubscriber] = set()
        self.price_subscribers: set[PriceSubscriber] = set()
        self.__coin_locks: dict[COIN_ID, asyncio.Lock] = {}
        self.logger = logging.getLogger(f'CcxtExchange.{name}')
        self.coins: bidict[COIN_NAME, COIN_ID] = bidict()
        self.usdt_id: COIN_ID
    
    @property
    def instance(self) -> ccxtpro.Exchange:
        return self.__ex
    
    async def _is_trading_with_usdt(self, markets, coin_name):
        try:
            # 2025-11-10 09:12:38,308 - CcxtExchange.bitget - INFO - [bitget] Error: bitget does not have market symbol MITO/USDT
            for market in markets:
                if (market['base'] == coin_name and 
                    market['quote'] == 'USDT' and 
                    market['active'] and market['symbol'] == f'{coin_name}/USDT'):
                    return True
            return False
        except Exception as e:
            print(f"Ошибка при проверке торговых пар: {e}")
            return False
    
    async def start(self, coins: bidict[COIN_NAME, COIN_ID]) -> None:
        if self._is_running: 
            return
        
        self._is_running = True
        try:
            # Инициализация
            # if 370 in coins.inverse:
            #     coins.inverse.pop(370)
            
            self.wallet = {}
            for coin_id in coins.inverse.keys():
                self.wallet[coin_id] = 0.0
                self.__coin_locks[coin_id] = asyncio.Lock()
            
            new_balances = await self.__ex.fetch_balance()
            await self._process_balance_update(new_balances)
            
            coin_names = list(coins.keys())
            coin_names.remove("USDT")
            
            self.logger.info(f"[{self.name}] Запуск мониторинга...")
            
            # Создаем задачи с возможностью отмены
            tickers_task = asyncio.create_task(self.watch_tickers(coin_names))
            balance_task = asyncio.create_task(self._balance_observe())
            
            try:
                # Ждем завершения обеих задач
                await asyncio.gather(tickers_task, balance_task, return_exceptions=True)
            except asyncio.CancelledError:
                self.logger.info(f"[{self.name}] Получен запрос на отмену...")
                self._is_running = False
                await asyncio.sleep(1)
                
                # Отменяем дочерние задачи
                tickers_task.cancel()
                balance_task.cancel()
                # Ждем их корректного завершения
                await asyncio.gather(tickers_task, balance_task, return_exceptions=True)
                raise  # Пробрасываем исключение дальше
                
        except asyncio.CancelledError:
            self.logger.info(f"[{self.name}] Задача отменена")
            raise
        except Exception as e:
            self.logger.error(f"[{self.name}] Error in start: {e}")
        finally:
            # Cleanup
            self._is_running = False
            for coin_id in self.coins.values():
                self.logger.debug(f"[{self.name}]: clear coin {coin_id} in analyst")
                await self._price_notify(coin_id, -10.0)
            self.logger.info(f"[{self.name}] Мониторинг остановлен")
    
    def _get_symbols(self, coin_names: list[COIN_NAME]) -> list[str]:
        return [f"{coin_name}/USDT" for coin_name in coin_names]
    
    async def watch_tickers(self, coin_names: list[COIN_NAME]) -> None:
        self._is_running = True
        try:
            symbols = self._get_symbols(coin_names)

            while self._is_running:
                try:
                    tickers = await self.instance.watch_tickers(symbols)
                    for symbol, ticker in tickers.items():
                        coin_name = symbol.split('/')[0]
                        
                        price = 0 #ticker['last']
                        
                        if (ticker['ask'] is not None):
                            price = ticker['ask']
                            
                        elif (ticker['lastPrice'] is not None):
                            price = ticker['lastPrice']
                            
                        elif (ticker['info']['lastPrice'] is not None):
                            price = ticker['info']['lastPrice']
                            
                        if (price == 0):
                            self.logger.warning(f"There is not fee data for Coin {coin_name} in exchange {self.name}")
                        
                        await self._price_notify(self.coins[coin_name], price)
                    
                except asyncio.CancelledError:
                    self.logger.debug(f"Observation cancelled for {self.name}")
                    break
                except Exception as e:
                    self.logger.error(f"[{self.name}] Error&&&: {e}")
                    await asyncio.sleep(1)
                        
        except Exception as e:
            self.logger.exception(f"Fatal error: {e}")
    
    async def _price_notify(self, coin_id: int, value: float):
        for sub in self.price_subscribers:
            try:
                asyncio.create_task(sub.on_price_update(coin_id, value))
            except Exception as e:
                self.logger.exception(f"Error notifying price subscriber: {e}")

                
    async def subscribe_price(self, sub: PriceSubscriber):
        self.price_subscribers.add(sub)
        
    async def unsubscribe_price(self, sub: PriceSubscriber):
        self.price_subscribers.discard(sub)
    
    # Balance observer
    async def _balance_notify(self, coin_id: COIN_ID, value: float):
        for sub in self.balance_sudscribers:
            try:
                asyncio.create_task(sub.on_balance_update(coin_id, value))
            except Exception as e:
                self.logger.exception(f"Error notifying price subscriber: {e}")
    
    async def _process_balance_update(self, new_balances: dict[str, Any]) -> None:
        try:
            for coin_name, new_balance in new_balances['total'].items():
                if coin_name not in self.coins: 
                    #self.logger.exception(f"[{self.name}] - coin: {coin_name}")
                    continue
                    
                coin_id: COIN_ID = self.coins[coin_name]
                
                if (new_balance < 10e-9):
                    new_balance = 0
                    
                async with self.__coin_locks[coin_id]:
                    if (self.wallet[coin_id] != new_balance):
                        self.wallet[coin_id] = new_balance
                        asyncio.create_task(self._balance_notify(coin_id, new_balance))
                        
        except Exception as e:
            self.logger.exception(f"Error processing balance update: {e}")
    
    async def _balance_observe(self) -> None:
        try:    
            while self._is_running:
                try:
                    balance_update = await self.__ex.watch_balance()
                    await self._process_balance_update(balance_update)
                    
                except asyncio.CancelledError:
                    self.logger.info(f"Observation cancelled for {self.name}")
                    break
                except Exception as e:
                    self.logger.info(f"[{self.name}] Error: {e}")
                    await asyncio.sleep(1)
                        
        except Exception as e:
            self.logger.exception(f"Fatal error: {e}")

    
    async def subscribe_balance(self, sub: BalanceSubscriber):
        self.balance_sudscribers.add(sub)
    
    async def unsubscribe_balance(self, sub: BalanceSubscriber):
        self.balance_sudscribers.discard(sub)
    
    async def get_balance(self) -> dict[COIN_ID, amount]:
        return self.wallet
    
    #Trader
    
    async def buy(self, coin_id: int, usdt_quantity: float, usdt_name: str = 'USDT'):
        coin_name = self.coins.inverse.get(coin_id)
        
        # self.logger.info(f'Exchange = {self.name}, createMarkerOrder = {self.__ex.has['createMarketOrder']}, createMarketBuyOrderRequiresPrice = {self.__ex.options.get('createMarketBuyOrderRequiresPrice')}')

        if (self.__ex.has['createMarketOrder']):
            symbol = f"{coin_name}/{usdt_name}"
            
            try:
                order = await self.__ex.create_order(symbol, 'market', 'buy', usdt_quantity)
                filled_amount = order.get('filled', 0)
                cost = order.get('cost', 0)
                self.logger.info(f"Buy order filled: {filled_amount} {coin_name} for {cost} {usdt_name}")
                return order
            except Exception as e:
                self.logger.error(f"Buy order failed for {symbol}: {e}")
                return None
            
        else:
            self.logger.warning(f"Market sell is not supported on exchange {self.__ex.id}")
    
    async def sell(self, coin_id: int, quantity: float, usdt_name: str = 'USDT'):
        coin_name = self.coins.inverse.get(coin_id)
        
        # self.logger.info(f'Exchange = {self.name}, createMarkerOrder = {self.__ex.has['createMarketOrder']}, createMarketBuyOrderRequiresPrice = {self.__ex.options.get('createMarketBuyOrderRequiresPrice')}')
        
        # Можно ли торговать по рыночной цене
        if (self.__ex.has['createMarketOrder']):                                 
            symbol = f"{coin_name}/{usdt_name}"
            try:
                order = await self.__ex.create_order(symbol, 'market', 'sell', quantity)
                filled_amount = order.get('filled', 0)
                cost = order.get('cost', 0)
                self.logger.info(f"Sell order filled: {filled_amount} {coin_name} for {cost} {usdt_name}")
                return order
            except Exception as e:
                self.logger.error(f"Sell order failed for {symbol}: {e}")
                return None
        else:
            self.logger.warning(f"Market sell is not supported on exchange {self.__ex.id}")
    
    # Courier
    async def get_deposit_address(self, coin: Coin) -> str | None:        
        try:
            coin_name = coin.name
            chain = coin.chain
            
            params = {
                'network': chain,
                'chain': chain
            }
            
            # address_info = await self.__ex.fetchDepositAddressesByNetwork(coin_name) #type: ignore
            address_info = await self.__ex.fetch_deposit_address(coin_name, params)
            
            address = None
            
            # self.logger.critical(f'INFO: {address_info}')
            
            # from pprint import pprint 
            
            # pprint(address_info)
            
            if isinstance(address_info, dict):
                self.logger.info(f'TAGS: {address_info}')
                address = address_info.get('address')
                if not address and 'addresses' in address_info:
                    address = address_info['addresses'][0].get('address') if address_info['addresses'] else None
            else:
                address = str(address_info)
                
            if not address:
                raise ValueError(f"Адрес не найден в ответе от биржи для {coin_name}")
                
            return address
        
        except ccxtpro.BadRequest as e:
            error_msg = f"Сеть {chain} не поддерживается для {coin_name}"
            self.logger.error(f"{error_msg}: {e}")
            return None
        except ccxtpro.BaseError as e:
            self.logger.error(f"Ошибка биржи при получении адреса {coin_name}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при получении адреса {coin_name}: {e}")
            return None
    
    
    async def withdraw(self, coin: Coin, amount: float, ex_destination: DESTINATION , tag: str = '') -> None:
        coin_name = coin.name
        chain = coin.chain
        
        self.logger.critical(chain)
        
        address = await ex_destination.get_deposit_address(coin)
        
        self.logger.info(f'Withdraw deposit address: {address}')
             
        params = {
            'network': chain,
            'chain': chain
        }
        
        self.logger.info(f'Withdraw params: {params}')
        
        try:
            withdraw_result = await self.instance.withdraw(coin_name, amount, address, tag=tag, params=params)
            self.logger.info(f'Withdraw Result: {withdraw_result}')
            
        except Exception as e:
            self.logger.error(f'Withdraw error: {e}')

    async def get_current_coins(self) -> dict[COIN_NAME, set[Coin]]:
        # loge NotImplementedError
        return {}
        
    def set_coins_by_mapper(self, coins: bidict[COIN_NAME, COIN_ID]):
        self.coins = coins