from core.models import Coin
from core.interfaces import Exchange

Coins = set[Coin]
CoinDict = dict[Coin, float]
ExchangeDict = dict[str, Exchange]
All_prices = dict[Exchange, CoinDict]