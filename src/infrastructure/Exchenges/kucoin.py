import asyncio
from typing import Any
from core.interfaces.Dto import Coins
from core.models import Coin
from core.models.types import COIN_NAME, COIN_ID
from infrastructure.CcxtExchange import CcxtExchange
import ccxt.pro  as ccxtpro

class KucoinExchange(CcxtExchange):
    def __init__(self, name: str, instance: ccxtpro.Exchange):
        super().__init__(name, instance)
        self.prices_wallet: dict[COIN_ID, float] = dict()
    
    async def get_current_coins(self) -> list[Coin]:
        markets = await self.instance.fetch_markets()
        currencies: dict | None= await self.instance.fetch_currencies()
        if not currencies:
            self.logger.warning(f"No currencies fetched from {self.name}.")
            return []
        
        coins: list[Coin] = []
        
        for coin_name, item in currencies.items():
            if coin_name != "USDT":
                trades_with_usdt = await self._is_trading_with_usdt(markets, coin_name)
                if not trades_with_usdt: continue
                
            networkList = item['info']['chains']
            for net in networkList:
                chain = net['chainId']
                if chain == "ERC20":
                    continue     
                if 'contractAddress' not in net or not net['contractAddress']: address = f'{coin_name}_{chain}'
                else: address = net['contractAddress']
            
                fee = float(net['withdrawalMinFee']) if net['withdrawalMinFee'] is not None else -1
                coin: Coin = Coin(_address = address, name=coin_name, chain=chain, fee=fee)
                coins.append(coin)
                    
        return coins

    async def watch_tickers(self, coin_names: list[COIN_NAME]) -> None:
        coin_names = coin_names[:390]
        # self.logger.warning("start kucoin")
        chunk_size: int = 10
        symbol_chunks: list[list[str]] = [coin_names[i:i + chunk_size] for i in range(0, len(coin_names), chunk_size)]
        
        coroutines = []
        for chunk in symbol_chunks:
            if chunk:
                coroutines.append(super(KucoinExchange, self).watch_tickers(chunk)) #type: ignore
        
        # Ждем выполнения всех корутин
        await asyncio.gather(*coroutines, return_exceptions=True)
        
    async def _price_notify(self, coin_id: int, value: float):
        for sub in self.price_subscribers:
            try:
                self.prices_wallet[coin_id] = value
                asyncio.create_task(sub.on_price_update(coin_id, value))
            except Exception as e:
                self.logger.exception(f"Error notifying price subscriber: {e}")


    async def sell(self, coin_id: int, quantity: float, usdt_name: str = 'USDT'):
        coin_name = self.coins.inverse.get(coin_id)
        
        coin_price = self.ex.prices_wallet[coin_id]
            
        quantity = quantity / coin_price
        
        self.logger.info(f'Exchange = {self.name}, createMarkerOrder = {self.__ex.has['createMarketOrder']}, createMarketBuyOrderRequiresPrice = {self.__ex.options.get('createMarketBuyOrderRequiresPrice')}')
        
        # Можно ли торговать по рыночной цене
        if (self.__ex.has['createMarketOrder']):                                 
            symbol = f"{coin_name}/{usdt_name}"
            try:
                order = await self.__ex.create_order(symbol, 'market', 'sell', quantity)
                filled_amount = order.get('filled', 0)
                cost = order.get('cost', 0)
                self.logger.info(f"Sell order filled: {filled_amount} {coin_name} for {cost} {usdt_name}")
                return order
            except Exception as e:
                self.logger.error(f"Sell order failed for {symbol}: {e}")
                return None
        else:
            self.logger.warning(f"Market sell is not supported on exchange {self.__ex.id}")