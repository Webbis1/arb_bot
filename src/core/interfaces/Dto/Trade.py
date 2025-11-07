from dataclasses import dataclass, field

from core.interfaces.Dto import Destination
from core.models import Coin

@dataclass
class Trade:
    buy_coin: Coin
    sell_coin: Coin

    