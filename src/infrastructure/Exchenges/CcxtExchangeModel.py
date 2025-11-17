from core.models import Exchange
from ccxt.pro import Exchange as CcxtProExchange


class CcxtExchangModel(Exchange):
    def __init__(self, name: str, instance: CcxtProExchange):
        Exchange.__init__(self, name)
        self.__ex: CcxtProExchange = instance
        
    @property
    def instance(self) -> CcxtProExchange:
        return self.__ex