import logging
from core.models.dto import CoinDict, Coins, Recommendation, Trade, Transfer, Wait
from dataclasses import dataclass, field
from core.interfaces import Exchange
from core.interfaces.Dto.Asset import Asset
from core.models import Coin, CoinPair, Deal, Commission
from core.models.types import FEE
from core.services.Analytics.Analyst import Analyst
from core.services.Mapper import Mapper


@dataclass
class Brain:
    analyst: 'Analyst'
    # _commission: Commission
    # _coin_list: CoinPair
    mapper: Mapper
    _additive: float = 2.0
    _logger: logging.Logger = field(default_factory=lambda: logging.getLogger('Brain'))
    
    
    async def analyse(self, exchange: Exchange, asset: Asset) -> Recommendation:
        if asset.coin_id == self.mapper.usdt:
            return await self.__usdt_analyse(exchange, asset)
        elif asset.coin_id in self.mapper.analyzed_coins:
            return await self.__other_analyse(exchange, asset)
        else:
            self._logger.warning(f"Coin ID = {asset.coin_id} not found in coin list")
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
        
        deal_fee: FEE | None = self.mapper.get_fee(deal)
        
        if deal_fee is None: 
            self._logger.info(f"Coin with id {deal.coin_id} not found in commission list deal")
            return Wait(seconds=10)
        
        if exchange is deal.departure:
            usdt_fee: FEE | None = None
            if coin := self.mapper.get_best_coin_transfer(exchange.name, deal.departure.name, coin_id): usdt_fee = coin.fee
        
            if usdt_fee is None: 
                self._logger.info(f"Coin with id {str(coin_id)} not found in commission list usdt")
                return Wait(seconds=10)
            
            profit: float = (asset.amount - usdt_fee) * (1 + deal.benefit) - self._additive
        
            if(profit >= deal_fee):
                transfer = Transfer(
                    coin=coin_id,
                    departure=exchange,
                    destination=deal.destination,
                )
                return transfer
        else:
            profit: float = (asset.amount) * (1 + deal.benefit) - self._additive
        
            if(profit >= deal_fee):
                trade = Trade(
                    buy_coin= deal.coin_id,
                    sell_coin=coin_id,
                )
                return trade
            
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
        
        deal_fee: FEE | None = self.mapper.get_fee(deal)
        
        if deal_fee is None: 
            self._logger.info(f"Coin with id {coin_id} not found in commission list")
            return sell
        
        profit: float = asset.amount * (1 + deal.benefit) - self._additive
        
        if(profit >= deal_fee):   
            transfer = Transfer(
                coin=coin_id,
                departure=current_exchange,
                destination=deal.destination,
            )
            return transfer
        
        return sell