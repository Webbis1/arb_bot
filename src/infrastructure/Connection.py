import asyncio
from copy import copy
import logging
import ccxt.pro as ccxtpro
import ccxt
import aiohttp
import math
import contextlib

from typing import AsyncGenerator, Type
from contextlib import asynccontextmanager
from ccxt.pro import Exchange as CcxtProExchange


from core.models.ExchangeBase import ExchangeBase


class Connection(ExchangeBase):
    def __init__(self, ex_name: str, params):
        super().__init__(ex_name)
        self.logger = logging.getLogger(f'Connection for {ex_name}')
        self.retry_count_limit = 2
        
        self.__params = params

        self.__exchange_class: Type[ccxtpro.Exchange] | None = getattr(ccxtpro, ex_name, None)

        self.__connected = asyncio.Event()
        self.__is_shutdown: asyncio.Event = asyncio.Event() #вызывать в случае поломки

        self.__exchange: CcxtProExchange | None = None
        
        
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
            
            self.logger.info(f"Connection attempt number {retry_count}")
            try:
                async with self.__connection_lock:
                    if self.__connected.is_set():
                        break
                        
                    if not self.__exchange_class:
                        await self.stop()
                        self.logger.critical(f"Exchange '{self.name}' not supported by ccxtpro.")
                        break
                    

                    try:
                        self.__exchange = self.__exchange_class(self.__params)
    
                        
                        # status = None
                        # if hasattr(self.__exchange, 'fetchStatus'):
                        #     status = await asyncio.wait_for(self.__exchange.fetch_status(), timeout=30.0)
                        
                        await asyncio.wait_for(self.__exchange.load_markets(), timeout=30.0)
                        
                        self.logger.info(f"Successfully connected to {self.name} and loaded markets.")
                        # self.logger.info(status or "Not supported fetch_status")
                            
                        
                        self.__connected.set()
                        self.__is_shutdown.clear()
                        asyncio.create_task(self.__shutdown_watcher())
                        
                        # self.logger.info("Подключились и съебались")
                        return
                        
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
                        self.logger.warning(f"Connection attempt {retry_count} failed: {type(e).__name__}")
                        
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
                        await self.disconnect(True)
                        return        
                    except Exception as e:
                        self.logger.error(f"Unexpected error: {e}")
                        continue
            finally:
                if not self.is_connection:
                    await self.disconnect(True)
                    
                    
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
            running_task = asyncio.create_task(self._disabled.wait())
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
            self.logger.info("Shutdown watcher was cancelled")
            await self.disconnect()
            return
        except Exception as e:
            self.logger.error(f"Unexpected error in shutdown watcher: {e}")
            await self.disconnect()
            await self.__reconnecting()
    
    

    
    async def wait_ready(self) -> bool:
        """Ждет подключения или остановки работы"""
        # self.logger.info("Start wait")
        status: bool = False
        try:
            connected_task = asyncio.create_task(self.__connected.wait())
            running_task = asyncio.create_task(self._disabled.wait())
            
            done, pending = await asyncio.wait(
                [connected_task, running_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            if connected_task in done:
                status = True
                
        except asyncio.CancelledError:
            self.logger.debug("wait_ready was cancelled")
        except Exception as e:
            self.logger.error(f"Unexpected error in wait_ready: {e}")
        finally:
            # self.logger.info(f"Wait status is {status}")
            return status
    
    @property
    def is_connection(self) -> bool:
        return self.__connected.is_set() and self.working
        


    async def disconnect(self, ignore: bool = False):
        self.logger.info("Close Connection")
        async with self.__connection_lock:
            if not self.is_connection and not ignore: 
                return 
            self.__connected.clear()
            if self.__exchange:
                try:
                    # Подавляем ошибки при закрытии
                    with contextlib.suppress(Exception):
                        await self.__exchange.close()
                    # self.logger.info("Successfully closed")
                except Exception as e:
                    self.logger.warning(f"Error closing exchange: {e}")
                finally:
                    self.__exchange = None
    
    @asynccontextmanager
    async def exchange(self):
        try:
            yield self.__exchange
            
            
        except (ccxt.DDoSProtection, ccxt.OnMaintenance, ccxt.ExchangeNotAvailable,
                ccxt.RequestTimeout, asyncio.TimeoutError, ConnectionError,
                aiohttp.ServerDisconnectedError, ccxt.NetworkError) as e:
            self.logger.warning({type(e).__name__})
            await self.disconnect()
            
            await self.__update_last_exception(e)
            
            
            self.__is_shutdown.set()
            yield None
        
        except asyncio.CancelledError:
            self.logger.critical("connection was cancelled")
            await self.disconnect(True)
            await asyncio.sleep(5)
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