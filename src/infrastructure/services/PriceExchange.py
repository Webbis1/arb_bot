
import asyncio
from core.models.types import COIN_NAME
from core.protocols.PriceSubscriber import PriceSubscriber
from infrastructure.CcxtExchangeModel import CcxtExchangModel
from infrastructure.ErrorHandlerServices.Connection import Connection


class PriceExchange(CcxtExchangModel):
    def __init__(self, name: str, instance: Connection):
        super().__init__(name, instance)
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

    async def watch_tickers(self, coin_names: list[COIN_NAME]) -> None:
        self._is_running = True
        try:
            symbols = self._get_symbols(coin_names)
            
            async with self.connection as exchange:
                while self._is_running:
                    if self.instance.wait_ready and exchange is not None:
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

    async def start_price_observation(self, coin_names: list[COIN_NAME]):
        await self.watch_tickers(coin_names)

    async def stop_price_observation(self):
        self._is_running = False

    async def subscribe_price(self, sub: PriceSubscriber):
        self.price_subscribers.add(sub)

    async def unsubscribe_price(self, sub: PriceSubscriber):
        self.price_subscribers.discard(sub)

