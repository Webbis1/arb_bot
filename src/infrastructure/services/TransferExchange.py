import ccxt
from core.models.Coins import Coin
from core.models.types import COIN_NAME
from infrastructure.CcxtExchangeModel import CcxtExchangModel
from ccxt.pro import Exchange as CcxtProExchange
import ccxt.pro as ccxtpro

class TransferExchange(CcxtExchangModel):
    async def withdraw(self, coin_address: str, amount: float, ex_destination: 'TransferExchange' , tag: str = '') -> bool:    
        if coin := self.get_coin(coin_address):
            if address := await ex_destination._get_deposit_address(coin_address):        
                self.logger.info(f'Withdraw deposit address: {address}')
                    
                params = {
                    'network': coin.network,
                    'chain': coin.network
                }
                
                self.logger.info(f'Withdraw params: {params}')
                
                try:
                    withdraw_result = await self.instance.withdraw(coin.name, amount, address, tag=tag, params=params)
                    self.logger.info(f'Withdraw Result: {withdraw_result}')
                    return True
                except ccxt.InsufficientFunds as e:
                    self.logger.error(f'Недостаточно средств для вывода: {e}')
                    return False
                except ccxt.InvalidAddress as e:
                    self.logger.error(f'Неверный адрес вывода: {e}')
                    return False
                except ccxt.PermissionDenied as e:
                    self.logger.error(f'Нет прав на вывод средств: {e}')
                    return False
                except ccxt.NetworkError as e:
                    self.logger.error(f'Сетевая ошибка: {e}')
                    return False
                except ccxt.ExchangeError as e:
                    self.logger.error(f'Ошибка биржи: {e}')
                    return False
                except Exception as e:
                    self.logger.error(f'Неизвестная ошибка при выводе: {e}')
                    return False
            
            else: self.logger.error(f'Cannot fetch deposit address on Exchange = {self.name}, Coin = {coin.name}, Chain = {coin.network}')
        else: self.logger.warning(f"Coin_address - {coin_address} is not supporting")
            
        return False
    
    
    async def _get_deposit_address(self, coin_address: str) -> str | None:
        if coin := self.get_coin(coin_address):
            try:       
                address_info = await self.instance.fetch_deposit_address(*self._get_deposit_address_params(coin))
                
                address = None       
                
                if isinstance(address_info, dict):
                    self.logger.info(f'TAGS: {address_info}')
                    address = address_info.get('address')
                    if not address and 'addresses' in address_info:
                        address = address_info['addresses'][0].get('address') if address_info['addresses'] else None
                else:
                    address = str(address_info)
                    
                if not address:
                    raise ValueError(f"Адрес не найден в ответе от биржи для {coin.name}")
                    
                return address
            
            except ccxtpro.BadRequest as e:
                error_msg = f"Сеть {coin.network} не поддерживается для {coin.name}"
                self.logger.error(f"{error_msg}: {e}")
                
            except ccxtpro.BaseError as e:
                self.logger.error(f"Ошибка биржи при получении адреса {coin.name}: {e}")
                
            except Exception as e:
                self.logger.error(f"Неожиданная ошибка при получении адреса {coin.name}: {e}")
    
    def _get_deposit_address_params(self, coin: Coin) -> tuple[COIN_NAME, dict]:
        params = {
            "network": coin.network
        }
        return coin.name, params
