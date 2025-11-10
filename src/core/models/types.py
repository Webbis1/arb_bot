from typing import TypeAlias

from core.interfaces import Exchange


COIN_NAME: TypeAlias = str
COIN_ID: TypeAlias = int
PROFIT: TypeAlias = float
PRICE: TypeAlias = float


amount: TypeAlias = float
EXCHANGE_NAME: TypeAlias = str
adress: TypeAlias = str
DEPARTURE: TypeAlias = Exchange 
"""Биржа отправления"""
DESTINATION: TypeAlias = Exchange
"""Биржа назначения"""