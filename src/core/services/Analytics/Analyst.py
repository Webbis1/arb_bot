from abc import ABC, abstractmethod
from sortedcollections import ValueSortedDict
from dataclasses import dataclass, field

from frozendict import frozendict
# from asyncio import Queue
from asyncio import Condition
from core.models.types import COIN_ID, COIN_NAME, PRICE, AMOUNT, PROFIT

import asyncio
import logging


from core.models.dto import Recommendation, Trade, Transfer, Wait
from core.models import Coin, Deal, CoinPair
from core.interfaces import Exchange, ExchangeDict, All_prices, DEPARTURE, DESTINATION, SellCommission, BuyCommission
from core.protocols import AnalistSubscriber, PriceSubscriber
from core.services.Mapper import Mapper

class Analyst:
    def __init__(self, mapper: Mapper, threshold: float = 0.002) -> None:
        self.mapper:Mapper = mapper
        self.threshold = threshold
        self._coin_locks: dict[COIN_ID, asyncio.Lock] = {}
        self._coin_list: dict[COIN_ID, dict[Exchange, PRICE]] = {}
        self.logger = logging.getLogger('analyst')
        # self.usdt_subscribers: set[AnalistSubscriber] = set()
        # self.other_subscribers: set[AnalistSubscriber] = set()
        self.__post_init__()
        # self._usdt_lock = asyncio.Lock()
        # self._other_lock = asyncio.Lock()
        
        # self._usdt_condition = Condition()
        # self._other_condition = Condition()
        
    
    @property
    def coin_locks(self) -> dict[COIN_ID, asyncio.Lock]:
        return self._coin_locks
    
    @property
    def coin_list(self) -> dict[COIN_ID, dict[Exchange, PRICE]]:
        return self._coin_list
    
    def __post_init__(self):
        self.sorted_coin: ValueSortedDict[COIN_ID, tuple[DEPARTURE, DESTINATION, PROFIT]] =  ValueSortedDict(lambda value: value[2]) #type: ignore
 
        
        coins_set = self.mapper.analyzed_coins
        
        for coin_id in coins_set:
            lock = self.coin_locks.get(coin_id)
            if lock is None or not isinstance(lock, asyncio.Lock):
                self._coin_locks[coin_id] = asyncio.Lock()
                
            price = self.coin_list.get(coin_id)
            if price is None or not isinstance(price, dict):
                self._coin_list[coin_id] = {}
        
 

    async def get_all_benefits(self, buy_exchange: Exchange, coin_id: COIN_ID) -> Deal | None:
        deal: Deal = Deal(
            coin_id=coin_id,
            departure=buy_exchange,
            destination=buy_exchange,
            benefit=-float('inf')
        )
        
        for exchange in self.coin_list[coin_id]:
            if exchange == buy_exchange: continue
            benefit = self.__benefit(buy_exchange, exchange, coin_id)
            if benefit is not None and benefit >= deal.benefit:
                deal.destination = exchange
                deal.benefit = benefit
                
        if deal.benefit == -float('inf'):
            self.logger.error(f"Could not find any valid benefit for coin ID = {coin_id} from exchange {buy_exchange}")
            return None
        return deal

    async def get_best_deal(self) -> Deal | None:
        best_coin: COIN_ID
        if len(self.sorted_coin) == 0:
            return None
        best_coin, exchanges_data = self.sorted_coin.peekitem(-1) # type: ignore
        if exchanges_data is None or len(exchanges_data) != 3:
            return None
        
        buy_exchange: DEPARTURE = exchanges_data[0]
        sell_exchange: DESTINATION = exchanges_data[1] 
        best_benefit: float = exchanges_data[2]
        
        deal = Deal(
            coin_id=best_coin,
            departure=buy_exchange,
            destination=sell_exchange,
            benefit=best_benefit
        )
        return deal 

    async def get_all_prices(self) -> All_prices:
        all_prices: All_prices = {}
        for coin_id, exchange_prices in self.coin_list.items():
            for exchange, price in exchange_prices.items():
                if exchange not in all_prices:
                    all_prices[exchange] = {}
                all_prices[exchange][coin_id] = price
        return all_prices
    
    async def start(self, exchanges: set[Exchange]):
        self.logger.info("Starting data collection")
        
        for exchange in exchanges:
            # self.logger.info(exchange)
            
            @dataclass
            class Subscriber(PriceSubscriber):
                analyst: Analyst
                exchange: Exchange
                
                def __hash__(self) -> int:
                    string: str = "analyst" + str(self.exchange.__hash__())
                    return hash(string)
                
                async def on_price_update(self, coin_id: COIN_ID, price: float) -> None:
                    if coin_id in self.analyst.coin_list and isinstance(price, float):
                        async with self.analyst.coin_locks[coin_id]:
                            
                            if price > 0:
                                self.analyst._coin_list[coin_id][self.exchange] = price
                                
                                try:
                                    benefit = await self.analyst._coin_culc(coin_id)
                                    
                                    if benefit is not None:
                                        self.analyst.sorted_coin[coin_id] = benefit
                                except Exception as e:
                                    self.analyst.logger.error(f"Error recalculating Coid ID = {coin_id}: {e}")
                            else:
                                if self.exchange in self.analyst.coin_list.get(coin_id, {}):
                                    self.analyst._coin_list[coin_id].pop(self.exchange)
                                
                                    try:   
                                        benefit = await self.analyst._coin_culc(coin_id)
                                        
                                        if benefit is not None:
                                            self.analyst.sorted_coin[coin_id] = benefit
                                    except Exception as e:
                                        self.analyst.logger.error(f"Error recalculating Coid ID = {coin_id}: {e}")
                    else:
                        pass
                        # self.analyst.logger.error(f"Invalid price update for Coin ID = {coin_id} on {self.exchange}: {price}")
            
            await exchange.subscribe_price(Subscriber(self, exchange))
        
        self.logger.info("Monitoring started")
        
    async def _coin_culc(self, coin_id: COIN_ID) -> tuple[DEPARTURE, DESTINATION, PROFIT] | None:
        # self.logger.info(f"Coin culc for {coin_id}")
        if len(self.coin_list[coin_id]) < 2:
            return None
        
        buy_ex: Exchange | None = self.__find_min_element_for_coin(coin_id)
        if buy_ex is None:
            self.logger.error(f"Could not determine buy exchange for coin ID = {coin_id}")
            return None
        
        buy_exchange: DEPARTURE = buy_ex
        peak_point: float = -float('inf')
        sell_exchange: DESTINATION | None = None
        
        for exchange in self._coin_list[coin_id]:
            benefit = self.__benefit(buy_exchange, exchange, coin_id)
            if benefit is not None and benefit >= peak_point:
                sell_exchange = exchange
                peak_point = benefit
        
        if sell_exchange is None:
            self.logger.error(f"Could not determine sell exchange for coin ID = {coin_id}")
            return None
        
        return buy_exchange, sell_exchange, peak_point
    
    def __find_min_element_for_coin(self, coin_id: COIN_ID) -> Exchange | None:
        if coin_id not in self.coin_list:
            self.logger.error(f"Coin ID = {coin_id} not found in coin list")
            return None
        elif len(self.coin_list[coin_id]) == 0:
            self.logger.error(f"No exchanges available for coin ID = {coin_id}")
            return None
        else:
            exchanges_prices: dict[Exchange, float] = self.coin_list[coin_id]
            min_exchange: Exchange = min(exchanges_prices, key=exchanges_prices.__getitem__)
            return min_exchange
                
    def __benefit(self, buy_exchange: DEPARTURE, sell_exchange: DESTINATION, coin_id: COIN_ID) -> float | None:
        try:
            procedure_time = 1.0
            
            if procedure_time is None or procedure_time <= 0:
                return None
                
            roi = self.__roi(buy_exchange, sell_exchange, coin_id)
            if roi is None:
                return None
            return roi / procedure_time
            
        except ZeroDivisionError:
            self.logger.error(f"Procedure time is zero for coin ID = {coin_id} between {buy_exchange} and {sell_exchange}")
            return None
        except Exception:
            self.logger.error(f"Unexpected error calculating benefit for coin ID = {coin_id} between {buy_exchange} and {sell_exchange}")
            return None

    def __roi(self, buy_exchange: DEPARTURE, sell_exchange: DESTINATION, coin_id: COIN_ID) -> float | None:
        try:
            # buy_commission: float = self.buy_commissions[coin_id][buy_exchange] 
            # sale_commission: float = self.sell_commissions[coin_id][sell_exchange]
            sale_commission = 0.01
            buy_commission = 0.01
            buy_price: float = self.coin_list[coin_id][buy_exchange]
            sale_price: float = self.coin_list[coin_id][sell_exchange]
            
            roi = ((sale_price * (1.0 - sale_commission) * (1.0 - buy_commission)) / buy_price) - 1
                
            return roi
        
        except KeyError as e:
            self.logger.error(f"Missing data for ROI calculation: {e}")
            return None
        except ZeroDivisionError:
            self.logger.error(f"Zero buy price for Coin ID = {coin_id} on {buy_exchange}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in ROI calculation: {e}")
            return None