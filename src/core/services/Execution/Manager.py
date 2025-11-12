

import asyncio
from collections import defaultdict
from dataclasses import field
import logging

from core.interfaces import Exchange
from core.interfaces.Dto import Recommendation, Trade, Transfer, Wait
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
        
        # self.conditions: dict[int, asyncio.Condition] = {}
        # self.tusks: dict[int, asyncio.Task] = {}
        # self.solutions: dict[int, tuple[bool, float, int | str]] = {}
        # self.traceable_coins: set[int] = set()
        self.pending_coins: dict[COIN_ID, BALANCE] = {}
        self.locks: defaultdict[COIN_ID, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
        

    async def start(self):
        await self.ex.subscribe_balance(self)
    
                    
    async def consultation(self, asset: Asset):
        rec: Recommendation = await self.brain.analyse(self.ex, asset)
        self.logger.critical(rec)
        if isinstance(rec, Wait):
            seconds: int = rec.seconds
            await self.set_pending_coin(asset.coin_id, asset.amount)
            await self.postponed_consultation(seconds, asset.coin_id)
        elif isinstance(rec, Trade):
            if rec.sell_coin == self.mapper.usdt: await self.ex.buy(rec.sell_coin)
            else: await self.ex.sell(rec.buy_coin)
            await self.remove_pending_coin(asset.coin_id)  # Очистка после действия
        elif isinstance(rec, Transfer):
            coin_id: COIN_ID = rec.coin
            # coin_name: COIN_NAME = self.ex.coins.inverse[coin_id]
            departure: DEPARTURE = rec.departure
            destination: DESTINATION = rec.destination
            if self.ex is departure:
                if coin := self.mapper.get_best_coin_transfer(self.ex.name, destination.name,coin_id):
                    coin_name = coin.name
                    chain = coin.chain
                    await self.ex.withdraw(coin_name, chain, asset.amount, destination)
                else:
                    # raise Exception(f"невозможно выполнить перевод {rec}")
                    self.logger.error(f"невозможно выполнить перевод {rec}")
                    await self.ex.sell(rec.coin)
            else:
                self.logger.error(f"перевод с биржи на саму себя {rec}")
                await self.ex.sell(rec.coin)
                
            await self.remove_pending_coin(asset.coin_id)  # Очистка после действия

    async def postponed_consultation(self, seconds: int, coin_id):
        await asyncio.sleep(seconds)
        balance = await self.get_and_remove_pending_coin(coin_id)  # Получить и удалить
        if balance is not None:  # Проверка на случай параллельного удаления
            await self.consultation(Asset(coin_id, balance))

    async def set_pending_coin(self, coin_id: COIN_ID, balance: BALANCE):
        async with self.locks[coin_id]:
            self.pending_coins[coin_id] = balance

    async def get_and_remove_pending_coin(self, coin_id: COIN_ID) -> BALANCE | None:
        async with self.locks[coin_id]:
            return self.pending_coins.pop(coin_id, None)

    async def remove_pending_coin(self, coin_id: COIN_ID):
        async with self.locks[coin_id]:
            self.pending_coins.pop(coin_id, None)
            
    async def check_pending_coin(self, coin_id: COIN_ID) -> bool:
        async with self.locks[coin_id]:
            return coin_id in self.pending_coins

    async def on_balance_update(self, coin_id: COIN_ID, balance: float) -> None:
        if await self.check_pending_coin(coin_id):
            await self.set_pending_coin(coin_id, balance)
        else:
            await self.consultation(Asset(coin_id, balance))
    
    
    
    
    
    
    
    
    
    
    # def _get_condition(self, coin_id: int) -> asyncio.Condition:
    #     if coin_id not in self.conditions:
    #         self.conditions[coin_id] = asyncio.Condition()
    #     return self.conditions[coin_id]

    # async def _start_wait_task(self, coin_id: int):
    #     """Создает задачу, которая ждет, пока баланс >= limit."""
    #     condition = self._get_condition(coin_id)

    #     async def wait_and_execute():
    #         async with condition:
    #             # Ждем, пока баланс >= limit (если решение существует)
    #             while coin_id in self.solutions and self.wallet.get(coin_id, 0) < self.solutions[coin_id][1] and self.wallet.get(coin_id, 0) > 0:
    #                 await condition.wait()

    #         # Проверяем, существует ли решение
    #         if coin_id in self.solutions:
    #             await self._apply_solution(coin_id, self.solutions[coin_id][0], self.solutions[coin_id][2])
            
    #         # Удаляем задачу из списка (опционально)
    #         self.tusks.pop(coin_id, None)
            
    #         sol = self.solutions[self.USDT]
            
    #         if not sol[0]: # обмен на другую валюту
    #             if sol[2] != coin_id: # обмениваем не на нашу валюту
    #                 await self.unsubscribe_from_the_brain(coin_id)

    #     task = asyncio.create_task(wait_and_execute(), name=f"wait_task_{coin_id}")
    #     self.tusks[coin_id] = task
        
    
    # async def _apply_solution(self, coin_id: int, move_type: bool, target: int | str):
    #     """Применяет решение в зависимости от типа."""
    #     if move_type == 0:
    #         await self._swap_coins(coin_id, target)
    #     elif move_type == 1:
    #         await self._transfer_to_exchange(coin_id, target)

    # async def _swap_coins(self, coin_id: int, target: int | str):
    #     """Заглушка: обмен монеты."""
    #     print(f"[SWAP] Обмен монеты {coin_id} на {target}")

    # async def _transfer_to_exchange(self, coin_id: int, target: int | str):
    #     """Заглушка: перевод на другую биржу."""
    #     print(f"[TRANSFER] Перевод монеты {coin_id} на биржу {target}")
        
        
    
    
    # async def update_solution(self, coin_id: int, move_type: bool, limit: float, target: int | str):
    #     """Обновляет решение от мозга и запускает задачу ожидания."""
    #     if coin_id in self.conditions:
    #         self.solutions[coin_id] = (move_type, limit, target)

    #         condition = self._get_condition(coin_id)
    #         async with condition:
    #             condition.notify_all() 
        
        
    # async def update_trade_solution(self, coin_id: int, target_coin_id: int, rate: float):
    #     # Проверяем, разрешено ли обновление для этой монеты
    #     if coin_id not in self.traceable_coins:
    #         return  # или можно вызвать raise, если это ошибка

    #     # Обновляем решение для пары

    #     # Если coin_id — это USDT, проверяем и управляем подпиской
    #     if coin_id == self.USDT:
    #         await self._manage_usdt_subscription(target_coin_id)

    #     self.solutions[coin_id] = (0, rate, target_coin_id)
    #     # Уведомляем ожидающие задачи
    #     condition = self._get_condition(coin_id)
    #     async with condition:
    #         condition.notify_all()

    # async def _manage_usdt_subscription(self, new_target_coin_id: int):
    #     """Управляет подпиской для USDT на основе текущего и нового таргета."""
    #     current_solution = self.solutions.get(self.USDT)

    #     if current_solution:
    #         _, _, current_target = current_solution
    #         if current_target != new_target_coin_id:
                
    #             await self.unsubscribe_from_the_brain(current_target)
    #             await self.subscribe_to_the_brain(new_target_coin_id)
    #     else:
    #         # Если решения не было — подписываемся впервые
    #         await self.subscribe_to_the_brain(new_target_coin_id)
                
            
        
    # async def update_price(self, coin: str, new_value: float) -> None:
    #     if coin in self._coins:
    #         coin_id = self._coins[coin]
    #         old_balance = self.wallet.get(coin_id, 0)
    #         self.wallet[coin_id] = old_balance + new_value
    #         if coin_id not in self.tusks:
    #             await self._start_wait_task(coin_id)
            
    #         condition = self._get_condition(coin_id)
    #         async with condition:
    #             condition.notify_all() 
                
    #         await self.subscribe_to_the_brain()
                