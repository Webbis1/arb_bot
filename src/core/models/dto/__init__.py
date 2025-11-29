from typing import TypeAlias


from core.interfaces.IExchange import IExchange
from core.models.Coins import Coin


from .Trade import Trade
from .Transfer import Transfer
from .Wait import Wait


from core.models.types import COIN_ID, COIN_NAME, AMOUNT, EXCHANGE_NAME

Recommendation: TypeAlias = Trade | Transfer | Wait
Coins = set[Coin]
CoinDict = dict[Coin, float]
ExchangeDict = dict[EXCHANGE_NAME, IExchange]
All_prices = dict[IExchange, dict[COIN_ID, float]]


DEPARTURE: TypeAlias = IExchange
DESTINATION: TypeAlias = IExchange
    



TransferCommission: TypeAlias = dict[Coin, dict[DEPARTURE, dict[DESTINATION, float]]]
SellCommission: TypeAlias = dict[COIN_ID, dict[IExchange, float]]
BuyCommission: TypeAlias = dict[COIN_ID, dict[IExchange, float]]
