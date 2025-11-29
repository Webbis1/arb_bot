import asyncio
from contextlib import _AsyncGeneratorContextManager
import functools
from typing import Any

import aiohttp
import ccxt

from ccxt.pro import Exchange as CcxtProExchange

from core.models.ExchangeBase import ExchangeBase
from infrastructure.Connection import Connection


class CcxtExchangModel(ExchangeBase):
    def __init__(self, name: str, conn: Connection):
        ExchangeBase.__init__(self, name)
        self.__ex: Connection = conn
        
    @property
    def instance(self) -> Connection:
        return self.__ex
    
    @property
    def connection(self) -> _AsyncGeneratorContextManager[CcxtProExchange | None, None]:
        return self.instance.exchange()