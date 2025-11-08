import logging
from core.interfaces.Dto import CoinDict, Coins, Recommendation, Trade, Transfer, Wait
from dataclasses import dataclass, field
from core.interfaces import Exchange
from core.interfaces.Dto.Asset import Asset
from core.models import Coin, CoinPair, Deal, Commission
from core.services.Analytics.Analyst import Analyst
from core.services.Mapper import Mapper


@dataclass
class Brain:
    analyst: 'Analyst'
    _commission: Commission
    _coin_list: CoinPair
    mapper: Mapper
    _additive: float = 2.0
    _logger: logging.Logger = field(default_factory=lambda: logging.getLogger('Brain'))
    
    
    async def analyse(self, exchange: Exchange, asset: Asset) -> Recommendation:
        if asset.coin_id == self.mapper.usdt:
            return await self.__usdt_analyse(exchange, asset)
        elif asset.coin_id in self._coin_list.inverse:
            return await self.__other_analyse(exchange, asset)
        else:
            self._logger.info(f"Coin ID = {asset.coin_id} not found in coin list")
            sell: Trade = Trade(
                buy_coin=self.mapper.usdt,
                sell_coin=asset.coin_id,
            )
            return sell
        
    async def __usdt_analyse(self, exchange: Exchange, asset: Asset) -> Recommendation:
        deal: Deal | None = await self.analyst.get_best_deal();
        
        if deal is None: 
            self._logger.info("No deals available")
            return Wait(seconds=10)
        
        coin_id: int | None = asset.coin_id #self._coin_list.inverse.get(asset.coin)
        
        if coin_id is None: 
            self._logger.info(f"Coin ID = {asset.coin_id} not found in coin list")
            return Wait(seconds=10)
        
        coin: Coin | None = self._commission[deal.departure][deal.destination].get(coin_id)
        
        if coin is None: 
            self._logger.info(f"Coin with id {coin_id} not found in commission list")
            return Wait(seconds=10)
        
        profit: float = asset.amount * (1 + deal.benefit) - self._additive
        
        if(profit >= coin.fee):
            if exchange == deal.departure:
                trade = Trade(
                    buy_coin= deal.coin_id,
                    sell_coin=coin_id,
                )
                return trade
            else:
                transfer = Transfer(
                    coin=coin_id,
                    departure=exchange,
                    destination=deal.destination,
                )
                return transfer
            
        return Wait(seconds=10)
    
    async def __other_analyse(self, current_exchange: Exchange, asset: Asset) -> Recommendation:
        deal: Deal | None = await self.analyst.get_all_benefits(current_exchange, asset.coin_id);
        
        sell: Trade = Trade(
                buy_coin=self.mapper.usdt,
                sell_coin=asset.coin_id,
            )
        
        if deal is None: 
            self._logger.info("No deals available")
            return sell
        
        
        coin_id: int | None = asset.coin_id #self._coin_list.inverse.get(asset.coin_id)
        
        if coin_id is None: 
            self._logger.info(f"Coin ID = {coin_id} not found in coin list")
            return sell
        
        coin: Coin | None = self._commission[deal.departure][deal.destination].get(coin_id)
        
        if coin is None: 
            self._logger.info(f"Coin with id {coin_id} not found in commission list")
            return sell
        
        profit: float = asset.amount * (1 + deal.benefit) - self._additive
        
        if(profit >= coin.fee):   
            transfer = Transfer(
                coin=coin_id,
                departure=current_exchange,
                destination=deal.destination,
            )
            return transfer
        
        return sell