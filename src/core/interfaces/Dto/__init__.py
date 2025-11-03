from typing import TypeAlias
from frozendict import frozendict

from core.models import Coin
from core.interfaces import Exchange

Coins = set[Coin]
CoinDict = dict[Coin, float]
ExchangeDict = dict[str, Exchange]
All_prices = dict[Exchange, CoinDict]


    
Departure: TypeAlias = Exchange 
"""Биржа отправления"""
Destination: TypeAlias = Exchange
"""Биржа назначения"""


TransferCommission: TypeAlias = frozendict[Coin, frozendict[Departure, frozendict[Destination, float]]]
SellCommission: TypeAlias = frozendict[Coin, frozendict[Exchange, float]]
BuyCommission: TypeAlias = frozendict[Coin, frozendict[Exchange, float]]
