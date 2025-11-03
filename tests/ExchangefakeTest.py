from core.interfaces import Exchange
from core.interfaces.Dto import Coins


class ExchangeFake(Exchange):
    def __init__(self, ex: Exchange) -> None:
        self._ex = ex
        
        
    async def connect(self) -> None: 
        await self._ex.connect()
    
    
    async def close(self) -> None: 
        await self._ex.close()
    
    
    async def get_current_coins(self) -> Coins: 
        return await self._ex.get_current_coins()
    
    
    
    #Trader
    
    async def sell(self, coin: Coin, amount: float) -> None: ...
   
    async def buy(self, coin: Coin, amount: float) -> None: ...