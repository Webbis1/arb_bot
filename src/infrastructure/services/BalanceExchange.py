
from infrastructure.CcxtExchangeModel import CcxtExchangModel


class BalanceExchange(CcxtExchangModel):
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


