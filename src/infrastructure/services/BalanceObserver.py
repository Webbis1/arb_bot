import asyncio
from copy import copy
import logging
import traceback
from typing import Any
import ccxt
from zope.interface import implementer
from ccxt.pro import Exchange as CcxtProExchange



from core.interfaces.IBalanceObserver import IBalanceObserver
from core.models.types import AMOUNT, COIN_NAME
from core.protocols.BalanceSubscriber import BalanceSubscriber
from infrastructure.CcxtExchangeModel import CcxtExchangModel
from infrastructure.Connection import Connection

@implementer(IBalanceObserver)
class BalanceObserver():
    def __init__(self, ex: CcxtExchangModel):
        self.__ex = ex
        
        self._logger = logging.getLogger(f'BalanceObserver.{self.__ex.name}')
        self._balance_subscribers: set[BalanceSubscriber] = set()
        self._coin_locks: dict[COIN_NAME, asyncio.Lock] = {}
        self._epsilon = 10e-6

    async def launch(self) -> None:
        self._logger.info("Launch")
        if not self._working: return
        self._coin_locks = {}
        for coin_name in self._wallet.keys():
            self._coin_locks[coin_name] = asyncio.Lock()
        
        if await self._prepare():
            self._balance_task = asyncio.create_task(self._start_balance_observe())

            try:
                await self._balance_task
            except asyncio.CancelledError:
                pass


            
    async def subscribe_balance(self, sub: BalanceSubscriber):
        self._balance_subscribers.add(sub)

    async def unsubscribe_balance(self, sub: BalanceSubscriber):
        self._balance_subscribers.discard(sub)

    async def get_balance(self) -> dict[COIN_NAME, AMOUNT]:
        return copy(self._wallet)
    
    @property
    def _wallet(self):
        return self.__ex.wallet
    
    @property
    def _connection(self):
        return self.__ex.connection
    
    @property
    def _working(self):
        return self.__ex.working
    
    @property
    def _instance(self) -> Connection:
        return self.__ex.instance

    async def _prepare(self) -> bool:
        self._logger.info("Prepare")
        try:
            if self._working and await self._instance.wait_ready():
                async with self._connection as exchange:
                    if exchange is not None:
                        try:
                            balance_update = await exchange.fetch_balance()
                            await self._process_balance_update(balance_update)
                            self._logger.info("Preparations for the launch were successful")
                            return True
                            
                        except asyncio.CancelledError:
                            self._logger.info(f"Prepare cancelled")
                        except ccxt.NotSupported as e:
                            self._logger.error(f"Получение баланса не поддерживается: {e}")
                        except ccxt.PermissionDenied as e:
                            self._logger.error(f"Нет прав для получения баланса: {e}")
                        except ccxt.ExchangeError as e:
                            error_msg = str(e).lower()
                            if 'too many' in error_msg or 'rate limit' in error_msg:
                                self._logger.warning(f"Превышен лимит запросов для баланса: {e}")
                            elif 'authentication' in error_msg or 'api' in error_msg:
                                self._logger.error(f"Проблема аутентификации для баланса: {e}")
                            elif 'maintenance' in error_msg:
                                self._logger.warning(f"Биржа на техническом обслуживании: {e}")
                            else:
                                self._logger.error(f"Ошибка биржи при получении баланса: {e}")
                        except ccxt.InvalidNonce as e:
                            self._logger.error(f"Проблема с синхронизацией времени для баланса: {e}")
                        except ccxt.RequestTimeout as e:
                            self._logger.warning(f"Таймаут при получении баланса: {e}")
                        except Exception as e:
                            self._logger.error(f"Неизвестная ошибка при получении баланса: {e}")
                            self._logger.info(f"DISCONNECT CALLED - Stack: {traceback.format_stack()}")
                        
        except Exception as e:
            self._logger.exception(f"Fatal balance error: {e}")
        
        return False
    
    async def _update_wallet(self, coin_name: str, amount: float) -> bool:
        if coin_name not in self._wallet: return False
        
        if amount <= self._epsilon:
            amount = 0
        
        if lock := self._coin_locks.get(coin_name):
            async with lock:
                if self._wallet[coin_name] != amount:
                    self._wallet[coin_name] = amount
                    return True
            
        return False
        
    async def _process_balance_update(self, new_balances: dict[str, Any]) -> None:
        try:
            notify_tasks = []
            for coin_name, new_balance in new_balances['total'].items():
                if await self._update_wallet(coin_name, new_balance):
                    self._logger.info(f"Update balance: {coin_name} - {new_balance}")
                    for sub in self._balance_subscribers:
                        notify_tasks.append(sub.on_balance_update(coin_name, new_balance))

            if notify_tasks:
                await asyncio.gather(*notify_tasks, return_exceptions=True)

        except Exception as e:
            self._logger.exception(f"Error processing balance update: {e}")

    async def _start_balance_observe(self) -> None:
        self._logger.info("Start balance observe")
        try:
            async with self._connection as exchange:
                while self._working:
                    if await self._instance.wait_ready() and exchange is not None:
                        try:
                            balance_update = await exchange.watch_balance()
                            await self._process_balance_update(balance_update)
                        except asyncio.CancelledError:
                            # await asyncio.sleep(0.5)
                            self._logger.info(f"Balance observation cancelled")
                            break
                        except ccxt.NotSupported as e:
                            self._logger.error(f"Наблюдение за балансом не поддерживается: {e}")
                            break
                        except ccxt.PermissionDenied as e:
                            self._logger.error(f"Нет прав для наблюдения за балансом: {e}")
                            break
                        except ccxt.ExchangeError as e:
                            error_msg = str(e).lower()
                            if 'connection' in error_msg or 'socket' in error_msg:
                                self._logger.warning(f"Проблема соединения при наблюдении за балансом: {e}")
                                await asyncio.sleep(10)
                            elif 'too many' in error_msg or 'rate limit' in error_msg:
                                self._logger.warning(f"Превышен лимит запросов для баланса: {e}")
                                await asyncio.sleep(60)
                            elif 'authentication' in error_msg or 'api' in error_msg:
                                self._logger.error(f"Проблема аутентификации для баланса: {e}")
                                break
                            else:
                                self._logger.error(f"Ошибка биржи при наблюдении за балансом: {e}")
                                await asyncio.sleep(5)
                        except ccxt.InvalidNonce as e:
                            self._logger.error(f"Проблема с синхронизацией времени для баланса: {e}")
                            await asyncio.sleep(10)
                        except Exception as e:
                            self._logger.error(f"Неизвестная ошибка при наблюдении за балансом: {e}")
                            await asyncio.sleep(5)
        except Exception as e:
            self._logger.exception(f"Fatal balance error: {e}")
        finally:
            await asyncio.sleep(0.5)
