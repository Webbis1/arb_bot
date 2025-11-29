

from core.interfaces.IBalanceObserver import IBalanceObserver
from core.interfaces.ICourier import ICourier
from core.interfaces.IPriceObserver import IPriceObserver
from core.interfaces.ITrader import ITrader
from core.models.Coins import Coin
from core.models.types import COIN_NAME

class IExchange(ITrader, IPriceObserver, IBalanceObserver, ICourier):
    async def get_current_coins(self) -> dict[COIN_NAME, set[Coin]]: ...
    async def watch_tickers(self, coin_names: list[COIN_NAME]) -> None: ...