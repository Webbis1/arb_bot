from zope.interface import Interface

from core.protocols.PriceSubscriber import PriceSubscriber


class IPriceObserver(Interface):
    async def subscribe_price(self, sub: PriceSubscriber): ...
    async def unsubscribe_price(self, sub: PriceSubscriber): ...