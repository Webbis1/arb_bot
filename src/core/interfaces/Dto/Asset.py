from typing import TypedDict
from dataclasses import Field, dataclass
from core.models import Coin

from core.models.types import COIN_ID, COIN_NAME, AMOUNT

@dataclass
class Asset():
    coin_id: int
    amount: float
    
    def __post_init__(self):
        # Проверка, что coin_id заполнен
        if self.coin_id is None:
            raise ValueError("coin_id is required")
        
        # Проверка, что amount заполнен
        if self.amount is None:
            raise ValueError("amount is required")
        
        # Дополнительные проверки типов
        if not isinstance(self.coin_id, int):
            raise TypeError(f"coin_id must be int, got {type(self.coin_id)}")
        
        if not isinstance(self.amount, (int, float)):
            raise TypeError(f"amount must be float, got {type(self.amount)}")