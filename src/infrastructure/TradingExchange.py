from typing import Any, Literal
from ccxt.pro import Exchange as CcxtProExchange

from core.interfaces.Exceptions.TransactionFailed import TransactionFailed
from infrastructure.Exchenges.CcxtExchangeModel import CcxtExchangModel


class TradingExchange(CcxtExchangModel):
    async def buy(self, coin_name: str, usdt_quantity: float | None = None):
        return await self._transaction("buy", coin_name, usdt_quantity)

    async def sell(self, coin_name: str, usdt_quantity: float | None = None):
        return await self._transaction("sell", coin_name, usdt_quantity)
    
    def symbol(self, coin_name: str) -> str:
        return f"{coin_name.upper()}/{self.usdt}"
    
    async def _transaction(self, side: Literal['buy', 'sell'], coin_name: str, quantity: float | None):
        if self.working:
            if coin_name.upper() == self.usdt:
                return TransactionFailed("Buy usdt/usdt")
            
            if not (quantity := quantity or self.wallet.get(coin_name)):
                return TransactionFailed("quantity is not installed")
            
            if not (side == "buy" or side == "sell"):
                return TransactionFailed("unknown side - {side}")
            
            
            symbol = self.symbol(coin_name)
            
            @self.connected
            async def transaction(exchange: CcxtProExchange, symbol: str, quantity: float, side):
                order = await exchange.create_order(symbol, 'market', side, quantity)
                self.logger.info(f"Buy order: {symbol}")
                return order
            
            return await transaction(self.instance, symbol, quantity, side)