from typing import Protocol

from core.interfaces.Dto.Trade import Trade
from core.interfaces.Dto.Transfer import Transfer
from core.models import Coin, Exchange


class AnalistSubscriber(Protocol):
        async def update_solution(self, dto: Trade | Transfer) -> None: ...
        def get_exchange(self) -> Exchange: ...