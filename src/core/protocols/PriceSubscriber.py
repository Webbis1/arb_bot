from typing import Protocol, runtime_checkable
from core.models import Coin


@runtime_checkable
class PriceSubscriber(Protocol):
    """ async def on_price_update(self, coin: Coin, value: float) -> None: ... """
    async def on_price_update(self, coin: int, value: float) -> None: ...