from core.models import Exchange
import asyncio
import logging
from typing import AsyncGenerator, Awaitable, Callable, Dict, Iterable, Optional, Type
from contextlib import asynccontextmanager, suppress
from ccxt.pro import Exchange as CcxtProExchange
import ccxt.pro as ccxtpro
import ccxt.async_support as ccxt_async
import ccxt
import functools
import aiohttp
from core.models.dto.ExchangeParams import ExchangeParams
import math





class Connection(Exchange):
    def __init__(self, ex_name: str, params: ExchangeParams):
        self.logger = logging.getLogger(f'Connection for {ex_name}')
        self.ex_name = ex_name
        self.retry_count_limit = 60
        
        self.__params = params

        self.__exchange_class: Type[ccxt.Exchange] | None = getattr(ccxtpro, ex_name, None)
        self.__exchange: CcxtProExchange
        self.__connected = asyncio.Event()
        self.__is_shutdown: asyncio.Event = asyncio.Event() #вызывать в случае поломки

        
        
        self._reconnect_lock = asyncio.Lock()

        self.__launch_time: float = 0
        

        self.__connection_lock = asyncio.Lock()

        
        
        self.__reconnection_is_underway: asyncio.Event = asyncio.Event()
        
    async def connection(self):
        if not self.working or self.is_connection: return

        base_delay = 1
        max_delay = 60
        
        for retry_count in range(self.retry_count_limit):
            if not self.working: return
            delay = min(base_delay * (2 ** retry_count), max_delay)
            await asyncio.sleep(delay)
            async with self.__connection_lock:
                if self.__connected.is_set():
                    break
                    
                if not self.__exchange_class:
                    await self.stop()
                    self.logger.critical(f"Exchange '{self.ex_name}' not supported by ccxtpro.")
                    break
                    
                try:
                    exchange = self.__exchange_class(self.__params)
                    await asyncio.wait_for(exchange.load_markets(), timeout=30.0)
                    self.logger.info(f"Successfully connected to {self.ex_name} and loaded markets.")
                    
                    if not self.working: return
                        
                    self.__exchange = exchange
                    
                    self.__connected.set()
                    self.__is_shutdown.clear()
                    await self.__shutdown_watcher()
                    break
                    
                except (ccxt.AuthenticationError, ccxt.PermissionDenied, ccxt.AccountSuspended) as e:
                    self.logger.critical(f"Critical auth error: {e}")
                    await self.stop()
                    break
                    
                except ccxt.DDoSProtection as e:
                    ddos_delay = getattr(e, 'retry_after', delay * 3)
                    self.logger.warning(f"DDoS protection, waiting {ddos_delay}s")
                    await asyncio.sleep(ddos_delay)
                    continue
                    
                except ccxt.OnMaintenance as e:
                    self.logger.warning("Exchange under maintenance, waiting 5 minutes")
                    await asyncio.sleep(300)
                    continue
                    
                except ccxt.RateLimitExceeded as e:
                    rate_delay = getattr(e, 'retry_after', delay * 2)
                    self.logger.warning(f"Rate limit exceeded, waiting {rate_delay}s")
                    await asyncio.sleep(rate_delay)
                    continue
                    
                except (asyncio.TimeoutError, ccxt.RequestTimeout, ccxt.NetworkError, 
                        ccxt.ExchangeNotAvailable, aiohttp.ClientConnectorError,
                        aiohttp.ServerDisconnectedError, ConnectionError, 
                        ConnectionRefusedError) as e:
                    self.logger.warning(f"Connection attempt {retry_count} failed: {e}")
                    continue
                    
                except ccxt.ExchangeError as e:
                    if 'maintenance' in str(e).lower():
                        self.logger.warning("Exchange maintenance detected, waiting 5 minutes")
                        await asyncio.sleep(300)
                        continue
                    else:
                        self.logger.error(f"Exchange error: {e}")
                        continue
                except asyncio.CancelledError:
                    self.logger.debug("connection was cancelled")
                    return        
                except Exception as e:
                    self.logger.error(f"Unexpected error: {e}")
                    continue
                    
        else:
            await self.stop()
            self.logger.critical("The number of reconnection attempts has been exhausted")
    
    async def __reconnecting(self):
        if self.__reconnection_is_underway.is_set() or not self.working:
            return
        
        self.__reconnection_is_underway.set()
        try:
            current_delay = 5
            await asyncio.sleep(current_delay)
            while self.working:
                async with self._reconnect_lock:
                    current_time = asyncio.get_event_loop().time()
                    if current_time >= self.__launch_time:
                        break
                    current_delay = math.ceil(self.__launch_time - current_time)
                await asyncio.sleep(current_delay)
            
            await self.connection()
        
        except asyncio.CancelledError:
            self.logger.debug("__reconnecting was cancelled")
            return
          
        finally:
            self.__reconnection_is_underway.clear()
    
    async def __update_last_exception(self, last_excpetion: Exception):
        delay = self.__get_retry_delay(last_excpetion)
        async with self._reconnect_lock:
            current_time = asyncio.get_event_loop().time()
            target_time = current_time + delay
            
            if self.__launch_time < target_time:
                self.__launch_time = target_time
    
    async def __shutdown_watcher(self):
        """Наблюдает за отключением или остановкой работы"""
        try:
            # Создаем задачу для каждого события
            shutdown_task = asyncio.create_task(self.__is_shutdown.wait())
            running_task = asyncio.create_task(self.__disabled.wait())
            timeout_task = asyncio.create_task(asyncio.sleep(24 * 60 * 60))  # 24 часа
            
            done, pending = await asyncio.wait(
                [shutdown_task, running_task, timeout_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                
            if shutdown_task in done:
                await self.__reconnecting()
                self.logger.info("Shutdown signal received")
            elif running_task in done:
                await self.disconnect()   
                self.logger.info("Running state changed")
            elif timeout_task in done:
                self.logger.warning("24-hour timeout reached, reconnecting...")
                await self.disconnect()
                await self.__reconnecting()
                self.logger.info("Reconnection after timeout completed")
                
        except asyncio.CancelledError:
            self.logger.debug("Shutdown watcher was cancelled")
            return
        except Exception as e:
            self.logger.error(f"Unexpected error in shutdown watcher: {e}")
            # При ошибке также выполняем переподключение
            await self.disconnect()
            await self.__reconnecting()
    
    

    
    async def wait_ready(self) -> bool:
        """Ждет подключения или остановки работы"""
        try:
            connected_task = asyncio.create_task(self.__connected.wait())
            running_task = asyncio.create_task(self.__disabled.wait())
            
            done, pending = await asyncio.wait(
                [connected_task, running_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            if connected_task in done:
                return True
            else:
                return False
                
        except asyncio.CancelledError:
            self.logger.debug("wait_ready was cancelled")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error in wait_ready: {e}")
            return False
    
    @property
    def is_connection(self) -> bool:
        return self.__connected.is_set() and self.working
        
    async def disconnect(self):
        async with self.__connection_lock:
            if not self.is_connection: 
                return 
            self.__connected.clear()
            if hasattr(self, '__exchange'):
                try:
                    await asyncio.wait_for(self.__exchange.close(), timeout=10.0)
                except (asyncio.TimeoutError, Exception) as e:
                    self.logger.warning(f"Error closing exchange: {e}")
                finally:
                    del self.__exchange
    
    @asynccontextmanager
    async def exchange(self) -> AsyncGenerator[CcxtProExchange | None]:
        try:
            if self.is_connection:
                yield self.__exchange
            else:
                yield None
            
        except (ccxt.DDoSProtection, ccxt.OnMaintenance, ccxt.ExchangeNotAvailable,
                ccxt.RequestTimeout, asyncio.TimeoutError, ConnectionError,
                aiohttp.ServerDisconnectedError, ccxt.NetworkError) as e:
            
            await self.disconnect()
            
            await self.__update_last_exception(e)
            
            
            self.__is_shutdown.set()
            yield None
        
        except ccxt.AuthenticationError as e:
            self.logger.critical(f"AuthenticationError")
            await self.stop()
            yield None
            
            
        finally: 
            pass

    def __get_retry_delay(self, error: Exception) -> int:
        """Определяет задержку для разных типов ошибок"""
        error_delays = {
            ccxt.DDoSProtection: 60,
            ccxt.OnMaintenance: 300,
            ccxt.ExchangeNotAvailable: 30,
            ccxt.RequestTimeout: 2,
            asyncio.TimeoutError: 2,
            ConnectionError: 10,
            aiohttp.ServerDisconnectedError: 10,
            ccxt.NetworkError: 5,
        }
        
        for error_type, delay in error_delays.items():
            if isinstance(error, error_type):
                return delay
        
        return 5