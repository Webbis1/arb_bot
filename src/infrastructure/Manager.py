

class Manager:
    def __init__(self, obs: BalanceObserver, brain: 'Brain', port: 'Port', name: str, coins: bidict[str, int], chains: dict[int, str], commissions:dict[int, float]):
        self._coins: bidict[str, int] = coins # название - id
        self.chains: dict[int, str] = chains # coin_id - сеть
        self.commissions: dict[int, float] = commissions # coin_id - комиссия 
        self.wallet: dict[int, float] = {}
        self.trader: 'Trader'
        self.conditions: dict[int, asyncio.Condition] = {}  # coin_id -> condition
        self.tusks: dict[int, asyncio.Task] = {}  # coin_id -> для каких монет есть нерешенные проблемы 
        self.solutions: dict[int, tuple[bool, float, int | str]] = {}  # coin_id -> (move_type, limit, target)
        self.traceable_coins: set[int] = set()
        
        
        self.reset_wallet()
        obs.subscribe(self)
        self.brain: 'Brain' = brain
        self.port: 'Port' = port
        
        self._name: str = name
        
        self.USDT = self._coins["USDT"]
    
    def get_name(self) -> str:
        return self._name
    
    def reset_wallet(self):
        self.wallet = {}
        for _, id in self._coins.items():
            self.wallet[id] = 0.0
    
    def _get_condition(self, coin_id: int) -> asyncio.Condition:
        if coin_id not in self.conditions:
            self.conditions[coin_id] = asyncio.Condition()
        return self.conditions[coin_id]



    async def subscribe_to_the_brain(self, coin_id: int):
        """Создает задачу, которая слушает решения от мозга для coin_id."""
        if coin_id not in self.traceable_coins:
            self.brain.subscribe(self, coin_id)
            self.traceable_coins.add(coin_id)


    async def unsubscribe_from_the_brain(self, coin_id: int):
        """Отменяет задачу подписки на мозг."""
        if coin_id in self.traceable_coins:
            self.brain.unsubscribe(self, coin_id)
            self.traceable_coins.remove(coin_id)

    async def _start_wait_task(self, coin_id: int):
        """Создает задачу, которая ждет, пока баланс >= limit."""
        condition = self._get_condition(coin_id)

        async def wait_and_execute():
            async with condition:
                # Ждем, пока баланс >= limit (если решение существует)
                while coin_id in self.solutions and self.wallet.get(coin_id, 0) < self.solutions[coin_id][1] and self.wallet.get(coin_id, 0) > 0:
                    await condition.wait()

            # Проверяем, существует ли решение
            if coin_id in self.solutions:
                await self._apply_solution(coin_id, self.solutions[coin_id][0], self.solutions[coin_id][2])
            
            # Удаляем задачу из списка (опционально)
            self.tusks.pop(coin_id, None)
            
            sol = self.solutions[self.USDT]
            
            if not sol[0]: # обмен на другую валюту
                if sol[2] != coin_id: # обмениваем не на нашу валюту
                    await self.unsubscribe_from_the_brain(coin_id)

        task = asyncio.create_task(wait_and_execute(), name=f"wait_task_{coin_id}")
        self.tusks[coin_id] = task
        
    
    async def _apply_solution(self, coin_id: int, move_type: bool, target: int | str):
        """Применяет решение в зависимости от типа."""
        if move_type == 0:
            await self._swap_coins(coin_id, target)
        elif move_type == 1:
            await self._transfer_to_exchange(coin_id, target)

    async def _swap_coins(self, coin_id: int, target: int | str):
        """Заглушка: обмен монеты."""
        print(f"[SWAP] Обмен монеты {coin_id} на {target}")

    async def _transfer_to_exchange(self, coin_id: int, target: int | str):
        """Заглушка: перевод на другую биржу."""
        print(f"[TRANSFER] Перевод монеты {coin_id} на биржу {target}")
        
        
    
    
    async def update_solution(self, coin_id: int, move_type: bool, limit: float, target: int | str):
        """Обновляет решение от мозга и запускает задачу ожидания."""
        if coin_id in self.conditions:
            self.solutions[coin_id] = (move_type, limit, target)

            condition = self._get_condition(coin_id)
            async with condition:
                condition.notify_all() 
        
        
    async def update_trade_solution(self, coin_id: int, target_coin_id: int, rate: float):
        # Проверяем, разрешено ли обновление для этой монеты
        if coin_id not in self.traceable_coins:
            return  # или можно вызвать raise, если это ошибка

        # Обновляем решение для пары

        # Если coin_id — это USDT, проверяем и управляем подпиской
        if coin_id == self.USDT:
            await self._manage_usdt_subscription(target_coin_id)

        self.solutions[coin_id] = (0, rate, target_coin_id)
        # Уведомляем ожидающие задачи
        condition = self._get_condition(coin_id)
        async with condition:
            condition.notify_all()

    async def _manage_usdt_subscription(self, new_target_coin_id: int):
        """Управляет подпиской для USDT на основе текущего и нового таргета."""
        current_solution = self.solutions.get(self.USDT)

        if current_solution:
            _, _, current_target = current_solution
            if current_target != new_target_coin_id:
                
                await self.unsubscribe_from_the_brain(current_target)
                await self.subscribe_to_the_brain(new_target_coin_id)
        else:
            # Если решения не было — подписываемся впервые
            await self.subscribe_to_the_brain(new_target_coin_id)
                
            
        
    async def update_price(self, coin: str, new_value: float) -> None:
        if coin in self._coins:
            coin_id = self._coins[coin]
            old_balance = self.wallet.get(coin_id, 0)
            self.wallet[coin_id] = old_balance + new_value
            if coin_id not in self.tusks:
                await self._start_wait_task(coin_id)
            
            condition = self._get_condition(coin_id)
            async with condition:
                condition.notify_all() 
                
            await self.subscribe_to_the_brain()
                