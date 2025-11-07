


from collections import defaultdict
from dataclasses import dataclass

from bidict import bidict

from core.models import Coin


@dataclass
class Mapper:
    _all_coins: bidict[Coin, int]
    all_ex: dict[str, set[Coin]]
    all_adresess: dict[str, int]
    actual_adresess: dict[str, int]
    _all_coin_names: defaultdict[str, bidict[str, int]]
    all_network_names: defaultdict[str, bidict[int, str]]

    _best_transfer: defaultdict[str, dict[str, dict[int, Coin]]] = defaultdict(lambda: defaultdict(dict))
    
    
    def get_coin_id(self, coin: Coin) -> int | None:
        return self._all_coins.get(coin, None)
    
    
    def get_coin_id_by_name(self, ex_name: str, coin_name: str) -> int | None:
        return self._all_coin_names.get(ex_name, {}).get(coin_name)
    
    def get_best_coin_transfer(self, departure_name: str, destination_name: str, coin_id: int) -> Coin | None:
        return self._best_transfer.get(departure_name, {}).get(destination_name, {}).get(coin_id)
    
    def get_all_coinname_by_ex(self, ex_name: str) -> set[str]:
        return set(self._all_coin_names.get(ex_name, {}).keys())