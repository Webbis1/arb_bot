from collections import UserDict

from core.models import Coin

class CoinList(UserDict['Coin', float]): ...



CoinDict = dict[Coin, float]