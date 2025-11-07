from abc import abstractmethod
from bidict import bidict
from typing import Optional, Any

from core.interfaces import Exchange
from core.interfaces.Dto import CoinDict, Coins
from core.models import Coin
from core.protocols import BalanceSubscriber, PriceSubscriber

import asyncio
from asyncio import Condition
import ccxt.pro as ccxtpro
import logging

from core.services.Mapper import Mapper



class CcxtExchange(Exchange):
    
    def __init__(self, mapper: Mapper, name: str, api_key: str, api_secret: str, **kwargs):
        self.mapper = mapper
        self.__api_key = api_key
        self.__api_secret = api_secret
        self.__password = kwargs.get('password', '')
        self.__ex: ccxtpro.Exchange 
        self.wallet: dict[int, float] = {}
        # self.coin_pairs: bidict[str, int] = bidict()
        
        self.coins: bidict[str, int] = bidict()
        self.balance_sudscribers: set[BalanceSubscriber] = set()
        self.price_subscribers: set[PriceSubscriber] = set()
        self._is_running = False
        

        
        self.logger = logging.getLogger(f'CcxtExchange.{name}')
        super().__init__(name)
    
    async def _connect(self, ex_name: str, api_key: str, api_secret: str, password: str = "") -> ccxtpro.Exchange | None:
        self.logger.debug(f"Attempting to connect to '{ex_name}'...")
        try:
            if not hasattr(ccxtpro, ex_name):
                self.logger.error(f"Exchange '{ex_name}' is not supported in ccxt.pro.")
                return None

            exchange_params = {
                'apiKey': api_key,
                'secret': api_secret,
                'sandbox': False,
                'enableRateLimit': True,
                'timeout': 30000,
                'verify': False,  # Отключить проверку SSL
                # 'verbose': True,
            }
            
            if password != "":
                exchange_params['password'] = password
            
            exchange_class = getattr(ccxtpro, ex_name)
            exchange = exchange_class(exchange_params)
            
            await exchange.load_markets()
            self.logger.debug(f"Successfully loaded markets for {ex_name}.")
            return exchange
            
        except ccxtpro.NetworkError as e:
            self.logger.error(f"✗ {ex_name}: Network error during connection - {e}", exc_info=True)
            return None
        except ccxtpro.AuthenticationError as e:
            self.logger.error(f"✗ {ex_name}: Authentication error (invalid API keys/secret/password) - {e}", exc_info=True)
            return None
        except ccxtpro.ExchangeError as e:
            self.logger.error(f"✗ {ex_name}: Exchange specific error - {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"✗ {ex_name}: An unexpected error occurred during connection - {e}", exc_info=True)
            return None
    
    
    async def connect(self) -> None:
        ex = await self._connect(self.name, self.__api_key, self.__api_secret, self.__password)
        if ex is None: raise ConnectionError(f"Failed to connect to exchange '{self.name}'.")
        else: self.__ex = ex
    
    async def close(self) -> None:
        try:
            await self.__ex.close()
            self.logger.info(f"Exchange '{self.name}' closed successfully.")
        except asyncio.CancelledError:
            self.logger.debug(f"Exchange '{self.name}': background tasks were cancelled")
        except Exception as e:
            self.logger.warning(f"Error closing exchange '{self.name}': {e}")
    
    async def get_current_coins(self) -> Coins: ...
    
    async def _is_trading_with_usdt(self, markets, coin_name):
        try:
            for market in markets:
                if (market['base'] == coin_name and 
                    market['quote'] == 'USDT' and 
                    market['active']):
                    return True, market['symbol']
            return False, None
        except Exception as e:
            print(f"Ошибка при проверке торговых пар: {e}")
            return False, None
    
    async def start(self, coins: bidict[str, int]) -> None:
        if self._is_running: return
        
        
        self.coins = coins
        self._is_running = True
        self.wallet = {}
        for coin_id in coins.inverse.keys():
            self.wallet[coin_id] = 0.0
        
        asyncio.create_task(self.watch_tickers(list(coins.keys())))
    
    def _get_symbols(self, coin_names: list[str]) -> list[str]:
        return [f"{coin_name}/USDT" for coin_name in coin_names]
    
    async def watch_tickers(self, coin_names: list[str]) -> None:
        self._is_running = True
        try:
            self.logger.info(f"Starting Price monitoring for {self.name}...")
            
            symbols = self._get_symbols(coin_names)
            
            while self._is_running:
                try:
                    tickers = await self.__ex.watch_tickers(symbols)
                    for symbol, ticker in tickers.items():
                        coin_name = symbol.split('/')[0]
                        price = ticker['last']
                        asyncio.create_task(self._price_notify(self.coins[coin_name], price))
                    
                except asyncio.CancelledError:
                    self.logger.info(f"Observation cancelled for {self.__ex.id}")
                    break
                except Exception as e:
                    self.logger.info(f"[{self.__ex.id}] Error: {e}")
                    await asyncio.sleep(1)
                        
        except Exception as e:
            self.logger.exception(f"Fatal error: {e}")
        finally:
            self._is_running = False
    
    
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
    async def _balance_notify(self, coin: Coin, value: float):
        for sub in self.balance_sudscribers:
            try:
                asyncio.create_task(sub.on_balance_update(coin, value))
            except Exception as e:
                self.logger.exception(f"Error notifying price subscriber: {e}")
    
    async def _process_balance_update(self, new_balances: dict[str, Any]) -> None:
        try:
            for currency, new_balance in new_balances['total'].items():
                self.wallet[currency] = new_balance
                asyncio.create_task(self._balance_notify(currency, new_balance))
                        
        except Exception as e:
            self.logger.exception(f"Error processing balance update: {e}")
    
    async def _balance_observe(self) -> None:
        self._is_running = True
        try:    
            self.logger.info(f"Starting Balance monitoring for {self.name}...")
            
            while self._is_running:
                try:
                    balance_update = await self.__ex.watch_balance()
                    await self._process_balance_update(balance_update)
                    
                except asyncio.CancelledError:
                    self.logger.info(f"Observation cancelled for {self.__ex.id}")
                    break
                except Exception as e:
                    self.logger.info(f"[{self.__ex.id}] Error: {e}")
                    await asyncio.sleep(1)
                        
        except Exception as e:
            self.logger.exception(f"Fatal error: {e}")
        finally:
            self._is_running = False
    
    async def subscribe_balance(self, sub: BalanceSubscriber):
        self.balance_sudscribers.add(sub)
    
    async def unsubscribe_balance(self, sub: BalanceSubscriber):
        self.balance_sudscribers.discard(sub)
    
    async def get_balance(self) -> CoinDict:
        return self.wallet
    
    #Trader
    
    async def sell(self, coin: Coin, amount: float) -> None: ...
    
    async def buy(self, coin: Coin, amount: float) -> None: ...
    
    # Courier
    
    async def withdraw(self, coin: Coin, amount: float, address: str, tag: Optional[str] = None, params: dict = {}) -> None: ...