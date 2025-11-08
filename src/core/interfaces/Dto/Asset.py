from typing import TypedDict
from dataclasses import dataclass
from core.models import Coin

from core.models.types import coin_id, coin_name, amount

@dataclass
class Asset():
    """
    Представляет собой актив на бирже
    coin: Coin - монета
    amount: float - количество монет
    """
    coin_id: coin_id
    amount: float