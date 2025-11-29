from typing import Protocol

class BalanceSubscriber(Protocol):
    async def on_balance_update(self, coin: str, balance: float) -> None: ...