from abc import abstractmethod
from bidict import bidict
from typing import Optional, Any

import ccxt
from ccxt.pro import Exchange as CcxtProExchange

from core.interfaces import Exchange
from core.models.Coins import Coin
from core.protocols import BalanceSubscriber, PriceSubscriber
from core.models.types import COIN_NAME, AMOUNT, DESTINATION

import asyncio
import logging


class BalanceExchange(Exchange):
    def __init__(self, name: str):
        super().__init__(name)
        self.balance_subscribers: set[BalanceSubscriber] = set()
        self.__coin_locks: dict[COIN_NAME, asyncio.Lock] = {}
        self.wallet: dict[COIN_NAME, AMOUNT] = {}
        self._is_running = False

    def set_wallet(self, wallet: dict[COIN_NAME, AMOUNT]):
        self.wallet = wallet

    def set_coin_locks(self, coin_locks: dict[COIN_NAME, asyncio.Lock]):
        self.__coin_locks = coin_locks

    async def _balance_notify(self, coin_name: str, value: float):
        for sub in self.balance_subscribers:
            try:
                asyncio.create_task(sub.on_balance_update(coin_name, value))
            except Exception as e:
                self.logger.exception(f"Error notifying balance subscriber: {e}")

    async def _process_balance_update(self, new_balances: dict[str, Any]) -> None:
        try:
            for coin_name, new_balance in new_balances['total'].items():
                if coin_name not in self.wallet: 
                    continue

                if new_balance < 10e-6:
                    new_balance = 0

                async with self.__coin_locks[coin_name]:
                    if self.wallet[coin_name] != new_balance:
                        self.wallet[coin_name] = new_balance
                        asyncio.create_task(self._balance_notify(coin_name, new_balance))

        except Exception as e:
            self.logger.exception(f"Error processing balance update: {e}")

    async def _balance_observe(self, exchange_instance: CcxtProExchange) -> None:
        try:    
            while self._is_running:
                try:
                    balance_update = await exchange_instance.watch_balance()
                    await self._process_balance_update(balance_update)
                except asyncio.CancelledError:
                    self.logger.info(f"Balance observation cancelled")
                    break
                except Exception as e:
                    self.logger.info(f"Balance observation error: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            self.logger.exception(f"Fatal balance error: {e}")

    async def start_balance_observation(self, exchange_instance: CcxtProExchange):
        self._is_running = True
        await self._balance_observe(exchange_instance)

    async def stop_balance_observation(self):
        self._is_running = False

    async def subscribe_balance(self, sub: BalanceSubscriber):
        self.balance_subscribers.add(sub)

    async def unsubscribe_balance(self, sub: BalanceSubscriber):
        self.balance_subscribers.discard(sub)

    async def get_balance(self) -> dict[COIN_NAME, AMOUNT]:
        return self.wallet


class PriceExchange(Exchange):
    def __init__(self, name: str):
        super().__init__(name)
        self.price_subscribers: set[PriceSubscriber] = set()
        self._is_running = False

    async def _price_notify(self, coin_name: str, value: float):
        for sub in self.price_subscribers:
            try:
                asyncio.create_task(sub.on_price_update(coin_name, value))
            except Exception as e:
                self.logger.exception(f"Error notifying price subscriber: {e}")

    def _get_symbols(self, coin_names: list[COIN_NAME]) -> list[str]:
        return [f"{coin_name}/USDT" for coin_name in coin_names]

    async def watch_tickers(self, exchange_instance: CcxtProExchange, coin_names: list[COIN_NAME]) -> None:
        self._is_running = True
        try:
            symbols = self._get_symbols(coin_names)

            while self._is_running:
                try:
                    tickers = await exchange_instance.watch_tickers(symbols)
                    for symbol, ticker in tickers.items():
                        coin_name = symbol.split('/')[0]
                        price = 0

                        if ticker['ask'] is not None:
                            price = ticker['ask']
                        elif ticker['lastPrice'] is not None:
                            price = ticker['lastPrice']
                        elif ticker['info']['lastPrice'] is not None:
                            price = ticker['info']['lastPrice']

                        if price == 0:
                            self.logger.warning(f"There is not fee data for Coin {coin_name}")

                        await self._price_notify(coin_name, price)

                except asyncio.CancelledError:
                    self.logger.debug("Price observation cancelled")
                    break
                except Exception as e:
                    self.logger.error(f"Price observation error: {e}")
                    await asyncio.sleep(1)

        except Exception as e:
            self.logger.exception(f"Fatal price error: {e}")

    async def start_price_observation(self, exchange_instance: CcxtProExchange, coin_names: list[COIN_NAME]):
        await self.watch_tickers(exchange_instance, coin_names)

    async def stop_price_observation(self):
        self._is_running = False

    async def subscribe_price(self, sub: PriceSubscriber):
        self.price_subscribers.add(sub)

    async def unsubscribe_price(self, sub: PriceSubscriber):
        self.price_subscribers.discard(sub)


class TradingExchange(Exchange):

    async def buy(self, exchange_instance: CcxtProExchange, coin_name: str, usdt_quantity: float | None = None, usdt_name: str = 'USDT'):
        if self.working:
            if coin_name == usdt_name:
                self.logger.warning("Buy usdt/usdt")
                return None

            
            
            if not usdt_quantity:
                usdt_quantity = self.wallet[coin_name]
                
            symbol = f"{coin_name}/{usdt_name}"
            
            @self.connected
            async def transaction(exchange: CcxtProExchange, symbol: str, quantity: float):
                if not exchange_instance.has['createMarketOrder']: #TODO: проверить для всех бирж
                    self.logger.warning(f"Market buy is not supported on exchange {self.name}")
                    return None
                order = await exchange.create_order(symbol, 'market', 'buy', quantity)
                filled_amount = order.get('filled')
                cost = order.get('cost')
                self.logger.info(f"Buy order: {symbol}, cost: {cost or ""}, filled: {filled_amount or ""}")
                return order
            
            return await transaction(exchange_instance, symbol, usdt_quantity)

    async def sell(self, exchange_instance: CcxtProExchange, coin_name: str, quantity: float | None = None, usdt_name: str = 'USDT'):
        if coin_name == usdt_name:
            self.logger.warning("Sell usdt/usdt")
            return None

        if not exchange_instance.has['createMarketOrder']:
            self.logger.warning(f"Market sell is not supported on exchange {exchange_instance.id}")
            return None

        symbol = f"{coin_name}/{usdt_name}"
        try:
            order = await exchange_instance.create_order(symbol, 'market', 'sell', quantity)
            filled_amount = order.get('filled')
            cost = order.get('cost', 0)
            self.logger.info(f"Sell order: {symbol}, cost: {cost}, filled: {filled_amount}")
            return order
        except Exception as e:
            self.logger.error(f"Sell order failed for {symbol}: {e}")
            return None


class TransferExchange(Exchange):


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

    def _get_deposit_address_params(self, coin: Coin) -> tuple[COIN_NAME, dict]:
        params = {
            "network": coin.network
        }
        return coin.name, params

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

class CcxtExchange(BalanceExchange, PriceExchange, TradingExchange, TransferExchange):
    def __init__(self, name: str, instance: CcxtProExchange):
        Exchange.__init__(self, name)
        self.__ex: CcxtProExchange = instance
        self._is_running = False
        self.logger = logging.getLogger(f'CcxtExchange.{name}')
        self.__coin_locks: dict[COIN_NAME, asyncio.Lock] = {}

    @property
    def instance(self) -> CcxtProExchange:
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
            self.logger.error(f"Error checking trading pairs: {e}")
            return False

    async def start(self) -> None:
        if self._is_running: 
            return

        self._is_running = True
        try:
            # Initialize wallet and locks
            self.wallet = {}
            for coin_id in coins.inverse.keys():
                self.wallet[coin_id] = 0.0
                self.__coin_locks[coin_id] = asyncio.Lock()

            # Setup components
            self.set_wallet(self.wallet)
            self.set_coin_locks(self.__coin_locks)

            new_balances = await self.instance.fetch_balance()
            await self._process_balance_update(new_balances)

            coin_names = list(coins.keys())
            if "USDT" in coin_names:
                coin_names.remove("USDT")

            self.logger.info(f"[{self.name}] Запуск мониторинга...")

            # Start observations
            tickers_task = asyncio.create_task(self.start_price_observation(self.instance, coin_names))
            await asyncio.sleep(5)
            self.logger.info("EX is load")
            
            balance_task = asyncio.create_task(self.start_balance_observation(self.instance))

            try:
                await asyncio.gather(tickers_task, balance_task, return_exceptions=True)
            except asyncio.CancelledError:
                self.logger.info(f"[{self.name}] Получен запрос на отмену...")
                self._is_running = False
                await asyncio.sleep(1)
                tickers_task.cancel()
                balance_task.cancel()
                await asyncio.gather(tickers_task, balance_task, return_exceptions=True)
                raise
                
        except asyncio.CancelledError:
            self.logger.info(f"[{self.name}] Задача отменена")
            raise
        except Exception as e:
            self.logger.error(f"[{self.name}] Error in start: {e}")
        finally:
            self._is_running = False
            for coin_id in self.coins.values():
                self.logger.debug(f"[{self.name}]: clear coin {coin_id} in analyst")
                await self._price_notify(coin_id, -10.0)
            self.logger.info(f"[{self.name}] Мониторинг остановлен")
