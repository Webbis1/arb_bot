from typing import TypeAlias

from core.models import Coin, Exchange


Commission: TypeAlias = dict[Exchange, dict[Exchange, dict[int, Coin]]]