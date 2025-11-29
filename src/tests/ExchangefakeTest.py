from typing import Optional
from core.interfaces import Exchange
from core.models.dto import Coins
from core.models import Coin


# Задача: реализовать методы sell и buy и withdraw, которые работают с вымышленным балансом, то есть делают вид, что операция выполнилась успешно, но на самом деле запрос на биржу не отпавляется.
# для withdraw сделать задержку перевода 
# соединить между собой биржи чтоб при переводе с одной на другую, баланс на первой уменьшается, а на второй увеличивается
# подготовить отчетность по выполненным операциям


import unittest

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
    
    async def withdraw(self, coin: Coin, amount: float, address: str, tag: Optional[str] = None, params: dict = {}) -> None: ...