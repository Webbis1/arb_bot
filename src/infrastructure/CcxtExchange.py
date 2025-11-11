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
        if self._is_running: return
        # self.logger.info(coins)
        if 370 in coins.inverse:
            coins.inverse.pop(370)
        
        self.coins = coins
        
        self._is_running = True
        self.wallet = {}
        for coin_id in coins.inverse.keys():
            self.wallet[coin_id] = 0.0
            self.__coin_locks[coin_id] = asyncio.Lock()
        
        coin_names = list(coins.keys())
        coin_names.remove("USDT")
        # coin_names.remove("WAXP")
        
        try:
            self.logger.info(f"[{self.name}] Запуск мониторинга...")
            
            results = await asyncio.gather(
                self.watch_tickers(coin_names),
                self._balance_observe(),
                return_exceptions=True
            )
            
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"[{self.name}] Задача {i} завершилась с ошибкой: {result}")
                else:
                    self.logger.info(f"[{self.name}] Задача {i} успешно завершена")
                    
        except Exception as e:
            self.logger.error(f"[{self.name}] Error in start: {e}")
        finally:
            self._is_running = False
            for coin_id in self.coins.values():
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
                    self.logger.error(f"[{self.name}] Error: {e}")
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
                    self.logger.exception(f"[{self.name}] - coin: {coin_name}")
                    continue
                    
                coin_id: COIN_ID = self.coins[coin_name]
                
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
    
    async def buy(self, coin_name: str, usdt_quantity: float, usdt_name: str = 'USDT'):
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
    
    async def sell(self, coin_id: int, quantity: float, usdt_name: str = 'USDT'):
        coin_name = self.coins.inverse.get(coin_id)
        print(self.coins)
        
        # symbol = f"{coin_name}/{usdt_name}"
        # try:
        #     order = await self.__ex.create_order(symbol, 'market', 'sell', quantity)
        #     filled_amount = order.get('filled', 0)
        #     cost = order.get('cost', 0)
        #     self.logger.info(f"Sell order filled: {filled_amount} {coin_name} for {cost} {usdt_name}")
        #     return order
        # except Exception as e:
        #     self.logger.error(f"Sell order failed for {symbol}: {e}")
        #     return None
    
    # Courier
    async def get_deposit_address(self, coin: Coin) -> str:        
        try:
            coin_name = coin.name
            chain = coin.chain
            
            params = {
                'network': chain,
                'chain': chain
            }
            
            address_info = await self.__ex.fetch_deposit_address(coin_name, params)
            
            address = None
            
            if isinstance(address_info, dict):
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
            raise ValueError(error_msg) from e
        except ccxtpro.BaseError as e:
            self.logger.error(f"Ошибка биржи при получении адреса {coin_name}: {e}")
            raise ConnectionError(f"Ошибка подключения к бирже: {e}") from e
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при получении адреса {coin_name}: {e}")
            raise RuntimeError(f"Ошибка получения адреса: {e}") from e
    
    
    async def withdraw(self, coin: Coin, amount: float, ex_destination: DESTINATION , tag: str = '') -> None:
        coin_name = coin.name
        chain = coin.chain
        
        address = await ex_destination.get_deposit_address(coin)
             
        params = {
            'network': chain,
            'chain': chain
        }
        
        await self.__ex.withdraw(coin_name, amount, address, tag=tag, params=params)

    async def get_current_coins(self) -> list[Coin]:
        # loge NotImplementedError
        return []
        