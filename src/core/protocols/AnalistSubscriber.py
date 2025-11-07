from typing import Protocol

from core.interfaces import Exchange
from core.interfaces.Dto import Recommendation



class AnalistSubscriber(Protocol):
        running: bool
        async def update_solution(self, dto: Recommendation) -> None: ...
        def get_exchange(self) -> Exchange: ...