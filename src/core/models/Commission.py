from typing import TypeAlias

from core.models import Coin, ExchangeBase


Commission: TypeAlias = dict[ExchangeBase, dict[ExchangeBase, dict[int, Coin]]]