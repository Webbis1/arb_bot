from core.models import Exchange
import asyncio
import logging
from typing import Awaitable, Callable, Dict, Iterable, Optional
from contextlib import asynccontextmanager, suppress
from ccxt.pro import Exchange as CcxtProExchange
import ccxt.pro as ccxtpro
import ccxt
import functools
import aiohttp
from core.models.dto.ExchangeParams import ExchangeParams

class ConnectionErrorHandler:
    def __init__(self, ex_name: str, params: ExchangeParams):
        self.logger = logging.getLogger('ConnectionErrorHandler')
        self.ex_name = ex_name
        self.attempts_count = 0
        self.exchange_class = getattr(ccxtpro, ex_name, None)
        self.exchange = None
        
        self.__connected = asyncio.Event()
        
        if not self.exchange_class:
            self.logger.error(f"Exchange '{ex_name}' not supported by ccxtpro.")
        else:
            self.exchange = self.exchange_class(params)  
            
    
    
    @property
    async def connected(self) -> bool:
        return self.__connected.is_set()    
    
    @asynccontextmanager
    async def conn(self):
        if not self.connected: 
            yield None
            return
        try: 
            yield self.instance
        
        finally: ...
      
                   
    async def _connection(self):
        if not self.exchange_class or not self.exchange:
            self.logger.error(f"Exchange '{self.ex_name}' not supported by ccxtpro.")
            return None

        # exchange = exchange_class(params)
        self.exchange.original_logger = logging.getLogger(f'ccxtpro.{self.exchange.id}')
        
        await asyncio.wait_for(self.exchange.load_markets(), timeout=30.0)
        self.logger.info(f"Successfully connected to {self.exchange.id} and loaded markets.")
        return self.exchange
    
    async def _auth (self): 
        pass
    
    # def connected(self):        
    #     def decorator(func):
    #         @functools.wraps(func)
    #         async def wrapper(*args, **kwargs):
    #             try:
    #                 return await func(*args, **kwargs)
                
    #             # Временные ошибки биржи (повторяемые)
    #             except (ccxt.DDoSProtection, ccxt.ExchangeNotAvailable, ccxt.OnMaintenance) as e:
    #                 self.logger.warning(f"Exchange temporary error (retryable): {type(e).__name__}: {str(e)}")
    #                 # Можно добавить задержку и повтор
    #                 await asyncio.sleep(5)  # Задержка перед повторной попыткой
    #                 await self._connection()
    #                 return None
                
                
    #             # Сетевые ошибки (повторяемые)
    #             except (ccxt.NetworkError, ccxt.RequestTimeout, 
    #                     asyncio.TimeoutError, ConnectionError,
    #                     aiohttp.ClientError, aiohttp.ServerDisconnectedError) as e:
    #                 self.logger.warning(f"Network error (retryable): {type(e).__name__}: {str(e)}")
    #                 await asyncio.sleep(5)  # Задержка перед повторной попыткой
    #                 await self._connection()
    #                 return None
                
                
    #             # Критические ошибки аутентификации
    #             except ccxt.AuthenticationError as e:
    #                 self.logger.error(f"API keys error: {type(e).__name__}: {str(e)}")
    #                 await asyncio.sleep(5)  # Задержка перед повторной попыткой
    #                 await self._auth()
    #                 return None
                

    #         return wrapper
    #     return decorator
    
    @property
    def instance(self):
        return self.exchange
    
    
    
    
    
    
# async def _connect(self, ex_name: str, params: ExchangeParams) -> ccxtpro.Exchange | None:
#         logger.debug(f"Connecting to '{ex_name}'...")
#         exchange = None
#         try:
#             exchange_class = getattr(ccxtpro, ex_name, None)
#             if not exchange_class:
#                 logger.error(f"Exchange '{ex_name}' not supported by ccxtpro.")
#                 return None

#             exchange = exchange_class(params)

#             exchange.original_logger = logging.getLogger(f'ccxtpro.{ex_name}')
            
#             await asyncio.wait_for(exchange.load_markets(), timeout=30.0)
#             logger.info(f"Successfully connected to {ex_name} and loaded markets.")
#             return exchange

#         except asyncio.TimeoutError:
#             logger.error(f"Timeout while loading markets for {ex_name}.")
#             return await self._safe_close(exchange)
            
#         except ccxt.PermissionDenied as e:
#             logger.error(f"Permission denied for {ex_name}: {str(e)}. Check API key permissions.")
#             return await self._safe_close(exchange)
            
#         except ccxt.AccountSuspended as e:
#             logger.error(f"Account suspended on {ex_name}: {str(e)}")
#             return await self._safe_close(exchange)
        
#         except ccxt.AuthenticationError as e:
#             logger.error(f"Authentication error for {ex_name}: {str(e)}. Check API keys and permissions.")
#             return await self._safe_close(exchange)
            
#         except ccxt.InsufficientFunds as e:
#             logger.error(f"Insufficient funds on {ex_name}: {str(e)}")
#             # Можно продолжить работу в режиме только чтения
#             logger.info(f"Continuing with {ex_name} in read-only mode")
#             return exchange
            
#         except ccxt.ExchangeNotAvailable as e:
#             logger.error(f"Exchange {ex_name} not available: {str(e)}")
#             return await self._safe_close(exchange)
            
#         except ccxt.ExchangeError as e:
#             logger.error(f"Exchange-specific error for {ex_name}: {str(e)}")
#             return await self._safe_close(exchange)
            
#         except ccxt.DDoSProtection as e:
#             logger.warning(f"DDoS protection triggered for {ex_name}: {str(e)}. Waiting before retry...")
#             await asyncio.sleep(10)  # Ждем перед повторной попыткой
#             return await self._safe_close(exchange)
            
#         except ccxt.RateLimitExceeded as e:
#             logger.warning(f"Rate limit exceeded for {ex_name}: {str(e)}. Waiting before retry...")
#             await asyncio.sleep(5)
#             return await self._safe_close(exchange)
            
#         except ccxt.RequestTimeout as e:
#             logger.error(f"Request timeout for {ex_name}: {str(e)}")
#             return await self._safe_close(exchange)
        
#         except ccxt.NetworkError as e:
#             logger.error(f"Network error for {ex_name}: {str(e)}")
#             return await self._safe_close(exchange)
            
#         except ccxt.BaseError as e:
#             logger.error(f"CCXT base error connecting to {ex_name}: {str(e)}")
#             return await self._safe_close(exchange)
            
#         except ConnectionError as e:
#             logger.error(f"Connection error for {ex_name}: {str(e)}")
#             return await self._safe_close(exchange)
            
#         except IOError as e:
#             logger.error(f"I/O error for {ex_name}: {str(e)}")
#             return await self._safe_close(exchange)
            
#         except Exception as e:
#             logger.error(f"Unexpected error connecting to {ex_name}: {str(e)}", exc_info=True)
#             return await self._safe_close(exchange)