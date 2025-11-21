import asyncio
from contextlib import _AsyncGeneratorContextManager
import functools
from typing import Any

import aiohttp
import ccxt
from core.models import Exchange
from ccxt.pro import Exchange as CcxtProExchange

from infrastructure.ErrorHandlerServices.Connection import Connection


class CcxtExchangModel(Exchange):
    def __init__(self, name: str, conn: Connection):
        Exchange.__init__(self, name)
        self.__ex: Connection = conn
        
    @property
    def instance(self) -> Connection:
        return self.__ex
    
    @property
    def connection(self) -> _AsyncGeneratorContextManager[CcxtProExchange | None, None]:
        return self.instance.exchange()