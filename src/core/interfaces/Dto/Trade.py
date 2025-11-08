from dataclasses import dataclass, field

from core.interfaces.Dto import Destination
from core.models import Coin

from core.models.types import coin_id

@dataclass
class Trade:
    buy_coin: coin_id
    sell_coin: coin_id

    