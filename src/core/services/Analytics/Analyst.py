from abc import ABC, abstractmethod
from sortedcollections import ValueSortedDict
from dataclasses import dataclass, field
from typing import cast

import asyncio
import logging

from core.models import Coin, Deal
from core.interfaces import Exchange, ExchangeDict, All_prices, Departure, Destination, SellCommission, BuyCommission
from core.protocols import PriceSubscriber

@dataclass
class Analyst:
    exchenges: ExchangeDict
    sell_commissions: SellCommission  
    buy_commissions: BuyCommission
    threshold: float = 0.002
    
    coin_list: dict[Coin, dict[Exchange, float]] = field(default_factory=dict)
    coin_locks: dict[Coin, asyncio.Lock] = field(default_factory=dict)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger('analyst'))
    


    def __post_init__(self):
        self.sorted_coin = cast(
            ValueSortedDict[Coin, tuple[Departure, Destination, float]], # type: ignore
            ValueSortedDict(lambda value: value[2])
        ) 
        
    
    
  
    async def get_best_deal(self) -> Deal:
        best_coin: Coin
        best_coin, exchanges_data = self.sorted_coin.peekitem(-1) # type: ignore
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
    
    @abstractmethod
    async def start_analysis(self, exchange: Exchange, coin: Coin) -> None: ...
    
    @abstractmethod
    async def stop_analysis(self, exchange: Exchange, coin: Coin) -> None: ...
    
    

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
                
                async def on_price_update(self, coin: Coin, value: float) -> None:
                    if coin not in self.analyst.coin_list:
                        self.analyst.coin_list[coin] = {}
                        self.analyst.coin_locks[coin] = asyncio.Lock()
                    
                    self.analyst.coin_list[coin][self.exchange] = value
                    
                    try:
                        self.analyst.sorted_coin[coin] = await self.analyst._coin_culc(coin) # TODO: может быть None
                    except Exception as e:
                        self.analyst.logger.error(f"Error recalculating {coin.name}: {e}")
            
            await exchange.subscribe_price(Subscriber(self, exchange))
        
        self.logger.info("Monitoring started")
        
    async def _coin_culc(self, coin: Coin) -> tuple[Departure, Destination | None, float]:
        async with self.coin_locks[coin]:
            buy_exchange: Departure = self.__find_min_element_for_coin(coin)
            peak_point: float = -float('inf')
            sell_exchange: Destination | None = None
            
            for exchange in self.coin_list[coin]:
                benefit = self.__benefit(buy_exchange, exchange, coin)
                if benefit is not None and benefit >= peak_point:
                    sell_exchange = exchange
                    peak_point = benefit
            
            if sell_exchange is None:
                raise ValueError(f"No suitable sell exchange found for coin {coin}")
            
            return buy_exchange, sell_exchange, peak_point
    
    def __find_min_element_for_coin(self, coin: Coin) -> Exchange:
        try:
            exchanges_prices: dict[Exchange, float] = self.coin_list[coin]
            if not exchanges_prices:
                raise ValueError(f"No exchanges for coin {coin}")
            min_exchange: Exchange = min(exchanges_prices, key=exchanges_prices.__getitem__)
            return min_exchange
        
        except KeyError:
            raise ValueError(f"No data for coin {coin}")
        except ValueError:
            raise ValueError(f"No exchanges for coin {coin}")
                
    def __benefit(self, buy_exchange: Departure, sell_exchange: Destination, coin: Coin) -> float | None:
        try:
            procedure_time = 1.0
            
            if procedure_time is None or procedure_time <= 0:
                return None
                
            roi = self.__roi(buy_exchange, sell_exchange, coin)
            return roi / procedure_time
            
        except ZeroDivisionError:
            return None
        except Exception:
            return None

    def __roi(self, buy_exchange: Departure, sell_exchange: Destination, coin: Coin) -> float:
        try:
            buy_commission: float = self.buy_commissions[coin][buy_exchange]
            sale_commission: float = self.sell_commissions[coin][sell_exchange]
            buy_price: float = self.coin_list[coin][buy_exchange]
            sale_price: float = self.coin_list[coin][sell_exchange]
            
            if buy_price == 0 or sale_price == 0:
                return 0.0
            
            roi = ((sale_price * (1.0 - sale_commission) * (1.0 - buy_commission)) / buy_price) - 1
                
            return roi
            
        except KeyError as e:
            self.logger.error(f"Missing data for ROI calculation: {e}")
            return 0.0
        except ZeroDivisionError:
            self.logger.error(f"Zero buy price for {coin} on {buy_exchange}")
            return 0.0
        except Exception as e:
            self.logger.error(f"Unexpected error in ROI calculation: {e}")
            return 0.0