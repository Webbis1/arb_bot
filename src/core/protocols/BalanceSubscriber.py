from typing import Protocol
from core.models import Coin
from core.models.types import COIN_ID, DESTINATION, COIN_NAME, AMOUNT

class BalanceSubscriber(Protocol):
    async def on_balance_update(self, coin: COIN_ID, balance: float) -> None: ...