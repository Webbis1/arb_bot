from dataclasses import dataclass, field

# from core.interfaces.Dto import Departure, Destination
# from core.models import Coin
from core.models.types import COIN_ID, DEPARTURE, DESTINATION


@dataclass
class Transfer:
    coin: COIN_ID
    departure: DEPARTURE
    destination: DESTINATION
    
    def __post_init__(self):
        if self.departure is self.destination:
            print("EEEEERORRORR")
    
    def __str__(self) -> str:
        return f"Transfer coin: {self.coin} from {self.departure} to {self.destination}"
    