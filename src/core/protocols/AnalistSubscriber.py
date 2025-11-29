from typing import Protocol

from core.models.ExchangeBase import ExchangeBase
from core.models.dto import Recommendation



class AnalistSubscriber(Protocol):
        running: bool
        async def update_solution(self, dto: Recommendation) -> None: ...
        def get_exchange(self) -> ExchangeBase: ...