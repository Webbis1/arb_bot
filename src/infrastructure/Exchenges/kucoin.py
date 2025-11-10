import asyncio
from typing import Any
from core.interfaces.Dto import Coins
from core.models import Coin
from core.models.types import COIN_NAME
from infrastructure.CcxtExchange import CcxtExchange


class KucoinExchange(CcxtExchange):
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
        self.logger.warning("start kucoin")
        chunk_size: int = 10
        symbol_chunks: list[list[str]] = [coin_names[i:i + chunk_size] for i in range(0, len(coin_names), chunk_size)]
        
        coroutines = []
        for chunk in symbol_chunks:
            if chunk:
                coroutines.append(super(KucoinExchange, self).watch_tickers(chunk)) #type: ignore
        
        # Ждем выполнения всех корутин
        await asyncio.gather(*coroutines, return_exceptions=True)