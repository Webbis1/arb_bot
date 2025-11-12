from core.interfaces.Dto import Coins
from core.models import Coin
from infrastructure.CcxtExchange import CcxtExchange
from core.models.types import COIN_NAME
from collections import defaultdict

class BitgetExchange(CcxtExchange):
    async def get_current_coins(self) -> dict[COIN_NAME, set[Coin]]:
        markets = await self.instance.fetch_markets()
        currencies: dict | None= await self.instance.fetch_currencies()
        if not currencies:
            self.logger.warning(f"No currencies fetched from {self.name}.")
            return []
        
        coins: defaultdict[COIN_NAME, set[Coin]] = defaultdict(lambda: set())
        
        for coin_name, item in currencies.items():
            if coin_name != "USDT":
                trades_with_usdt = await self._is_trading_with_usdt(markets, coin_name)
                if not trades_with_usdt: continue
                
            networkList = item['info']['chains']
            for net in networkList:
                chain = net['chain']
                if chain == "ETH":
                    continue     
                if 'contractAddress' not in net or not net['contractAddress']: address = f'{coin_name}_{chain}'
                else: address = net['contractAddress']
            
                fee = float(net['withdrawFee'])
                coin: Coin = Coin(_address = address, name=coin_name, chain=chain, fee=fee)
                coins[coin_name].add(coin)
                    
        return coins
    
    