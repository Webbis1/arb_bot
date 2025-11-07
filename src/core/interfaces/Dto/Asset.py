from typing import TypedDict
from dataclasses import dataclass
from core.models import Coin

@dataclass
class Asset():
    """
    Представляет собой актив на бирже
    coin: Coin - монета
    amount: float - количество монет
    """
    coin: Coin
    amount: float