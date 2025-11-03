from abc import ABC, abstractmethod
from typing import Optional

from core.interfaces import CoinDict, Coins
from core.models import Coin
from core.protocols import BalanceSubscriber, PriceSubscriber

class Exchange(ABC):
    @abstractmethod
    async def connect(self) -> None: ...
    @abstractmethod
    async def close(self) -> None: ...
    @abstractmethod
    async def get_current_coins(self) -> Coins: ...
    
    
    
    # Price observer
    @abstractmethod
    async def subscribe_price(self, coin: Coin, sub: PriceSubscriber): ...
    @abstractmethod
    async def unsubscribe_price(self, coin: Coin, sub: PriceSubscriber): ...
    
    # Balance observer
    @abstractmethod
    async def subscribe_balance(self, sub: BalanceSubscriber): ...
    @abstractmethod
    async def unsubscribe_balance(self, sub: BalanceSubscriber): ...
    @abstractmethod
    async def get_balance(self) -> CoinDict: ...
    
    #Trader
    @abstractmethod
    async def sell(self, coin: Coin, amount: float) -> None: ...
    @abstractmethod
    async def buy(self, coin: Coin, amount: float) -> None: ...
    
    # Courier
    @abstractmethod
    async def withdraw(self, coin: Coin, amount: float, address: str, tag: Optional[str] = None, params: dict = {}) -> None: ...