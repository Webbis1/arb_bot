from typing import Protocol, runtime_checkable
from core.models import Coin
from core.models.types import COIN_ID


@runtime_checkable
class PriceSubscriber(Protocol):
    def __hash__(self) -> int: ...
    async def on_price_update(self, coin_id: COIN_ID, value: float) -> None: ...