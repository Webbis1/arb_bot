import asyncio
from typing import Any, Literal
import ccxt
from ccxt.pro import Exchange as CcxtProExchange

from core.interfaces.Exceptions.TransactionFailed import TransactionFailed
from core.models.types import COIN_NAME, RESUME_TIME
from infrastructure.CcxtExchangeModel import CcxtExchangModel

from asyncio import Queue


class TradingExchange(CcxtExchangModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paused_coins: dict[COIN_NAME, RESUME_TIME] = {}
        self._paused_coins_lock = asyncio.Lock()
    

    async def buy(self, coin_name: str, usdt_quantity: float | None = None):
        return await self.__transaction("buy", coin_name, usdt_quantity)

    async def sell(self, coin_name: str, usdt_quantity: float | None = None):
        return await self.__transaction("sell", coin_name, usdt_quantity)
    

    
    async def __transaction(self, side: Literal['buy', 'sell'], coin_name: str, quantity: float | None):
        if await self.__is_coin_paused(coin_name):
            self.logger.debug(f"Coin {coin_name} is paused, skipping transaction")
            return None
        
        if self.working:
            if coin_name.upper() == self.usdt:
                return TransactionFailed("Buy usdt/usdt")
            
            if not (quantity := quantity or self.wallet.get(coin_name)):
                return TransactionFailed("quantity is not installed")
            
            if not (side == "buy" or side == "sell"):
                return TransactionFailed("unknown side - {side}")
            
            symbol = self.symbol(coin_name)
            
            async with self.connection as exchange:
                if exchange is not None:
                    if not await self.__validate_order_params(exchange, symbol, quantity):
                        return TransactionFailed(self.name, f"Validate error for {symbol} and {quantity}")
                    try:
                        order = await exchange.create_order(symbol, 'market', side, quantity)
                        self.logger.info(f"{side} order: {symbol}")
                        return order
                    
                    except ccxt.InsufficientFunds as e:
                        return TransactionFailed(self.name, f"Insufficient funds: {type(e).__name__}: {str(e)}")
                    
                    except ccxt.AddressPending:
                        await self.__pause_coin(coin_name, 60)
                        return TransactionFailed(self.name, f"Address pending for {symbol}, pausing for 60s")
                    
                    except ccxt.InvalidAddress:
                        await self.__pause_coin(coin_name, 3600)  # 1 час
                        self.logger.critical(self.name, f"InvalidAddress for {symbol}, pausing for 1 hour")
                        #TODO: здесь еще нужно разобраться
                        return None
                    
                    except ccxt.InvalidOrder as e:
                        return TransactionFailed(self.name, f"InvalidOrder for {symbol}, quantity - {quantity}, ")

                    except (TypeError, ValueError, AttributeError, KeyError) as e:
                        return TransactionFailed(self.name, f"Argument error: {e}")
                        
                    except asyncio.CancelledError:
                        self.logger.warning("Operation cancelled")
                        raise
                    
                    except Exception as e:
                        return TransactionFailed(self.name, "Непредвиденная ошибка")
                    
    async def __validate_order_params(self, exchange, symbol: str, quantity: float) -> bool:
        """Проверяет параметры ордера перед отправкой"""
        try:
            market = exchange.markets[symbol]
            
            # Проверка минимального количества
            min_amount = market['limits']['amount']['min']
            if quantity < min_amount:
                self.logger.error(f"Quantity {quantity} < min {min_amount}")
                return False
            
            # Проверка шага количества
            if 'amount' in market['precision']:
                # Приводим к правильному шагу
                quantity = exchange.amount_to_precision(symbol, quantity)
            
            # Проверка минимальной стоимости (notional)
            if 'cost' in market['limits']:
                min_cost = market['limits']['cost']['min']
                ticker = await exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                order_value = quantity * current_price
                
                if order_value < min_cost:
                    self.logger.error(f"Order value {order_value} < min {min_cost}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Validation error: {e}")
            return False             
    
    async def __is_coin_paused(self, coin_name: str) -> bool:
        """Проверяет, находится ли монета в паузе"""
        async with self._paused_coins_lock:
            resume_time = self._paused_coins.get(coin_name.upper())
            if resume_time and resume_time > asyncio.get_event_loop().time():
                return True
            elif resume_time:
                del self._paused_coins[coin_name.upper()]
            return False

    async def __pause_coin(self, coin_name: str, pause_seconds: float = 60):
        """Ставит монету на паузу"""
        async with self._paused_coins_lock:
            resume_time = asyncio.get_event_loop().time() + pause_seconds
            self._paused_coins[coin_name.upper()] = resume_time
            self.logger.info(f"Paused {coin_name} for {pause_seconds} seconds")

    async def __resume_coin(self, coin_name: str):
        """Снимает паузу с монеты"""
        async with self._paused_coins_lock:
            if coin_name.upper() in self._paused_coins:
                del self._paused_coins[coin_name.upper()]
                self.logger.info(f"Resumed {coin_name}") 
        
    