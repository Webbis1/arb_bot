from collections import defaultdict
from dataclasses import dataclass, field
import logging
from typing import ValuesView 

from bidict import ValueDuplicationError, bidict

from core.interfaces import Exchange
from core.interfaces.Dto import Coins, ExchangeDict
from core.models import Coin
from core.models.Deal import Deal
from core.models.types import COIN_ID, DEPARTURE_NAME, DESTINATION_NAME, FEE, adress, EXCHANGE_NAME, COIN_NAME

logger = logging.getLogger(__name__)


class Mapper:
    def __init__(self):
        self.__name_iter: COIN_ID = 0
        self._all_coins: bidict[Coin, COIN_ID] = bidict()
        self._ex_coins: dict[EXCHANGE_NAME, defaultdict[COIN_ID, set[Coin]]] = defaultdict(lambda: defaultdict(set))
    # all_ex: dict[str, set[Coin]]
    # all_adresess: dict[str, int]
    # actual_adresess: dict[str, int]
        self._all_coin_names: defaultdict[EXCHANGE_NAME, bidict[COIN_NAME, COIN_ID]] = defaultdict()
        # self._all_network_names: defaultdict[str, bidict[int, str]]
        self._usdt: int | None = None

        self._best_transfer: defaultdict[DEPARTURE_NAME, dict[DESTINATION_NAME, dict[COIN_ID, Coin]]] = defaultdict(lambda: defaultdict(dict))
        
        self._exchanges: dict[EXCHANGE_NAME, Exchange] = {}
    
    @property
    def next_id(self) -> COIN_ID:
        self.__name_iter += 1
        logger.debug(f"Generated new unique ID: {self.__name_iter}")
        return self.__name_iter

    async def generate_data(self, exchanges: ValuesView[Exchange]) -> None:
        address_id: dict[str, COIN_ID] = {}

        logger.info("Starting data generation for exchanges.")
        
        for ex in exchanges:
            logger.debug(f"Processing exchange: {ex.name}")
            current_exchange_name_id: bidict[COIN_NAME, COIN_ID] = bidict()
            coins: list[Coin] = await ex.get_current_coins()
            
            
            if not coins:
                logger.warning(f"No coins returned from {ex.name}. Skipping.")
                continue

            self._all_coin_names[ex.name] = bidict()
            self._exchanges[ex.name] = ex
            
            
            for coin in coins:
                if not coin.address or not coin.name or coin.fee < 0: continue
                c_id: COIN_ID

                if coin.name in current_exchange_name_id:
                    c_id = current_exchange_name_id[coin.name]
                    logger.debug(f"Found existing ID {c_id} for coin name '{coin.name}' in {ex.name}'s name_id.")
                elif coin.address in address_id:
                    c_id = address_id[coin.address]
                    logger.debug(f"Found existing ID {c_id} for coin address '{coin.address}' in global address_id.")
                else:
                    c_id = self.next_id
                    logger.debug(f"Generated new ID {c_id} for coin '{coin.name}' (address: '{coin.address}').")

                if coin.name not in current_exchange_name_id: 
                    if c_id in current_exchange_name_id.inverse: logger.debug(f"ex - {ex.name}, name - {coin.name}, address - {coin.address} | in arr {current_exchange_name_id.inverse[c_id]}")
                    else: current_exchange_name_id[coin.name] = c_id
                
                address_id[coin.address] = c_id
                
                self._ex_coins[ex.name][c_id].add(coin) 

                # TODO: заполнение _all_coins
                
            self._all_coin_names[ex.name] = current_exchange_name_id
        
        
        for ex, data in self._ex_coins.items():
            for ex2, data2 in self._ex_coins.items():
                if ex == ex2: continue
                common_coin_ids = set(data.keys()) & set(data2.keys())
                
                from pprint import pprint
                
                # pprint(common_coin_ids)
        
                for coin_id in common_coin_ids:
                    intersection: set[Coin] = data2[coin_id] & data[coin_id]
                    
                    # pprint(intersection)
                    if len(intersection):
                        # print(min(intersection))
                        self._best_transfer[ex][ex2][coin_id] = min(intersection)
        
        
        # print(self.print_best_transfer())                     
            
        logger.info(f"Data generation completed. Generated {len(address_id)} unique coin addresses.")

                
    def get_coinID(self): ...
    # name + ex
    
    def get_coin(self): ...
    
    def get_name(self): ...
    
    def get_coinId_by_name_for_ex(self, ex_name: str, coin_name: COIN_NAME) -> int:
        return self._all_coin_names[ex_name][coin_name]
    
    @property
    def all_coins(self) -> set[COIN_ID]:
        return set(self._all_coins.values())
    
    @property
    def analyzed_coins(self) -> set[COIN_ID]:
        ex_sets: dict[EXCHANGE_NAME, set[COIN_ID]] = {}
        
        for ex_name, coin_pair in self._all_coin_names.items():
            ex_sets[ex_name] = set()
            for ex_name2, coin_pair2 in self._all_coin_names.items():
                if ex_name == ex_name2: continue
                intersection: set[COIN_ID] = set(coin_pair.values()) & set(coin_pair2.values())
                ex_sets[ex_name] |= intersection
        
        analyzed_coins: set[COIN_ID] = set()
            
        for coin_set in ex_sets.values():
            analyzed_coins |= coin_set
            
        return analyzed_coins
        
    
    @property
    def exchange_set(self) -> set[Exchange]:
        return set(self._exchanges.values())
    
    def get_coin_id(self, coin: Coin) -> int | None:
        return self._all_coins.get(coin, None)
    
    def get_coin_name_id_for_ex(self, ex_name: EXCHANGE_NAME) -> bidict[COIN_NAME, COIN_ID]:
        return self._all_coin_names.get(ex_name, bidict())
    
    def get_coin_id_by_name(self, ex_name: str, coin_name: str) -> int | None:
        return self._all_coin_names.get(ex_name, {}).get(coin_name)
    
    def get_best_coin_transfer(self, departure_name: str, destination_name: str, coin_id: int) -> Coin | None:
        # logger.warning(f"from {departure_name} to {destination_name} with {coin_id}")
        return self._best_transfer.get(departure_name, {}).get(destination_name, {}).get(coin_id)
    
    def get_fee(self, deal: Deal, coin_id: COIN_ID | None = None) -> FEE | None:
        if coin := self.get_best_coin_transfer(
            deal.departure.name,
            deal.destination.name, 
            coin_id or deal.coin_id
        ):
            return coin.fee if coin.fee >= 0 else None
        return None
    
    def get_all_coinname_by_ex(self, ex_name: str) -> set[str]:
        return set(self._all_coin_names.get(ex_name, {}).keys())
    
    @property
    def usdt(self) -> int:
        if self._usdt is None: 
            for _, names in self._all_coin_names.items():
                if "USDT" in names.keys():
                    # logger.warning(f"Mapper - usdt {names["USDT"]}")
                    self._usdt = names["USDT"]
                    break
                
        if self._usdt is None:
            raise 
        
        # logger.info(f"Mapper usdt is {self._usdt}")
        
        return self._usdt
    
    
    def print_best_transfer(self) -> str:
        """Красивый вывод best_transfer в виде дерева"""
        if not self._best_transfer:
            return "No transfer data available"
        
        result = ["🏗️  Best Transfer Routes:"]
        
        for departure, destinations in self._best_transfer.items():
            result.append(f"┌─ From: {departure}")
            
            dest_list = list(destinations.items())
            for i, (destination, coins) in enumerate(dest_list):
                prefix = "├─" if i < len(dest_list) - 1 else "└─"
                result.append(f"{prefix} To: {destination}")
                
                coin_list = list(coins.items())
                for j, (coin_id, coin) in enumerate(coin_list):
                    sub_prefix = "│  ├─" if i < len(dest_list) - 1 else "   ├─"
                    if j == len(coin_list) - 1:
                        sub_prefix = "│  └─" if i < len(dest_list) - 1 else "   └─"
                    
                    result.append(f"{sub_prefix} Coin {coin_id}: {coin}")
        
        return "\n".join(result)