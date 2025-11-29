from collections import defaultdict
from core.models.dto import Coins
from core.models import Coin
from infrastructure.CcxtExchange import CcxtExchange
from core.models.types import COIN_NAME

class OkxExchange(CcxtExchange):
    async def get_current_coins(self) -> dict[COIN_NAME, set[Coin]]:
        markets = await self.instance.fetch_markets()
        currencies: dict | None= await self.instance.fetch_currencies()
        if not currencies:
            self.logger.warning(f"No currencies fetched from {self.name}.")
            return {}
        
        coins: defaultdict[COIN_NAME, set[Coin]] = defaultdict(lambda: set())
        
        for coin_name, item in currencies.items():
            if coin_name != "USDT":
                trades_with_usdt = await self._is_trading_with_usdt(markets, coin_name)
                if not trades_with_usdt: continue
            
            self.logger.info(f"check {coin_name}")
               
            deposit_addresses_fetch_results = await self.instance.fetch_deposit_addresses_by_network(coin_name)
            deposit_addresses = set()
            
            for net, net_data in deposit_addresses_fetch_results.items():                
                deposit_addresses.add(net_data['info']['ctAddr'])
                
                
            networkList = item['info']
            
            for net in networkList:
                chain = net['chain']
                chain = chain[5:]
                
                # USDT-
                if chain == "ETH":
                    continue     
                if 'ctAddr' not in net or not net['ctAddr']: address = f'{coin_name}_{chain}'
                else: address = net['ctAddr']
                
                if (address in deposit_addresses):                
                    fee = float(net['fee']) if net['fee'] is not None else -1
                    coin: Coin = Coin(_address = address, name=coin_name, chain=chain, fee=fee)
                    coins[coin_name].add(coin)
                    
                else:
                    continue
                    
        return coins