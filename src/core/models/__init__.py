from typing import TypeAlias

from core.interfaces import Exchange
from .Coin import Coin
from .Deal import Deal


Departure: TypeAlias = Exchange 
"""Биржа отправления"""
Destination: TypeAlias = Exchange
"""Биржа назначения"""


TransferCommission: TypeAlias = dict[Coin, dict[Departure, dict[Destination, float]]]
SellCommission: TypeAlias = dict[Coin, dict[Exchange, float]]
BuyCommission: TypeAlias = dict[Coin, dict[Exchange, float]]