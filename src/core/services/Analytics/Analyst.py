from abc import ABC, abstractmethod
from sortedcollections import ValueSortedDict
from dataclasses import dataclass, field

from frozendict import frozendict
# from asyncio import Queue
from asyncio import Condition
from core.models.types import *

import asyncio
import logging


from core.interfaces.Dto import Recommendation, Trade, Transfer, Wait
from core.models import Coin, Deal, CoinPair
from core.interfaces import Exchange, ExchangeDict, All_prices, Departure, Destination, SellCommission, BuyCommission
from core.protocols import AnalistSubscriber, PriceSubscriber

# @dataclass
class Analyst:
    # exchenges: ExchangeDict = field()
    """ dict[str, Exchange]"""
    # _coin_pair: CoinPair = field()
    """ bidict[int, Coin] """
    # sell_commissions: SellCommission = field()
    """ frozendict[Coin, frozendict[Exchange, float]]"""
    # buy_commissions: BuyCommission = field()
    """ dict[Coin, dict[Exchange, float]]"""
    # _threshold: float = field(default=0.002)
    
    # _coin_list: dict[Coin, dict[Exchange, float]] = field(default_factory=dict)
    # _coin_locks: dict[Coin, asyncio.Lock] = field(default_factory=dict)
    
    # logger: logging.Logger = field(default_factory=lambda: logging.getLogger('analyst'))
    
    
    
    def __init__(self, exchenges: ExchangeDict, coin_pair: CoinPair, sell_commissions: SellCommission, buy_commissions: BuyCommission, threshold: float = 0.002) -> None:
        self.exchenges = frozendict(exchenges)
        self._coin_pair = frozendict(coin_pair)
        self.sell_commissions = frozendict(sell_commissions)
        self.buy_commissions = frozendict(buy_commissions)
        self.threshold = threshold
        self._coin_locks: dict[coin_id, asyncio.Lock] = {}
        self._coin_list: dict[Coin, dict[Exchange, float]] = {}
        self.logger = logging.getLogger('analyst')
        self.usdt_subscribers: set[AnalistSubscriber] = set()
        self.other_subscribers: set[AnalistSubscriber] = set()
        self.__post_init__()
        self._usdt_lock = asyncio.Lock()
        self._other_lock = asyncio.Lock()
        
        self._usdt_condition = Condition()
        self._other_condition = Condition()
        
        
        for coin in set(coin_pair.values()):
            if coin.name == "USDT":
                self.USDT: Coin = coin
        
    
    @property
    def coin_pair(self):
        return self._coin_pair
    
    # @property
    # def threshold(self) -> float:
    #     return self._threshold
    
    @property
    def coin_locks(self) -> dict[coin_id, asyncio.Lock]:
        return self._coin_locks
    
    @property
    def coin_list(self) -> dict[Coin, dict[Exchange, float]]:
        return self._coin_list
    
    def __post_init__(self):
        self.sorted_coin: ValueSortedDict[coin_id, tuple[Departure, Destination, float]] =  ValueSortedDict(lambda value: value[2]) #type: ignore
 
        
        coins_set = set(self._coin_pair.values())
        
        for coin in coins_set:
            lock = self.coin_locks.get(coin)
            if lock is None or not isinstance(lock, asyncio.Lock):
                self._coin_locks[coin] = asyncio.Lock()
                
            price = self.coin_list.get(coin)
            if price is None or not isinstance(price, dict):
                self._coin_list[coin] = {}
        
        
        if not self.check_initialized():
            raise ValueError("Analyst is not properly initialized.")
 
    def check_initialized(self) -> bool:
        try:
            exchanges_set = set(self.exchenges.values())
            coins_set = set(self._coin_pair.values())

            def _validate_commissions(comm: frozendict[Coin, frozendict[Exchange, float]], table_name: str) -> None:
                for c in list(comm.keys()):
                    if c not in coins_set:
                        raise ValueError(f"Unexpected coin {c} in {table_name}")

                for coin in coins_set:
                    if coin not in comm or not isinstance(comm[coin], dict):
                        raise ValueError(f"Missing commission data for coin {coin} in {table_name}")

                    for ex in list(comm[coin].keys()):
                        if ex not in exchanges_set:
                            raise ValueError(f"Unexpected exchange {ex} for coin {coin} in {table_name}")

                    for ex in exchanges_set:
                        if ex not in comm[coin]:
                            raise ValueError(f"Missing commission for coin {coin} on exchange {ex} in {table_name}")
                        else:
                            val = comm[coin][ex]
                            if val is None:
                                raise ValueError(f"Commission for coin {coin} on exchange {ex} in {table_name} is None")
                            elif not isinstance(val, float):
                                raise ValueError(f"Commission for coin {coin} on exchange {ex} in {table_name} is not float")

            _validate_commissions(self.sell_commissions, "sell_commissions")
            _validate_commissions(self.buy_commissions, "buy_commissions")

            return True

        except Exception as e:
            self.logger.error(f"Initialization check failed: {e}")
            return False
    
    

    async def get_all_benefits(self, buy_exchange: Exchange, coin: Coin) -> Deal | None:
        deal: Deal = Deal(
            coin=coin,
            departure=buy_exchange,
            destination=buy_exchange,
            benefit=-float('inf')
        )
        
        for exchange in self.coin_list[coin]:
            if exchange == buy_exchange: continue
            benefit = self.__benefit(buy_exchange, exchange, coin)
            if benefit is not None and benefit >= deal.benefit:
                deal.destination = exchange
                deal.benefit = benefit
                
        if deal.benefit == -float('inf'):
            self.logger.error(f"Could not find any valid benefit for coin {coin} from exchange {buy_exchange}")
            return None
        return deal

    async def get_best_deal(self) -> Deal | None:
        best_coin: Coin
        if len(self.sorted_coin) == 0:
            return None
        best_coin, exchanges_data = self.sorted_coin.peekitem(-1) # type: ignore
        if exchanges_data is None or len(exchanges_data) != 3:
            return None
        
        buy_exchange: Departure = exchanges_data[0]
        sell_exchange: Destination = exchanges_data[1] 
        best_benefit: float = exchanges_data[2]
        
        deal = Deal(
            coin=best_coin,
            departure=buy_exchange,
            destination=sell_exchange,
            benefit=best_benefit
        )
        return deal 

    async def get_all_prices(self) -> All_prices:
        all_prices: All_prices = {}
        for coin, exchange_prices in self.coin_list.items():
            for exchange, price in exchange_prices.items():
                if exchange not in all_prices:
                    all_prices[exchange] = {}
                all_prices[exchange][coin] = price
        return all_prices
    
    async def start(self):
        self.logger.info("Starting data collection")
        
        for _, exchange in self.exchenges.items():
            @dataclass
            class Subscriber(PriceSubscriber):
                analyst: Analyst
                exchange: Exchange
                
                async def on_price_update(self, coin_id: int, value: float) -> None:
                    if coin_id in self.analyst.coin_list and isinstance(value, float) and value > 0:
                        async with self.analyst.coin_locks[coin_id]:
                            self.analyst._coin_list[coin_id][self.exchange] = value
                            
                            try:
                                benefit = await self.analyst._coin_culc(coin_id)
                                
                                if benefit is not None:
                                    self.analyst.sorted_coin[coin_id] = benefit
                            except Exception as e:
                                self.analyst.logger.error(f"Error recalculating {coin.name}: {e}")
                    else:
                        self.analyst.logger.error(f"Invalid price update for {coin.name} on {self.exchange}: {value}")
            
            await exchange.subscribe_price(Subscriber(self, exchange))
        
        self.logger.info("Monitoring started")
        
    async def _coin_culc(self, coin: Coin) -> tuple[Departure, Destination, float] | None:
        if len(self.coin_list[coin]) < 2:
            return None
        
        buy_ex: Exchange | None = self.__find_min_element_for_coin(coin)
        if buy_ex is None:
            self.logger.error(f"Could not determine buy exchange for coin {coin}")
            return None
        
        buy_exchange: Departure = buy_ex
        peak_point: float = -float('inf')
        sell_exchange: Destination | None = None
        
        for exchange in self._coin_list[coin]:
            benefit = self.__benefit(buy_exchange, exchange, coin)
            if benefit is not None and benefit >= peak_point:
                sell_exchange = exchange
                peak_point = benefit
        
        if sell_exchange is None:
            self.logger.error(f"Could not determine sell exchange for coin {coin}")
            return None
        
        return buy_exchange, sell_exchange, peak_point
    
    def __find_min_element_for_coin(self, coin: Coin) -> Exchange | None:
        if coin not in self.coin_list:
            self.logger.error(f"Coin {coin} not found in coin list")
            return None
        elif len(self.coin_list[coin]) == 0:
            self.logger.error(f"No exchanges available for coin {coin}")
            return None
        else:
            exchanges_prices: dict[Exchange, float] = self.coin_list[coin]
            min_exchange: Exchange = min(exchanges_prices, key=exchanges_prices.__getitem__)
            return min_exchange
                
    def __benefit(self, buy_exchange: Departure, sell_exchange: Destination, coin: Coin) -> float | None:
        try:
            procedure_time = 1.0
            
            if procedure_time is None or procedure_time <= 0:
                return None
                
            roi = self.__roi(buy_exchange, sell_exchange, coin)
            if roi is None:
                return None
            return roi / procedure_time
            
        except ZeroDivisionError:
            self.logger.error(f"Procedure time is zero for coin {coin} between {buy_exchange} and {sell_exchange}")
            return None
        except Exception:
            self.logger.error(f"Unexpected error calculating benefit for coin {coin} between {buy_exchange} and {sell_exchange}")
            return None

    def __roi(self, buy_exchange: Departure, sell_exchange: Destination, coin: Coin) -> float | None:
        try:
            buy_commission: float = self.buy_commissions[coin][buy_exchange]
            sale_commission: float = self.sell_commissions[coin][sell_exchange]
            buy_price: float = self.coin_list[coin][buy_exchange]
            sale_price: float = self.coin_list[coin][sell_exchange]
            
            roi = ((sale_price * (1.0 - sale_commission) * (1.0 - buy_commission)) / buy_price) - 1
                
            return roi
        
        except KeyError as e:
            self.logger.error(f"Missing data for ROI calculation: {e}")
            return None
        except ZeroDivisionError:
            self.logger.error(f"Zero buy price for {coin} on {buy_exchange}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in ROI calculation: {e}")
            return None