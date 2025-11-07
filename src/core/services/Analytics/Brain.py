import logging
from core.interfaces.Dto import CoinDict, Coins, Recommendation, Trade, Transfer, Wait
from dataclasses import dataclass, field
from core.interfaces import Exchange
from core.interfaces.Dto.Asset import Asset
from core.models import Coin, CoinPair, Deal, Commission
from core.services.Analytics.Analyst import Analyst


@dataclass
class Brain:
    analyst: 'Analyst'
    _commission: Commission
    _coin_list: CoinPair
    _additive: float = 2.0
    _logger: logging.Logger = field(default_factory=lambda: logging.getLogger('Brain'))
    
    def __post_init__(self):
        for _, coin in self._coin_list.items():
            if coin.name == "USDT":
                self.USDT = coin
                break
        if not hasattr(self, 'USDT'): raise ValueError("USDT coin not found in coin list")
    
    async def analyse(self, exchange: Exchange, asset: Asset) -> Recommendation:
        if asset.coin == self.USDT:
            return await self.__usdt_analyse(exchange, asset)
        elif asset.coin in self._coin_list.inverse:
            return await self.__other_analyse(exchange, asset)
        else:
            self._logger.info(f"Coin {asset.coin.name} not found in coin list")
            sell: Trade = Trade(
                buy_coin=self.USDT,
                sell_coin=asset.coin,
            )
            return sell
        
    async def __usdt_analyse(self, exchange: Exchange, asset: Asset) -> Recommendation:
        deal: Deal | None = await self.analyst.get_best_deal();
        
        if deal is None: 
            self._logger.info("No deals available")
            return Wait(seconds=10)
        
        coin_id: int | None = self._coin_list.inverse.get(asset.coin)
        
        if coin_id is None: 
            self._logger.info(f"Coin {asset.coin.name} not found in coin list")
            return Wait(seconds=10)
        
        coin: Coin | None = self._commission[deal.departure][deal.destination].get(coin_id)
        
        if coin is None: 
            self._logger.info(f"Coin with id {coin_id} not found in commission list")
            return Wait(seconds=10)
        
        profit: float = asset.amount * (1 + deal.benefit) - self._additive
        
        if(profit >= coin.fee):
            if exchange == deal.departure:
                trade = Trade(
                    buy_coin= deal.coin,
                    sell_coin=coin,
                )
                return trade
            else:
                transfer = Transfer(
                    coin=coin,
                    departure=exchange,
                    destination=deal.destination,
                )
                return transfer
            
        return Wait(seconds=10)
    
    async def __other_analyse(self, current_exchange: Exchange, asset: Asset) -> Recommendation:
        deal: Deal | None = await self.analyst.get_all_benefits(current_exchange, asset.coin);
        
        sell: Trade = Trade(
                buy_coin=self.USDT,
                sell_coin=asset.coin,
            )
        
        if deal is None: 
            self._logger.info("No deals available")
            return sell
        
        
        coin_id: int | None = self._coin_list.inverse.get(asset.coin)
        
        if coin_id is None: 
            self._logger.info(f"Coin {asset.coin.name} not found in coin list")
            return sell
        
        coin: Coin | None = self._commission[deal.departure][deal.destination].get(coin_id)
        
        if coin is None: 
            self._logger.info(f"Coin with id {coin_id} not found in commission list")
            return sell
        
        profit: float = asset.amount * (1 + deal.benefit) - self._additive
        
        if(profit >= coin.fee):   
            transfer = Transfer(
                coin=coin,
                departure=current_exchange,
                destination=deal.destination,
            )
            return transfer
        
        return sell