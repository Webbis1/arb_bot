import asyncio
from typing import Any, Literal
import ccxt
from ccxt.pro import Exchange as CcxtProExchange

from core.interfaces.Exceptions.TransactionFailed import TransactionFailed
from infrastructure.CcxtExchangeModel import CcxtExchangModel


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
            
            async with 
                try:
                    order = await exchange.create_order(symbol, 'market', side, quantity)
                    self.logger.info(f"{side} order: {symbol}")
                    return order
                except (
                    ccxt.InvalidOrder,
                    ccxt.OrderNotFound,
                    ccxt.InvalidAddress,
                    ccxt.AddressPending,
                ) as e:
                    self.logger.error(
                        "[%s] Order validation error: %s", self.name, e
                    )
                    return None

                except (TypeError, ValueError, AttributeError, KeyError) as e:
                    self.logger.error(
                        "[%s] Argument error: %s", self.name, e
                    )
                    return None 
                except ccxt.InsufficientFunds as e:
                    self.logger.error(f"Insufficient funds: {type(e).__name__}: {str(e)}")
                    # Требует пополнения баланса
                    return None
                except asyncio.CancelledError:
                    self.logger.warning("Operation cancelled")
                    raise  # Пробрасываем дальше, т.к. это нормальное завершение
                
            return await transaction(self.instance, symbol, quantity, side)
