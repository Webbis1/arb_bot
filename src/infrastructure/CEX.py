from zope.interface import implementer
from functools import partial



from core.interfaces import IBalanceObserver, ICourier, IExchange, IPriceObserver, ITrader
from core.models.types import DESTINATION
from infrastructure.CcxtExchangeModel import CcxtExchangModel
from infrastructure.Connection import Connection
from infrastructure.services import BalanceObserver, PriceObserver, Trader
from infrastructure.services.Courier import Courier



@implementer(IExchange)
class CEX(CcxtExchangModel):
    def __init__(self, name: str, conn: Connection, trader: ITrader, courier: ICourier, price_observer: IPriceObserver, balance_observer: IBalanceObserver):
        super().__init__(name, conn)
        self.__trader = trader
        self.__courier  = courier
        self.__price_observer = price_observer
        self.__balance_observer = balance_observer
        
        # Courier
        self.withdraw = partial(self.__courier.withdraw)
        self.get_deposit_address = partial(self.__courier._get_deposit_address)
        
        #Trader
        self.sell = partial(self.__trader.sell)
        self.buy = partial(self.__trader.buy)
        
        # Balance observer
        self.subscribe_balance = partial(self.__balance_observer.subscribe_balance)
        self.unsubscribe_balance = partial(self.__balance_observer.unsubscribe_balance)
        self.get_balance = partial(self.__balance_observer.get_balance)
        
        # Price observer
        self.subscribe_price = partial(self.__price_observer.subscribe_price)
        self.unsubscribe_price = partial(self.__price_observer.unsubscribe_price)
                
        
    
