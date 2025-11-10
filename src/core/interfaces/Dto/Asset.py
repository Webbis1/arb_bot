from typing import TypedDict
from dataclasses import dataclass
from core.models import Coin

from core.models.types import COIN_ID, COIN_NAME, amount

@dataclass
class Asset():
    """
    Представляет собой актив на бирже
    coin: Coin - монета
    amount: float - количество монет
    """
    coin_id: COIN_ID
    amount: float