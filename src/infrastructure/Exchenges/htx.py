import asyncio
from core.models.dto import Coins
from core.models import Coin
from core.models.types import COIN_NAME
from infrastructure.CcxtExchange import CcxtExchange
from typing import Set, Dict, Optional
import ccxt.pro as ccxtpro
from collections import defaultdict


class HtxExchange(CcxtExchange):    
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
                deposit_addresses.add(net_data['info']['chain'])
                
            networkList = item['info']['chains']
            for net in networkList:
                chain = net['chain']
                if chain == "ERC20":
                    continue     
                if 'contractAddress' not in net or not net['contractAddress']: address = f'{coin_name}_{chain}'
                else: address = net['contractAddress']
            
                if (chain in deposit_addresses):
                    fee = -1 
                    if 'transactFeeWithdraw' in net and net['transactFeeWithdraw'] is not None:
                        try:
                            fee = float(net['transactFeeWithdraw'])
                        except (ValueError, TypeError):
                            fee = -1
                    # Альтернативные поля для комиссии, если основное отсутствует
                    elif 'withdrawFee' in net and net['withdrawFee'] is not None:
                        try:
                            fee = float(net['withdrawFee'])
                        except (ValueError, TypeError):
                            fee = -1
                    coin: Coin = Coin(_address = address, name=coin_name, chain=chain, fee=fee)
                    coins[coin_name].add(coin)
                
                else:
                    continue
                    
        return coins
 
    async def watch_tickers(self, coin_names: list[COIN_NAME]) -> None:
        self._is_running = True
        try:
            # self.logger.info(f"Starting Price monitoring for {self.name}...")
            
            symbols = self._get_symbols(coin_names)
            # if "FIO/USDT" in symbols:
            #     symbols.remove("FIO/USDT")
                
            async def watch_ticker(symbol: str):
                while self._is_running:
                    try:
                        ticker_data = await self.instance.watch_ticker(symbol)
                        
                        coin_name = symbol.split('/')[0]
                        
                        price = 0 #ticker['last']
                        
                        if 'ask' in ticker_data and ticker_data['ask'] is not None:
                            price = float(ticker_data['ask'])
                        elif 'last' in ticker_data and ticker_data['last'] is not None:
                            price = float(ticker_data['last'])
                        elif 'info' in ticker_data and 'lastPrice' in ticker_data['info'] and ticker_data['info']['lastPrice'] is not None:
                            price = float(ticker_data['info']['lastPrice'])
                            
                        if (price == 0):
                            self.logger.warning(f"There is not fee data for Coin {coin_name} in exchange {self.name}")
                        
                        await self._price_notify(self.coins[coin_name], price)
                        
                    except asyncio.CancelledError:
                        self.logger.debug(f"Observation cancelled for {self.name}")
                        break
                    except Exception as e:
                        self.logger.error(f"[{self.name}] Error: {e}")
                        await asyncio.sleep(1)
                        
            tasks = [watch_ticker(symbol) for symbol in symbols[:45]]
            await asyncio.gather(*tasks)
                        
        except Exception as e:
            self.logger.exception(f"Fatal error: {e}")
        # finally:
        #     self._is_running = False
    
    