from core.interfaces.Dto import Coins
from core.models import Coin
from infrastructure.CcxtExchange import CcxtExchange


class BitgetExchange(CcxtExchange):
    async def get_current_coins(self) -> Coins:
        markets = await self.__ex.fetch_markets()
        currencies: dict | None= await self.__ex.fetch_currencies()
        if not currencies:
            self.logger.warning(f"No currencies fetched from {self.name}.")
            return set()
        
        coins: set[Coin] = set()
        
        for coin_name, item in currencies.items():
            if coin_name != "USDT":
                trades_with_usdt, _ = await self._is_trading_with_usdt(markets, coin_name)
                if not trades_with_usdt: continue
                
            networkList = item['info']['networkList']
            for net in networkList:
                chain = net['network']
                if chain == "ETH":
                    continue     
                if 'contractAddress' not in net or not net['contractAddress']: address = f'{coin_name}_{chain}'
                else: address = net['contractAddress']
            
                fee = float(net['withdrawFee'])
                coin: Coin = Coin(_address = address, name=coin_name, chain=chain, fee=fee)
                coins.add(coin)
                    
        return coins