import asyncio
import functools
import logging
import aiohttp
from bidict import bidict
import ccxt

from core.models.Coins import Coin
from core.models.types import ADDRESS, CHAIN, COIN_ID, COIN_NAME, FEE, AMOUNT


class Exchange:
    def __init__(self, name: str):
        self.name: str = name
        self._is_running = asyncio.Event()
        # self.coins: bidict[COIN_NAME, COIN_ID] = bidict()
        self._address_map: dict[ADDRESS, Coin] = {}
        self.wallet: dict[COIN_NAME, AMOUNT] = {}
        self.logger = logging.getLogger(f'Exchange.{name}')
    
    
    @property
    def usdt(self) -> str:
        return "USDT"
    
    @property
    def connected(self):        
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                
                # Временные ошибки биржи (повторяемые)
                except (ccxt.DDoSProtection, ccxt.ExchangeNotAvailable, ccxt.OnMaintenance) as e:
                    self.logger.warning(f"Exchange temporary error (retryable): {type(e).__name__}: {str(e)}")
                    # Можно добавить задержку и повтор
                    await asyncio.sleep(5)  # Задержка перед повторной попыткой
                    return None
                
                
                # Сетевые ошибки (повторяемые)
                except (ccxt.NetworkError, ccxt.RequestTimeout, 
                        asyncio.TimeoutError, ConnectionError,
                        aiohttp.ClientError, aiohttp.ServerDisconnectedError) as e:
                    self.logger.warning(f"Network error (retryable): {type(e).__name__}: {str(e)}")
                    # Здесь можно добавить логику повторных попыток
                    return None
                
                
                # Критические ошибки аутентификации
                except ccxt.AuthenticationError as e:
                    self.logger.error(f"API keys error: {type(e).__name__}: {str(e)}")
                    # Требует вмешательства пользователя
                    return None
                
                # Ошибки недостатка средств
                # except ccxt.InsufficientFunds as e:
                #     self.logger.error(f"Insufficient funds: {type(e).__name__}: {str(e)}")
                #     # Требует пополнения баланса
                #     return None
                
                # Ошибки валидации ордеров
                # except (ccxt.InvalidOrder, ccxt.OrderNotFound, 
                #         ccxt.InvalidAddress, ccxt.AddressPending) as e:
                #     self.logger.error(f"Order validation error: {type(e).__name__}: {str(e)}")
                #     # Проблема с параметрами ордера
                #     return None
                
                # Ошибки аргументов
                except (TypeError, ValueError, AttributeError, KeyError) as e:
                    self.logger.error(f"Argument error: {type(e).__name__}: {str(e)}")
                    # Программная ошибка, требует исправления кода
                    return None
                
                # Ошибки отмены
                # except asyncio.CancelledError:
                #     self.logger.warning("Operation cancelled")
                #     raise  # Пробрасываем дальше, т.к. это нормальное завершение
                
                # Общие ошибки биржи
                except ccxt.ExchangeError as e:
                    self.logger.error(f"Exchange error: {type(e).__name__}: {str(e)}")
                    # Общая ошибка биржи, возможно временная
                    return None
                
                # Неизвестные ошибки CCXT
                # except ccxt.BaseError as e:
                #     self.logger.error(f"Unknown CCXT error: {type(e).__name__}: {str(e)}")
                #     return None
                
                # Все остальные непредвиденные ошибки
                # except Exception as e:
                #     self.logger.error(f"Unexpected error: {type(e).__name__}: {str(e)}")
                #     return None

            return wrapper
        return decorator
    
    @property
    def working(self) -> bool:
        return self._is_running.is_set()

    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Exchange):
            return False
        return self.name == other.name
    
    def get_coin(self, address: str) -> Coin | None:
        return self._address_map.get(address)
    
    def add_coin(self, coin: Coin):
        coin_address: str = coin.address
        
        if coin_address in self._address_map: raise Exception("The coin is already in address_map")
        
        self._address_map[coin_address] = coin