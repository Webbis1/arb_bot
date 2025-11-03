from typing import Protocol
from core.models import Coin

class PriceSubscriber(Protocol):
    async def on_price_update(self, coin: Coin, value: float) -> None: ...