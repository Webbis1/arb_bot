from dataclasses import dataclass, field

# from core.interfaces.Dto import Destination
# from core.models import Coin

from core.models.types import COIN_ID

@dataclass
class Trade:
    buy_coin: COIN_ID
    sell_coin: COIN_ID
    
    def __str__(self) -> str:
        return f"Trade {self.sell_coin} to {self.buy_coin}"

    