from zope.interface import Interface

# from core.models.dto import CoinDict
from core.models.Coins import Coin
from core.protocols.BalanceSubscriber import BalanceSubscriber

CoinDict = dict[Coin, float]


class IBalanceObserver(Interface):
    async def subscribe_balance(self, sub: BalanceSubscriber): ...
    async def unsubscribe_balance(self, sub: BalanceSubscriber): ...
    async def get_balance(self) -> CoinDict: ...
    async def launch(self) -> None: ...