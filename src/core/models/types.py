from typing import TypeAlias

from core.interfaces import Exchange


COIN_NAME: TypeAlias = str
COIN_ID: TypeAlias = int
PROFIT: TypeAlias = float
PRICE: TypeAlias = float
FEE: TypeAlias = float
CHAIN: TypeAlias = str

BALANCE: TypeAlias = float

amount: TypeAlias = float
EXCHANGE_NAME: TypeAlias = str

DEPARTURE_NAME: TypeAlias = EXCHANGE_NAME
DESTINATION_NAME: TypeAlias = EXCHANGE_NAME


ADDRESS: TypeAlias = str
DEPARTURE: TypeAlias = Exchange 
"""Биржа отправления"""
DESTINATION: TypeAlias = Exchange
"""Биржа назначения"""