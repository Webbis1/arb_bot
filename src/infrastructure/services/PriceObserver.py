import asyncio
import logging
import ccxt
from zope.interface import implementer



from core.interfaces.IPriceObserver import IPriceObserver
from core.models.types import COIN_NAME
from core.protocols.PriceSubscriber import PriceSubscriber
from infrastructure.CcxtExchangeModel import CcxtExchangModel
from infrastructure.Connection import Connection

@implementer(IPriceObserver)
class PriceObserver():
    def __init__(self, ex: CcxtExchangModel):
        self.__ex = ex
        self._logger = logging.getLogger(f'PriceObserver.{self.__ex.name}')
        self.price_subscribers: set[PriceSubscriber] = set()

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
    def _get_coin(self):
        return self.__ex.get_coin
    
    @property
    def _instance(self) -> Connection:
        return self.__ex.instance
    
    async def _price_notify(self, coin_name: str, value: float):
        try:
            notify_tasks = []
            for sub in self.price_subscribers:
                notify_tasks.append(sub.on_price_update(coin_name, value))
            if notify_tasks:
                await asyncio.gather(*notify_tasks, return_exceptions=True)
        except Exception as e:
            self._logger.exception(f"Error notifying price subscriber: {e}")

    def _get_symbols(self, coin_names: list[COIN_NAME]) -> list[str]:
        return [f"{coin_name}/USDT" for coin_name in coin_names]

    async def _start_price_observation(self, coin_names: list[COIN_NAME]) -> None:
        self._logger.info("Start price observe")
        try:
            symbols = self._get_symbols(coin_names)
            
            async with self._connection as exchange:
                while self._working:
                    if await self._instance.wait_ready() and exchange is not None:
                        try:
                            tickers = await exchange.watch_tickers(symbols)
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
                                    self._logger.warning(f"There is not fee data for Coin {coin_name}")

                                await self._price_notify(coin_name, price)

                        except asyncio.CancelledError:
                            self._logger.info("Price observation cancelled")
                            break
                        except ccxt.BadSymbol as e:
                            self._logger.error(f"Неверный символ для наблюдения: {e}")
                            await asyncio.sleep(5)
                        except ccxt.NotSupported as e:
                            self._logger.error(f"Наблюдение за тикерами не поддерживается: {e}")
                            break
                        except ccxt.ExchangeError as e:
                            error_msg = str(e).lower()
                            if 'connection' in error_msg or 'socket' in error_msg:
                                self._logger.warning(f"Проблема соединения при наблюдении: {e}")
                                await asyncio.sleep(10)
                            elif 'too many' in error_msg or 'rate limit' in error_msg:
                                self._logger.warning(f"Превышен лимит запросов: {e}")
                                await asyncio.sleep(60)
                            elif 'market' in error_msg or 'symbol' in error_msg:
                                self._logger.error(f"Проблема с торговой парой: {e}")
                                await asyncio.sleep(5)
                            else:
                                self._logger.error(f"Ошибка биржи при наблюдении: {e}")
                                await asyncio.sleep(5)
                        except ccxt.InvalidNonce as e:
                            self._logger.error(f"Проблема с синхронизацией времени: {e}")
                            await asyncio.sleep(10)
                        except Exception as e:
                            self._logger.error(f"Неизвестная ошибка при наблюдении за ценами: {e}")
                            await asyncio.sleep(5)

        except Exception as e:
            self._logger.exception(f"Fatal price error: {e}")
        finally:
            await asyncio.sleep(0.5)

    async def stop_price_observation(self):
        self._is_running = False

    async def subscribe_price(self, sub: PriceSubscriber):
        self.price_subscribers.add(sub)

    async def unsubscribe_price(self, sub: PriceSubscriber):
        self.price_subscribers.discard(sub)

    async def launch(self) -> None:
        self._logger.info("Launch")
        if not self._working: return
        coin_names: list[COIN_NAME] = []

        for coin_name in self._wallet.keys():
            coin_names.append(coin_name)
        
        self.__price_task = asyncio.create_task(self._start_price_observation(coin_names))

        
        await self.__price_task
        