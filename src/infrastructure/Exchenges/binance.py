from core.models.dto import Coins
# from core.models import Coin
from core.models.Coins import Coin, CoinCreateError
from core.models.types import COIN_NAME
from infrastructure.CcxtExchange import CcxtExchange
from collections import defaultdict

class BinanceExchange(CcxtExchange):
    
    def convert_currency(self, currency: dict[str, dict]) -> list[Coin]:
        coin_list: list[Coin] = []
        for data in currency.values():
            if coin_name := data.get('code'):
                for network in data.get('networks', {}).values():
                    if network.get('active') and network.get('deposit') and network.get('withdraw'):
                        chain = network.get('id')
                        fee = network.get('fee')
                        min_amount = network.get('limits', {}).get('withdraw', {}).get('min')
                        address = network.get('info', {}).get('contractAddress')
                        try:
                            coin: Coin = Coin(address, coin_name, chain, fee, min_amount)
                            coin_list.append(coin)
                        except CoinCreateError:
                            continue
        return coin_list
                
    
    async def get_current_coins(self):
        coin_list: list[Coin] = []
        
        if currencies := self.instance.currencies:
            coin_list = self.convert_currency(currencies)
    
                    
        return coin_list
    
    