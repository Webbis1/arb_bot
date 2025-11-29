import asyncio
import logging

from core.models.Coins import Coin
from core.models.types import ADDRESS, COIN_NAME, AMOUNT


class ExchangeBase:
    def __init__(self, name: str):
        self.name: str = name
        self._disabled = asyncio.Event()
        self._address_map: dict[ADDRESS, Coin] = {}
        self.wallet: dict[COIN_NAME, AMOUNT] = {}
        self.logger = logging.getLogger(f'Exchange.{name}')
    
    
    @property
    def usdt(self) -> str:
        return "USDT"
    
    
    def symbol(self, coin_name: str) -> str:
        return f"{coin_name.upper()}/{self.usdt}"
   
    @property
    def working(self) -> bool:
        return not self._disabled.is_set()


    async def pause(self, seconds: float = 60):
        self._disabled.set()
        self.logger.info(f"A {seconds}-second pause was taken")
        await asyncio.sleep(seconds)
        self._disabled.clear()
    
    async def stop(self):
        self._disabled.set()
    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExchangeBase):
            return False
        return self.name == other.name
    
    def get_coin(self, address: str) -> Coin | None:
        return self._address_map.get(address)
    
    def add_coin(self, coin: Coin):
        coin_address: str = coin.address
        
        if coin_address in self._address_map: raise Exception("The coin is already in address_map")
        
        self._address_map[coin_address] = coin