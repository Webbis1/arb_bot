from abc import ABC, abstractmethod
from sortedcollections import ValueSortedDict
from dataclasses import dataclass, field

import asyncio
import logging

from core.models import Coin, Deal, TransferCommission, SellCommission, BuyCommission, Departure, Destination
from core.interfaces import Exchange, ExchangeDict, All_prices

@dataclass
class Analyst:
    exchenges: ExchangeDict
    transfer_commission: TransferCommission
    sell_commissions: SellCommission  
    buy_commissions: BuyCommission
    threshold: float = 0.002
    
    coin_list: dict[Coin, dict[Exchange, float]] = field(default_factory=dict)
    coin_locks: dict[Coin, asyncio.Lock] = field(default_factory=dict)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger('analyst'))
    
    def __post_init__(self):
        self.sorted_coin: ValueSortedDict = ValueSortedDict(lambda value: value[2])  # type: ignore
    
    
    @abstractmethod
    async def start_analysis(self, exchange: Exchange, coin: Coin) -> None: ...
    
    @abstractmethod
    async def stop_analysis(self, exchange: Exchange, coin: Coin) -> None: ...
    
    @abstractmethod
    async def get_all_prices(self) -> All_prices: ...
    
    @abstractmethod
    async def get_best_deal(self) -> Deal: ...
    
    async def start_update(self):
        self.logger.info("Starting data collection")
        
        await self.scout.start_monitoring()
        self.logger.info("Monitoring started")
        
        update_count = 0
        async for update_coin in self.scout.coin_update():
            update_count += 1
            exchange: Exchange = update_coin[0]
            coin: Coin = update_coin[1].currency
            new_price: float = update_coin[1].amount
            
            self.coin_list[coin][exchange] = new_price
            
            try:
                self.sorted_coin[coin] = await self._coin_culc(coin)
            except Exception as e:
                self.logger.error(f"Error recalculating {coin.name}: {e}")
    
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