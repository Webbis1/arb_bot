from dataclasses import dataclass, field

from core.interfaces.Dto import Departure, Destination
from core.models import Coin

@dataclass
class Transfer:
    coin: Coin
    departure: Departure
    destination: Destination
    amount: float
    