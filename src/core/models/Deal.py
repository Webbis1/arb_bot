from dataclasses import dataclass

from core.models import Coin
from core.interfaces import Exchange

@dataclass
class Deal:
    coin: Coin
    departure: Exchange
    destination: Exchange
    benefit: float