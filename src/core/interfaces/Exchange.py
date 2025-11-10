from abc import ABC, abstractmethod
from typing import Optional

# from core.interfaces import CoinDict, Coins
from core.models import Coin, Exchange as ExchangeModel
from core.models.types import COIN_NAME
from core.protocols import BalanceSubscriber, PriceSubscriber

from core.interfaces.Dto import CoinDict, DESTINATION

class Exchange(ABC, ExchangeModel):
    # @abstractmethod
    # async def connect(self) -> None: ...
    # @abstractmethod
    # async def close(self) -> None: ...
    @abstractmethod
    async def get_current_coins(self) -> list[Coin]: ...
    
    @abstractmethod
    async def watch_tickers(self, coin_names: list[COIN_NAME]) -> None: ...
    
    # Price observer
    @abstractmethod
    async def subscribe_price(self, sub: PriceSubscriber): ...
    @abstractmethod
    async def unsubscribe_price(self, sub: PriceSubscriber): ...
    
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
    
    @abstractmethod
    async def get_deposit_address(self, coin: Coin) -> str: ...
    
    # Courier
    @abstractmethod
    async def withdraw(self, coin: Coin, amount: float, ex_destination: DESTINATION , tag: str = '') -> None: ...