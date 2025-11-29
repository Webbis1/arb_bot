import asyncio
import logging
from typing import Literal
import ccxt
from zope.interface import implementer


from core.interfaces import ITrader
from core.models.types import COIN_NAME, RESUME_TIME
from infrastructure.CcxtExchangeModel import CcxtExchangModel


@implementer(ITrader)
class Trader():
    def __init__(self, ex: CcxtExchangModel):
        self.__ex = ex
        
        self._logger = logging.getLogger(f'Trader.{self.__ex.name}')
        self._paused_coins: dict[COIN_NAME, RESUME_TIME] = {}
        self._paused_coins_lock = asyncio.Lock()
    

    async def buy(self, coin_name: str, usdt_quantity: float | None = None):
        return await self.__transaction("buy", coin_name, usdt_quantity)

    async def sell(self, coin_name: str, amount: float | None = None):
        return await self.__transaction("sell", coin_name, amount)
    

    @property
    def _working(self):
        return self.__ex.working
    
    @property  
    def _symbol(self):
        return self.__ex.symbol
    
    @property
    def _usdt(self):
        return self.__ex.usdt
    
    @property
    def _wallet(self):
        return self.__ex.wallet
    
    @property
    def _connection(self):
        return self.__ex.connection
    
    
    async def __transaction(self, side: Literal['buy', 'sell'], coin_name: str, quantity: float | None):
        if await self.__is_coin_paused(coin_name):
            self._logger.debug(f"Coin {coin_name} is paused, skipping transaction")
            return None
        
        
        if self._working:
            if coin_name.upper() == self._usdt:
                self._logger.error("Cannot trade USDT/USDT pair")
                return None
            
            if not (quantity := quantity or self._wallet.get(coin_name)):
                self._logger.error("Quantity is not specified")
                return None
            
            if not (side == "buy" or side == "sell"):
                self._logger.error(f"Unknown side: {side}")
                return None
            
            symbol = self._symbol(coin_name)
            
            async with self._connection as exchange:
                if exchange is not None:
                    if not await self.__validate_order_params(exchange, symbol, quantity):
                        self._logger.error(f"Validation error for {symbol} and quantity {quantity}")
                        return None
                    try:
                        order = await exchange.create_order(symbol, 'market', side, quantity)
                        self._logger.info(f"Successful {side} order: {symbol}")
                        return order
                    
                    except ccxt.InsufficientFunds as e:
                        self._logger.error(f"Insufficient funds: {type(e).__name__}: {str(e)}")
                        return None
                    
                    except ccxt.AddressPending:
                        await self.__pause_coin(coin_name, 60)
                        self._logger.warning(f"Address pending for {symbol}, pausing for 60s")
                        return None
                    
                    except ccxt.InvalidAddress:
                        await self.__pause_coin(coin_name, 3600)  # 1 час
                        self._logger.critical(f"InvalidAddress for {symbol}, pausing for 1 hour")
                        #TODO: здесь еще нужно разобраться
                        return None
                    
                    except ccxt.InvalidOrder as e:
                        self._logger.error(f"InvalidOrder for {symbol}, quantity - {quantity}: {str(e)}")
                        return None

                    except (TypeError, ValueError, AttributeError, KeyError) as e:
                        self._logger.error(f"Argument error: {e}")
                        return None
                        
                    except asyncio.CancelledError:
                        self._logger.warning("Operation cancelled")
                        raise
                    
                    except Exception as e:
                        self._logger.error(f"Unexpected error: {e}")
                        return None
                    
    async def __validate_order_params(self, exchange, symbol: str, quantity: float) -> bool:
        """Проверяет параметры ордера перед отправкой"""
        try:
            market = exchange.markets[symbol]
            
            # Проверка минимального количества
            min_amount = market['limits']['amount']['min']
            if quantity < min_amount:
                self._logger.error(f"Quantity {quantity} < min {min_amount}")
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
                    self._logger.error(f"Order value {order_value} < min {min_cost}")
                    return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"Validation error: {e}")
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
            self._logger.info(f"Paused {coin_name} for {pause_seconds} seconds")

    async def __resume_coin(self, coin_name: str):
        """Снимает паузу с монеты"""
        async with self._paused_coins_lock:
            if coin_name.upper() in self._paused_coins:
                del self._paused_coins[coin_name.upper()]
                self._logger.info(f"Resumed {coin_name}") 