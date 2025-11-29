from abc import abstractmethod
from bidict import bidict
from typing import Optional, Any

import ccxt

from core.interfaces import Exchange
# from core.interfaces.Dto import CoinDict, Coins, Destination
# from core.models import Coin
from core.models.Coins import  Coin
from core.protocols import BalanceSubscriber, PriceSubscriber
from core.models.types import COIN_ID, DESTINATION, COIN_NAME, AMOUNT, CHAIN


import asyncio
from asyncio import Condition
import ccxt.pro  as ccxtpro
import logging

from core.services.Mapper import Mapper


# этот класс ничего не должен знать о COIN_ID
class CcxtExchange(Exchange):
    
    def __init__(self, name: str, instance: ccxtpro.Exchange):
        super().__init__(name)
        self.__ex: ccxtpro.Exchange = instance
        self._is_running = False
        
        self.balance_sudscribers: set[BalanceSubscriber] = set()
        self.price_subscribers: set[PriceSubscriber] = set()
        self.__coin_locks: dict[COIN_NAME, asyncio.Lock] = {}
        self.logger = logging.getLogger(f'CcxtExchange.{name}')
    
    @property
    def instance(self) -> ccxtpro.Exchange:
        return self.__ex
    
    async def _is_trading_with_usdt(self, markets, coin_name):
        try:
            for market in markets:
                if (market['base'] == coin_name and 
                    market['quote'] == 'USDT' and 
                    market['active'] and market['symbol'] == f'{coin_name}/USDT'):
                    return True
            return False
        except Exception as e:
            print(f"Ошибка при проверке торговых пар: {e}")
            return False
    
    async def start(self) -> None:
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
            
            new_balances = await self.instance.fetch_balance()
            await self._process_balance_update(new_balances)
            
            coin_names = list(coins.keys())
            if "USDT" in coin_names:
                coin_names.remove("USDT")
            
            self.logger.info(f"[{self.name}] Запуск мониторинга...")
            
            # Создаем задачи с возможностью отмены
            tickers_task = asyncio.create_task(self.watch_tickers(coin_names))
            
            await asyncio.sleep(5)
            self.logger.info("EX is load")
            
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
                        
                        await self._price_notify(coin_name, price)
                    
                except asyncio.CancelledError:
                    self.logger.debug(f"Observation cancelled for {self.name}")
                    break
                except Exception as e:
                    self.logger.error(f"[{self.name}] Error&&&: {e}")
                    await asyncio.sleep(1)
                        
        except Exception as e:
            self.logger.exception(f"Fatal error: {e}")
    
    async def _price_notify(self, coin_name: str, value: float):
        for sub in self.price_subscribers:
            try:
                asyncio.create_task(sub.on_price_update(coin_name, value))
            except Exception as e:
                self.logger.exception(f"Error notifying price subscriber: {e}")

                
    async def subscribe_price(self, sub: PriceSubscriber):
        self.price_subscribers.add(sub)
        
    async def unsubscribe_price(self, sub: PriceSubscriber):
        self.price_subscribers.discard(sub)
    
    # Balance observer
    async def _balance_notify(self, coin_name: str, value: float):
        for sub in self.balance_sudscribers:
            try:
                asyncio.create_task(sub.on_balance_update(coin_name, value))
            except Exception as e:
                self.logger.exception(f"Error notifying price subscriber: {e}")
    
    async def _process_balance_update(self, new_balances: dict[str, Any]) -> None:
        try:
            for coin_name, new_balance in new_balances['total'].items():
                if coin_name not in self.coins: 
                    #self.logger.exception(f"[{self.name}] - coin: {coin_name}")
                    continue
                    
                # coin_id: COIN_ID = self.coins[coin_name]
                
                if (new_balance < 10e-6):
                    new_balance = 0
                    
                async with self.__coin_locks[coin_name]:
                    if (self.wallet[coin_name] != new_balance):
                        self.wallet[coin_name] = new_balance
                        asyncio.create_task(self._balance_notify(coin_name, new_balance))
                        
        except Exception as e:
            self.logger.exception(f"Error processing balance update: {e}")
    
    async def _balance_observe(self) -> None:
        try:    
            while self._is_running:
                try:
                    balance_update = await self.instance.watch_balance()
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
    
    async def get_balance(self) -> dict[COIN_NAME, AMOUNT]:
        return self.wallet
    
    #Trader
    
    async def buy(self, coin_name: str, usdt_quantity: float | None = None, usdt_name: str = 'USDT'):
        # if coin_id not in self.coins.inverse:
        #     self.logger.warning(f"coin - {coin_id} not support for buy")
            
        if usdt_quantity is None:
            async with self.__coin_locks[usdt_name]:
                usdt_quantity = self.wallet[usdt_name]
        
        # coin_name: COIN_NAME = self.coins.inverse[coin_id]
        
        if coin_name == usdt_name:
            self.logger.warning("Buy usdt/usdt")
            return None
        
        # self.logger.info(f'Exchange = {self.name}, createMarkerOrder = {self.instance.has['createMarketOrder']}, createMarketBuyOrderRequiresPrice = {self.instance.options.get('createMarketBuyOrderRequiresPrice')}')

        if (self.instance.has['createMarketOrder']):
            symbol = f"{coin_name}/{usdt_name}"
            
            try:
                order = await self.instance.create_order(symbol, 'market', 'buy', usdt_quantity)
                filled_amount = order.get('filled')
                cost = order.get('cost')
                self.logger.buy(symbol, cost or "", filled_amount or "")
                return order
            except Exception as e:
                self.logger.error(f"Buy order failed for {symbol}: {e}")
                return None
            
        else:
            self.logger.warning(f"Market sell is not supported on exchange {self.instance.id}")
    
    async def sell(self, coin_name: str, quantity: float | None = None, usdt_name: str = 'USDT'):
        if coin_name == usdt_name:
            self.logger.warning("Sell usdt/usdt")
            return None
        
        if quantity is None:
            async with self.__coin_locks[coin_name]:
                quantity = self.wallet[coin_name]
        
        # self.logger.info(f'Exchange = {self.name}, createMarkerOrder = {self.instance.has['createMarketOrder']}, createMarketBuyOrderRequiresPrice = {self.instance.options.get('createMarketBuyOrderRequiresPrice')}')
        
        # Можно ли торговать по рыночной цене
        if (self.instance.has['createMarketOrder']):                                 
            symbol = f"{coin_name}/{usdt_name}"
            try:
                order = await self.instance.create_order(symbol, 'market', 'sell', quantity)
                filled_amount = order.get('filled')
                cost = order.get('cost', 0)
                self.logger.sell(symbol, cost or "", filled_amount or "")
                return order
            except Exception as e:
                self.logger.error(f"Sell order failed for {symbol}: {e}")
                return None
        else:
            self.logger.warning(f"Market sell is not supported on exchange {self.name}")
    
    async def get_deposit_address(self, coin_address: str) -> str | None:
        if coin := self.get_coin(coin_address):
            try:       
                address_info = await self.instance.fetch_deposit_address(*self._get_deposit_address_params(coin))
                
                address = None       
                
                if isinstance(address_info, dict):
                    self.logger.info(f'TAGS: {address_info}')
                    address = address_info.get('address')
                    if not address and 'addresses' in address_info:
                        address = address_info['addresses'][0].get('address') if address_info['addresses'] else None
                else:
                    address = str(address_info)
                    
                if not address:
                    raise ValueError(f"Адрес не найден в ответе от биржи для {coin.name}")
                    
                return address
            
            except ccxtpro.BadRequest as e:
                error_msg = f"Сеть {coin.network} не поддерживается для {coin.name}"
                self.logger.error(f"{error_msg}: {e}")
                
            except ccxtpro.BaseError as e:
                self.logger.error(f"Ошибка биржи при получении адреса {coin.name}: {e}")
                
            except Exception as e:
                self.logger.error(f"Неожиданная ошибка при получении адреса {coin.name}: {e}")
                
    

        
    
    async def withdraw(self, coin_address: str, amount: float, ex_destination: DESTINATION , tag: str = '') -> bool:    
        if coin := self.get_coin(coin_address):
            if address := await ex_destination.get_deposit_address(coin_address):        
                self.logger.info(f'Withdraw deposit address: {address}')
                    
                params = {
                    'network': coin.network,
                    'chain': coin.network
                }
                
                self.logger.info(f'Withdraw params: {params}')
                
                try:
                    withdraw_result = await self.instance.withdraw(coin.name, amount, address, tag=tag, params=params)
                    self.logger.info(f'Withdraw Result: {withdraw_result}')
                    return True
                except ccxt.InsufficientFunds as e:
                    self.logger.error(f'Недостаточно средств для вывода: {e}')
                    return False
                except ccxt.InvalidAddress as e:
                    self.logger.error(f'Неверный адрес вывода: {e}')
                    return False
                except ccxt.PermissionDenied as e:
                    self.logger.error(f'Нет прав на вывод средств: {e}')
                    return False
                except ccxt.NetworkError as e:
                    self.logger.error(f'Сетевая ошибка: {e}')
                    # Можно попробовать повторить запрос
                    return False
                except ccxt.ExchangeError as e:
                    self.logger.error(f'Ошибка биржи: {e}')
                    return False
                except Exception as e:
                    self.logger.error(f'Неизвестная ошибка при выводе: {e}')
                    return False
            
            else: self.logger.error(f'Cannot fetch deposit address on Exchange = {self.name}, Coin = {coin.name}, Chain = {coin.network}')
        else: self.logger.warning(f"Coin_address - {coin_address} is not supporting")
            
        return False

    async def get_current_coins(self) -> dict[COIN_NAME, set[Coin]]:
        # loge NotImplementedError
        return {}
        
    def set_coins_by_mapper(self, coins: bidict[COIN_NAME, COIN_ID]):
        self.coins = coins
        
    
    def _get_deposit_address_params(self, coin: Coin) -> tuple[COIN_NAME, dict]:
        params = {
            "network": coin.network
        }
        return coin.name, params
        
        
