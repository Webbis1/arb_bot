import asyncio
import functools

import aiohttp
import ccxt
from core.models import Exchange
from ccxt.pro import Exchange as CcxtProExchange

from infrastructure.ErrorHandlerServices.ConnectionErrorHandler import ConnectionErrorHandler


class CcxtExchangModel(Exchange):
    def __init__(self, name: str, instance: ConnectionErrorHandler):
        Exchange.__init__(self, name)
        self.__ex: ConnectionErrorHandler = instance
        
    @property
    def instance(self) -> CcxtProExchange:
        return self.__ex