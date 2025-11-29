import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
import logging
import pickle
from typing import ValuesView 

from bidict import ValueDuplicationError, bidict

from core.interfaces import Exchange
from core.models.dto import Coins, ExchangeDict
from core.models import Coin
from core.models.Deal import Deal
from core.models.types import CHAIN, COIN_ID, DEPARTURE_NAME, DESTINATION_NAME, FEE, ADDRESS, EXCHANGE_NAME, COIN_NAME

logger = logging.getLogger(__name__)


class Mapper:
    def __init__(self):
        self.__name_iter: COIN_ID = 0
        self._all_coins: bidict[Coin, COIN_ID] = bidict()
        self._ex_coins: dict[EXCHANGE_NAME, defaultdict[COIN_ID, set[Coin]]] = defaultdict(lambda: defaultdict(set))
        self._ex_coin_dict: defaultdict[EXCHANGE_NAME, dict[ADDRESS, tuple[COIN_NAME, CHAIN]]] = defaultdict(dict)

        self._all_coin_names: defaultdict[EXCHANGE_NAME, bidict[COIN_NAME, COIN_ID]] = defaultdict()
        self._usdt: int | None = None

        self._best_transfer: defaultdict[DEPARTURE_NAME, dict[DESTINATION_NAME, dict[COIN_ID, Coin]]] = defaultdict(lambda: defaultdict(dict))
        
    
    @property
    def next_id(self) -> COIN_ID:
        self.__name_iter += 1
        logger.debug(f"Generated new unique ID: {self.__name_iter}")
        return self.__name_iter

    async def generate_data(self, exchanges: ValuesView[Exchange]) -> None:
        address_id: dict[str, COIN_ID] = {}

        logger.info("Starting data generation for exchanges.")
        
        # Создаем задачи для всех exchanges
        tasks = []
        for departure in exchanges:
            logger.debug(f"Creating task for exchange: {departure.name}")
            task = asyncio.create_task(departure.get_current_coins())
            tasks.append((departure, task))

        # Ждем завершения всех задач
        results = []
        for departure, task in tasks:
            try:
                coins = await task
                results.append((departure, coins))
            except Exception as e:
                logger.error(f"Error getting coins from {departure.name}: {e}")
                results.append((departure, None))

        # Обрабатываем результаты
        for departure, coins in results:
            if coins is not None:
                logger.debug(f"Processing exchange: {departure.name}")
                current_exchange_name_id: bidict[COIN_NAME, COIN_ID] = bidict()
            
            
            if not coins:
                logger.warning(f"No coins returned from {departure.name}. Skipping.")
                continue

            self._all_coin_names[departure.name] = bidict()
            # self._exchanges[departure.name] = departure
            self._ex_coin_dict[departure.name] = {}
            
            for coin_name, coin_set in coins.items():
                c_id: COIN_ID = self.next_id
                normal_coins: set[Coin] = set()
                for coin in coin_set:
                    if not coin.address or not coin.name or coin.fee < 0 or coin.chain == "Aptos" or coin.chain == "ETH" or coin.chain == "ERC20":
                        continue
                    else: normal_coins.add(coin)
                        
                    if coin.address in address_id:
                        c_id = address_id[coin.address]
                        logger.debug(f"Found existing ID {c_id} for coin address '{coin.address}' in global address_id.")
                        break
                
                if coin_name not in current_exchange_name_id: 
                    if c_id in current_exchange_name_id.inverse: logger.debug(f"ex - {departure.name}, name - {coin.name}, address - {coin.address} | in arr {current_exchange_name_id.inverse[c_id]}")
                    else: current_exchange_name_id[coin_name] = c_id
                
                for coin in normal_coins:
                    address_id[coin.address] = c_id
                    self._ex_coins[departure.name][c_id].add(coin) 
                    self._ex_coin_dict[departure.name][coin.address] = coin.name, coin.chain
                
                if coin_name == 'USDT':
                    logger.critical(f"USDT - {c_id} for {departure.name}")

                # TODO: заполнение _all_coins
                
            self._all_coin_names[departure.name] = current_exchange_name_id
        
        def intersection_with_priority(set1: set[Coin], set2: set[Coin]) -> set[Coin]:
            """Пересечение множеств с приоритетом объектов из set1"""
            result = set()
            
            for coin1 in set1:
                for coin2 in set2:
                    if coin1 == coin2:  # Используем перегруженный __eq__
                        result.add(coin1)  # Добавляем экземпляр из set1
                        break
            
            return result
        
        for departure_name, data in self._ex_coins.items():
            for destination_name, data2 in self._ex_coins.items():
                if departure_name == destination_name: continue
                common_coin_ids = set(data.keys()) & set(data2.keys())
                
                from pprint import pprint
                
                # pprint(common_coin_ids)
                print(departure_name + "    ----    " + destination_name)
                for coin_id in common_coin_ids:
                    
                    intersection: set[Coin] = intersection_with_priority(data2[coin_id], data[coin_id])
                    
                    # if coin_id == self.usdt and departure_name == 'kucoin' and destination_name == 'okx':
                    #     print('from - ' +  destination_name)
                    #     pprint(data2[coin_id])
                    #     print('================')
                        
                    #     print('from - ' + departure_name)
                    #     pprint(data[coin_id])
                    #     print('================')
                        
                    #     print('Intersection: ')
                    #     pprint(intersection)
                    
                    
                    if len(intersection):
                        # print(min(intersection))
                        self._best_transfer[departure_name][destination_name][coin_id] = min(intersection)
        
        
        # print(self.print_best_transfer())                     
            
        logger.info(f"Data generation completed. Generated {len(address_id)} unique coin addresses.")

                
    def get_coinID(self): ...
    # name + ex
    
    def get_coin_name_chain_from_ex_by_address(self, address: str, ex: Exchange) -> tuple[COIN_NAME, CHAIN] | None:
        return self._ex_coin_dict.get(ex.name, {}).get(address)
    
    def get_name(self): ...
    
    def get_coinId_by_name_for_ex(self, ex_name: str, coin_name: COIN_NAME) -> int | None:
        return self._all_coin_names.get(ex_name, {}).get(coin_name)
    
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
        
    
    # @property
    # def exchange_set(self) -> set[Exchange]:
    #     return set(self._exchanges.values())
    
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
            raise Exception("USDT not init")
        
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
    
    
    
    
    def save(self, filename: str) -> None:
        """
        Сохраняет состояние объекта Mapper в файл
        
        Args:
            filename (str): Имя файла для сохранения
        """
        # Создаем словарь с данными для сохранения
        data = {
            '_Mapper__name_iter': self.__name_iter,
            '_all_coins': self._all_coins,
            '_ex_coins': dict(self._ex_coins),  # Преобразуем defaultdict в dict
            '_ex_coin_dict': dict(self._ex_coin_dict),  # Преобразуем defaultdict в dict
            '_all_coin_names': dict(self._all_coin_names),  # Преобразуем defaultdict в dict
            '_usdt': self._usdt,
            '_best_transfer': dict(self._best_transfer)  # Преобразуем defaultdict в dict
        }
        
        with open(filename, 'wb') as f:
            pickle.dump(data, f)
    
    def load(self, filename: str) -> None:
        """
        Загружает состояние объекта Mapper из файла
        
        Args:
            filename (str): Имя файла для загрузки
        """
        try:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
            
            # Восстанавливаем атрибуты
            self.__name_iter = data['_Mapper__name_iter']
            self._all_coins = data['_all_coins']
            
            # Восстанавливаем defaultdict с правильными фабричными функциями
            self._ex_coins = defaultdict(lambda: defaultdict(set))
            self._ex_coins.update(data['_ex_coins'])
            
            self._ex_coin_dict = defaultdict(dict)
            self._ex_coin_dict.update(data['_ex_coin_dict'])
            
            self._all_coin_names = defaultdict(bidict)
            self._all_coin_names.update(data['_all_coin_names'])
            
            self._usdt = data['_usdt']
            
            self._best_transfer = defaultdict(lambda: defaultdict(dict))
            self._best_transfer.update(data['_best_transfer'])
            
        except FileNotFoundError:
            print(f"Файл {filename} не найден")
        except Exception as e:
            print(f"Ошибка при загрузке данных: {e}")