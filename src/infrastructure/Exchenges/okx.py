from core.interfaces.Dto import Coins
from core.models import Coin
from infrastructure.CcxtExchange import CcxtExchange


class OkxExchange(CcxtExchange):
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
                
            networkList = item['info']
            for net in networkList:
                chain = net['chain']
                if chain == "ETH":
                    continue     
                if 'ctAddr' not in net or not net['ctAddr']: address = f'{coin_name}_{chain}'
                else: address = net['ctAddr']
            
                fee = float(net['fee']) if net['fee'] is not None else -1
                coin: Coin = Coin(_address = address, name=coin_name, chain=chain, fee=fee)
                coins.append(coin)
                    
        return coins