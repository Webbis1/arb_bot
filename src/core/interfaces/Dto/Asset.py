from typing import TypedDict
from dataclasses import dataclass
from core.models import Coin

@dataclass
class Asset():
    coin: Coin
    ammount: float