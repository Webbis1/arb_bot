import asyncio
import logging
import ccxt
import ccxt.pro as ccxtpro

from .ExFactory import ExFactory
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Port:
    @dataclass
    class Destination:
        ex: ccxtpro.Exchange 
        coin_name: str 
        chains: dict[str, str] # биржа отправления - сеть
            
        async def get_deposit_address(self, departure: str) -> str:
            network = self.chains.get(departure)
            if not network:
                error_msg = f"Сеть '{departure}' не поддерживается для {self.coin_name}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            try:
                params = {'network': network, 'chain': network}
                address_info = await self.ex.fetchDepositAddress(self.coin_name, params)
                
                address = None
                if isinstance(address_info, dict):
                    address = address_info.get('address')
                    if not address and 'addresses' in address_info:
                        address = address_info['addresses'][0].get('address') if address_info['addresses'] else None
                else:
                    address = str(address_info)
                    
                if not address:
                    raise ValueError(f"Адрес не найден в ответе от биржи для {self.coin_name}")
                    
                return address
                
            except ccxt.BadRequest as e:
                error_msg = f"Сеть {network} не поддерживается для {self.coin_name}"
                logger.error(f"{error_msg}: {e}")
                raise ValueError(error_msg) from e
            except ccxt.BaseError as e:
                logger.error(f"Ошибка биржи при получении адреса {self.coin_name}: {e}")
                raise ConnectionError(f"Ошибка подключения к бирже: {e}") from e
            except Exception as e:
                logger.error(f"Неожиданная ошибка при получении адреса {self.coin_name}: {e}")
                raise RuntimeError(f"Ошибка получения адреса: {e}") from e

    def __init__(self, ex_factory: ExFactory, routes: dict[str, dict[int, dict[str, str]]]):
        self.ex_factory = ex_factory
        self.routes = routes
    
    async def preparation(self, destination_name: str, coin: tuple[int, str]) -> Destination | None:
        """
        Подготавливает данные для отправки монеты на указанную биржу.

        :param destination_name: Название биржи прибытия (например, 'kucoin', 'binance')
        :param coin: Кортеж из id и названия монеты, например (1, 'BTC')
        :return: Объект Destination или None, если подготовка не удалась
        """
        if destination_name not in self.routes:
            logger.warning(f'Route for {destination_name} not defined')
            return None
        
        destination_route_matrix = self.routes[destination_name]
        coin_id, coin_name = coin
        
        if coin_id not in destination_route_matrix:
            logger.warning(f'Value for coin {coin_name} (ID: {coin_id}) in route {destination_name} not defined')
            return None
        
        destination_route_for_coin = destination_route_matrix[coin_id]
        ex = self.ex_factory[destination_name]
        
        if not ex:
            logger.warning(f'{destination_name} is an unknown destination')
            return None

        return self.Destination(ex, coin_name, destination_route_for_coin)