from dataclasses import dataclass, field

from core.interfaces.Dto import Departure, Destination
from core.models import Coin
from core.models.types import coin_id


@dataclass
class Transfer:
    coin: coin_id
    departure: Departure
    destination: Destination
    