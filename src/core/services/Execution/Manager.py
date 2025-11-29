

import asyncio
from collections import defaultdict
from dataclasses import field
import logging

from core.interfaces import Exchange
from core.models.dto import Recommendation, Trade, Transfer, Wait
from core.interfaces.Dto.Asset import Asset
from core.models.types import BALANCE, COIN_ID, COIN_NAME, DEPARTURE, DESTINATION
from core.protocols.BalanceSubscriber import BalanceSubscriber
from core.services.Analytics.Brain import Brain
from core.services.Mapper import Mapper


class Manager(BalanceSubscriber):
    def __init__(self, brain: 'Brain', ex: 'Exchange'):
        
        self.ex: Exchange = ex
        self.brain: Brain = brain
        self.mapper: Mapper = self.brain.mapper
        self.logger: logging.Logger = logging.getLogger(f'Manager for {ex.name}')
        self.pending_coins: dict[COIN_ID, BALANCE] = {}
        self.locks: dict[COIN_ID, asyncio.Lock] = {}
        

    async def start(self):
        # await asyncio.sleep(5)
        self.logger.info(f"{self.ex.name} прогружена")
        await self.ex.subscribe_balance(self)
        # coin_dict = await self.ex.get_balance()
    
    async def _get_lock(self, coin_id: COIN_ID) -> asyncio.Lock:
        if coin_id not in self.locks:
            self.locks[coin_id] = asyncio.Lock()
        return self.locks[coin_id]

    async def check_pending_coin(self, coin_id: COIN_ID) -> bool:
        lock = await self._get_lock(coin_id)
        async with lock:
            return coin_id in self.pending_coins

    async def set_pending_coin(self, coin_id: COIN_ID, balance: BALANCE):
        lock = await self._get_lock(coin_id)
        async with lock:
            self.pending_coins[coin_id] = balance

    async def get_and_remove_pending_coin(self, coin_id: COIN_ID) -> BALANCE | None:
        lock = await self._get_lock(coin_id)
        async with lock:
            return self.pending_coins.pop(coin_id, None)

    async def remove_pending_coin(self, coin_id: COIN_ID):
        lock = await self._get_lock(coin_id)
        async with lock:
            self.pending_coins.pop(coin_id, None)
                  
    async def consultation(self, asset: Asset):
        rec: Recommendation = await self.brain.analyse(self.ex, asset)
        self.logger.critical(rec)
        if isinstance(rec, Wait):
            seconds: int = rec.seconds
            await self.set_pending_coin(asset.coin_id, asset.amount)
            await self.postponed_consultation(seconds, asset.coin_id)
        elif isinstance(rec, Trade):
            if rec.sell_coin == self.mapper.usdt: await self.ex.buy(rec.buy_coin)
            else: await self.ex.sell(rec.sell_coin)
            await self.remove_pending_coin(asset.coin_id)  # Очистка после действия
        elif isinstance(rec, Transfer):
            coin_id: COIN_ID = rec.coin
            departure: DEPARTURE = rec.departure
            destination: DESTINATION = rec.destination
            transfer_result: bool = False
            if self.ex is not departure: self.logger.error(f"перевод с биржи на саму себя {rec}")
            elif coin := self.mapper.get_best_coin_transfer(self.ex.name, destination.name,coin_id):
                coin_name = coin.name
                chain = coin.chain
                transfer_result = await self.ex.withdraw(coin_name, chain, asset.amount, destination)
            else:
                self.logger.error(f"невозможно выполнить перевод {rec}")
                    # await self.ex.sell(rec.coin)
            if not transfer_result:    
                await self.ex.sell(rec.coin)
                
            await self.remove_pending_coin(asset.coin_id)  # Очистка после действия

    async def postponed_consultation(self, seconds: int, coin_id):
        await asyncio.sleep(seconds)
        balance = await self.get_and_remove_pending_coin(coin_id)  # Получить и удалить
        if balance is not None:  # Проверка на случай параллельного удаления
            await self.consultation(Asset(coin_id, balance))

    async def on_balance_update(self, coin_id: COIN_ID, balance: float) -> None:
        if await self.check_pending_coin(coin_id):
            await self.set_pending_coin(coin_id, balance)
        else:
            await self.consultation(Asset(coin_id, balance))
    
    
