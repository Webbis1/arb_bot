from typing import Protocol
from core.models import Coin

class BalanceSubscriber(Protocol):
    async def on_balance_update(self, coin: Coin, balance: float) -> None: ...