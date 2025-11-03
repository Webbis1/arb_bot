from .Types import Assets, ScoutHead, Coin, Exchange
from .Guide import Guide
from typing import Dict, Optional, Any, AsyncIterator, List
import asyncio
from sortedcollections import ValueSortedDict
from datetime import datetime
import logging

class Analyst:
    def __init__(self, scout: 'ScoutHead', guide: 'Guide', threshold: float = 0.002):
        self.scout: 'ScoutHead' = scout
        self.coin_list: Dict[Coin, Dict[Exchange, float]] = {}
        self.threshold = threshold
        self.guide = guide
        self.coin_locks: Dict[Coin, asyncio.Lock] = {}
        self.sorted_coin: ValueSortedDict[Coin, tuple[Exchange, Exchange, float]] = ValueSortedDict(lambda value: value[2])
        self.logger = logging.getLogger('analyst')

    async def analyse(self, exchange: Exchange, coin: Coin):
        if coin == 1: 
            return await self._usdt_analyse(exchange)
        else:
            return await self._other_analyse(exchange, coin)
        
    async def _usdt_analyse(self, exchange: Exchange):
        worst_coin, (buy_exchange, _, worst_benefit) = self.sorted_coin.peekitem(-1)
        if(worst_benefit >= self.threshold):
            if exchange == buy_exchange:
                answer = {
                    'recommendation': "trade",
                    'buying': worst_coin.name
                }
                return answer
            else:
                answer = {
                    'recommendation': "transfer",
                    'destination': buy_exchange.name
                }
                return answer
        else:
            answer = {
                'recommendation': "wait",
                'time': 10
            }
            return answer
    
    async def _other_analyse(self, current_exchange: Exchange, coin: Coin):
        buy_exchange = current_exchange
        peak_point: float = -float('inf')
        sell_exchange: Exchange = None
        
        for exchange in self.coin_list[coin]:
            benefit = self.__benefit(buy_exchange, exchange, coin)
            if benefit is not None and benefit >= peak_point:
                sell_exchange = exchange
                peak_point = benefit
        
        if sell_exchange is None:
            raise ValueError(f"No suitable sell exchange found for coin {coin}")
        
        if current_exchange == sell_exchange:
            answer = {
                    'recommendation': "trade",
                    'buying': 'USDT'
                }
            return answer
        else:
            if(peak_point >= self.threshold):   
                answer = {
                    'recommendation': "transfer",
                    'destination': sell_exchange.name
                }
                return answer
            else:
                answer = {
                    'recommendation': "trade",
                    'buying': 'USDT'
                }
                return answer
            
    def __find_min_element_for_coin(self, coin: Coin) -> Exchange:
        try:
            exchanges_prices = self.coin_list[coin]
            min_exchange = min(exchanges_prices, key=exchanges_prices.get)
            return min_exchange
        
        except KeyError:
            raise ValueError(f"No data for coin {coin}")
        except ValueError:
            raise ValueError(f"No exchanges for coin {coin}")
    
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
            
            # if update_count % 1000 == 0:
                # self.logger.info(f"Processed {update_count} updates")
    
    async def _coin_culc(self, coin: Coin) -> tuple[Exchange, Exchange, float]:
        async with self.coin_locks[coin]:
            buy_exchange = self.__find_min_element_for_coin(coin)
            peak_point: float = -float('inf')
            sell_exchange: Exchange = None
            
            for exchange in self.coin_list[coin]:
                benefit = self.__benefit(buy_exchange, exchange, coin)
                if benefit is not None and benefit >= peak_point:
                    sell_exchange = exchange
                    peak_point = benefit
            
            if sell_exchange is None:
                raise ValueError(f"No suitable sell exchange found for coin {coin}")
            
            return buy_exchange, sell_exchange, peak_point
                
    def __benefit(self, buy_exchange: Exchange, sell_exchange: Exchange, coin: Coin) -> float | None:
        try:
            procedure_time = self.guide.transfer_time.get(coin, {}).get(buy_exchange, {}).get(sell_exchange)
            
            if procedure_time is None or procedure_time <= 0:
                return None
                
            roi = self.__roi(buy_exchange, sell_exchange, coin)
            return roi / procedure_time
            
        except ZeroDivisionError:
            return None
        except Exception:
            return None

    def __roi(self, buy_exchange: Exchange, sell_exchange: Exchange, coin: Coin) -> float:
        try:
            buy_commission = self.guide.buy_commission[coin][buy_exchange]
            sale_commission = self.guide.sell_commission[coin][sell_exchange]
            buy_price = self.coin_list[coin][buy_exchange]
            sale_price = self.coin_list[coin][sell_exchange]
            
            if buy_price == 0 or sale_price == 0:
                return 0.0
            
            commission: float = (1.0 - sale_commission) * (1.0 - buy_commission)
            effective_sale = ((1 * sale_price) / buy_price) * commission
            roi = (effective_sale - 1) / 1
                
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
        
    async def __aenter__(self):
        self.logger.info("Starting analyst")
        self.coin_list: dict[Coin, dict[Exchange, float]] = await self.scout.coin_list()
        self.logger.info(f"Initial data collected for {len(self.coin_list)} coins")
        
        for coin in self.coin_list:
            self.coin_locks[coin] = asyncio.Lock()
            self.sorted_coin[coin] = await self._coin_culc(coin)
            
        worst_coin, (buy_exchange, sale_exchange, worst_benefit) = self.sorted_coin.peekitem(-1)
        self.logger.info(f"Best opportunity: buy {worst_coin} on {buy_exchange}, sell on {sale_exchange}, profit: {worst_benefit*100:.2f}%")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("Analyst stopped")