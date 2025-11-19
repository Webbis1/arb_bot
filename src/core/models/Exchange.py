import asyncio
import functools
import logging
import aiohttp
from bidict import bidict
import ccxt

from core.models.Coins import Coin
from core.models.types import ADDRESS, CHAIN, COIN_ID, COIN_NAME, FEE, AMOUNT


class Exchange:
    def __init__(self, name: str):
        self.name: str = name
        self._is_running = asyncio.Event()
        # self.coins: bidict[COIN_NAME, COIN_ID] = bidict()
        self._address_map: dict[ADDRESS, Coin] = {}
        self.wallet: dict[COIN_NAME, AMOUNT] = {}
        self.logger = logging.getLogger(f'Exchange.{name}')
    
    
    @property
    def usdt(self) -> str:
        return "USDT"
    
   
    @property
    def working(self) -> bool:
        return self._is_running.is_set()

    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Exchange):
            return False
        return self.name == other.name
    
    def get_coin(self, address: str) -> Coin | None:
        return self._address_map.get(address)
    
    def add_coin(self, coin: Coin):
        coin_address: str = coin.address
        
        if coin_address in self._address_map: raise Exception("The coin is already in address_map")
        
        self._address_map[coin_address] = coin