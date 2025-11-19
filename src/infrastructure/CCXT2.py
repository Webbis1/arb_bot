from abc import abstractmethod
from bidict import bidict
from typing import Literal, Optional, Any

import ccxt
from ccxt.pro import Exchange as CcxtProExchange

from core.interfaces import Exchange
from core.models.Coins import Coin
from core.protocols import BalanceSubscriber, PriceSubscriber
from core.models.types import COIN_NAME, AMOUNT, DESTINATION

import asyncio
import logging

from infrastructure.CcxtExchangeModel import CcxtExchangModel
from infrastructure.ErrorHandlerServices.ConnectionErrorHandler import ConnectionErrorHandler
from infrastructure.services.BalanceExchange import BalanceExchange
from infrastructure.services.PriceExchange import PriceExchange
from infrastructure.services.TradingExchange import TradingExchange
from infrastructure.services.TransferExchange import TransferExchange





class CcxtExchange(BalanceExchange, PriceExchange, TradingExchange, TransferExchange):
    def __init__(self, name: str, instance: ConnectionErrorHandler):
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
