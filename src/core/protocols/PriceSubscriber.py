from typing import Protocol, runtime_checkable
from core.models import Coin
from core.models.types import COIN_ID, COIN_NAME


@runtime_checkable
class PriceSubscriber(Protocol):
    def __hash__(self) -> int: ...
    async def on_price_update(self, coin_name: COIN_NAME, value: float) -> None: ...