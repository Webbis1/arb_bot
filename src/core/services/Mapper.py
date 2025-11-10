from collections import defaultdict
from dataclasses import dataclass, field
import logging
from typing import ValuesView 

from bidict import ValueDuplicationError, bidict

from core.interfaces import Exchange
from core.interfaces.Dto import Coins, ExchangeDict
from core.models import Coin
from core.models.types import COIN_ID, adress, EXCHANGE_NAME, COIN_NAME

logger = logging.getLogger(__name__)


class Mapper:
    def __init__(self):
        self.__name_iter: COIN_ID = 0
        self._all_coins: bidict[Coin, int] = bidict()
    # all_ex: dict[str, set[Coin]]
    # all_adresess: dict[str, int]
    # actual_adresess: dict[str, int]
        self._all_coin_names: defaultdict[str, bidict[COIN_NAME, COIN_ID]] = defaultdict()
        # self._all_network_names: defaultdict[str, bidict[int, str]]
    # _usdt: int | None = field(default = None)

        self._best_transfer: defaultdict[str, dict[str, dict[int, Coin]]] = defaultdict(lambda: defaultdict(dict))
        
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
                if not coin.address or not coin.name: continue
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

                # TODO: заполнение _all_coins
                
            self._all_coin_names[ex.name] = current_exchange_name_id
            
        logger.info(f"Data generation completed. Generated {len(address_id)} unique coin addresses.")
        # return address_id, last_name_id
                
    def get_coinID(self): ...
    # name + ex
    
    def get_coin(self): ...
    
    def get_name(self): ...
    
    def get_coinId_by_name_for_ex(self, ex_name: str) -> int: ...
    
    @property
    def all_coins(self) -> set[COIN_ID]:
        return set(self._all_coins.values())
    
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
        return self._best_transfer.get(departure_name, {}).get(destination_name, {}).get(coin_id)
    
    def get_all_coinname_by_ex(self, ex_name: str) -> set[str]:
        return set(self._all_coin_names.get(ex_name, {}).keys())
    
    @property
    def usdt(self) -> int:
        if self._usdt is None: 
            for _, names in self._all_coin_names.items():
                if "USDT" in names.keys():
                    self._usdt = names["USDT"]
                    break
        if self._usdt is None:
            raise 
        
        return self._usdt