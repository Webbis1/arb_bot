from typing import TypeAlias
from frozendict import frozendict

from core.models import Coin
from core.interfaces import Exchange
from .Trade import Trade
from .Transfer import Transfer
from .Wait import Wait

# from core.models.types import *

from core.models.types import COIN_ID, DEPARTURE, DESTINATION, COIN_NAME, amount, EXCHANGE_NAME

Recommendation: TypeAlias = Trade | Transfer | Wait
Coins = set[Coin]
CoinDict = dict[Coin, float]
ExchangeDict = dict[EXCHANGE_NAME, Exchange]
All_prices = dict[Exchange, dict[COIN_ID, float]]


    



TransferCommission: TypeAlias = dict[Coin, dict[DEPARTURE, dict[DESTINATION, float]]]
SellCommission: TypeAlias = dict[COIN_ID, dict[Exchange, float]]
BuyCommission: TypeAlias = dict[COIN_ID, dict[Exchange, float]]
