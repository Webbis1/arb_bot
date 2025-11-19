
from infrastructure.CcxtExchangeModel import CcxtExchangModel


class PriceExchange(CcxtExchangModel):
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

