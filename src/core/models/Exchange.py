from bidict import bidict

from core.models.types import COIN_ID, COIN_NAME


class Exchange:
    def __init__(self, name: str):
        self.name: str = name
        self.coins: bidict[COIN_NAME, COIN_ID] = bidict()
    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Exchange):
            return False
        return self.name == other.name