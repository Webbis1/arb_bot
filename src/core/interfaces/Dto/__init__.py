from typing import TypeAlias
from frozendict import frozendict

from core.models import Coin
from core.interfaces import Exchange
from .Trade import Trade
from .Transfer import Transfer
from .Wait import Wait


Recommendation: TypeAlias = Trade | Transfer | Wait
Coins = set[Coin]
CoinDict = dict[Coin, float]
ExchangeDict = dict[str, Exchange]
All_prices = dict[Exchange, CoinDict]


    
Departure: TypeAlias = Exchange 
"""Биржа отправления"""
Destination: TypeAlias = Exchange
"""Биржа назначения"""


TransferCommission: TypeAlias = dict[Coin, dict[Departure, dict[Destination, float]]]
SellCommission: TypeAlias = dict[Coin, dict[Exchange, float]]
BuyCommission: TypeAlias = dict[Coin, dict[Exchange, float]]
