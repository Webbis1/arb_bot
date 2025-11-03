from typing import TypeAlias
from bidict import bidict
from .Exchange import Exchange
from .Coin import Coin
from .Deal import Deal



CoinPair: TypeAlias = bidict[int, Coin]


