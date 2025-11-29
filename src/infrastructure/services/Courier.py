import logging
import ccxt

from zope.interface import implementer

from core.interfaces import ICourier
from core.models.Coins import Coin
from core.models.types import COIN_NAME
from infrastructure.CcxtExchangeModel import CcxtExchangModel


@implementer(ICourier)
class Courier():
    def __init__(self, ex: CcxtExchangModel):
        self.__ex = ex
        self._logger = logging.getLogger(f'Courier.{self.__ex.name}')
    
    @property
    def _connection(self):
        return self.__ex.connection
    
    @property
    def _working(self):
        return self.__ex.working
    
    @property
    def _get_coin(self):
        return self.__ex.get_coin
    
    async def withdraw(self, coin_address: str, amount: float, ex_destination: 'ICourier' , tag: str = '') -> bool:    
        if not self._working: 
            self._logger.warning(f"not working")
            return False
        
        if coin := self._get_coin(coin_address):
            async with self._connection as exchange:
                if exchange is None:
                    self._logger.warning("Connection access is missing")
                    return False
                
                if address := await ex_destination.get_deposit_address(coin_address):        
                    self._logger.info(f'Withdraw deposit address: {address}')
                    
                    params = {
                        'network': coin.network,
                        'chain': coin.network
                    }
                    
                    self._logger.info(f'Withdraw params: {params}')
                    
                    if exchange is None:
                        self._logger.warning("Connection access is missing")
                        return False
                    
                    try:
                        withdraw_result = await exchange.withdraw(coin.name, amount, address, tag=tag, params=params)
                        self._logger.info(f'Withdraw Result: {withdraw_result}')
                        return True
                        
                    except ccxt.InsufficientFunds as e:
                        self._logger.error(f'Недостаточно средств для вывода {coin.name}: {e}')
  
                    except ccxt.InvalidAddress as e:
                        self._logger.error(f'Неверный адрес вывода {coin.name}: {e}')

                    except ccxt.PermissionDenied as e:
                        error_msg = str(e).lower()
                        if 'withdraw' in error_msg or 'disabled' in error_msg:
                            self._logger.error(f'Вывод средств отключен для {coin.name}: {e}')
                        else:
                            self._logger.error(f'Нет прав на вывод средств {coin.name}: {e}')

                    except ccxt.NotSupported as e:
                        self._logger.error(f'Вывод не поддерживается для {coin.name}: {e}')

                    except ccxt.BadRequest as e:
                        error_msg = str(e).lower()
                        if 'network' in error_msg:
                            self._logger.error(f'Требуется указать сеть для вывода {coin.name}: {e}')
                        elif 'amount' in error_msg or 'minimum' in error_msg:
                            self._logger.error(f'Неверная сумма вывода {coin.name}: {e}')
                        else:
                            self._logger.error(f'Неверный запрос на вывод {coin.name}: {e}')

                    except ccxt.InvalidOrder as e:
                        self._logger.error(f'Неверные параметры вывода {coin.name}: {e}')

                    except ccxt.ExchangeError as e:
                        error_msg = str(e).lower()
                        if 'maintenance' in error_msg:
                            self._logger.error(f'Кошелек на техническом обслуживании для {coin.name}: {e}')
                        elif 'withdrawal' in error_msg and 'fee' in error_msg:
                            self._logger.error(f'Проблема с комиссией вывода {coin.name}: {e}')
                        elif 'limit' in error_msg or 'exceeded' in error_msg:
                            self._logger.error(f'Превышен лимит вывода {coin.name}: {e}')
                        else:
                            self._logger.error(f'Ошибка биржи при выводе {coin.name}: {e}')

                    except Exception as e:
                        self._logger.error(f'Неизвестная ошибка при выводе {coin.name}: {e}', exc_info=True)
                    
                    return False
            
                else: self._logger.error(f'Cannot fetch deposit address, Coin = {coin.name}, Chain = {coin.network}')
        else:
            self._logger.warning(f"coin_address - {coin_address} is missing on this exchange")
            
        return False
    
    
    async def get_deposit_address(self, coin_address: str) -> str | None:
        if not self._working: 
            self._logger.warning(f"not working")
            return None
        
        if coin := self._get_coin(coin_address):
            async with self._connection as exchange:
                if exchange is None:
                    self._logger.warning("Connection access is missing")
                    return None
                
                try:       
                    address_info = await exchange.fetch_deposit_address(*self._get_deposit_address_params(coin))

                    address = None

                    if isinstance(address_info, dict):
                        address = address_info.get('address')

                        if not address and 'addresses' in address_info and address_info['addresses']:
                            address = address_info['addresses'][0].get('address')

                        if address:
                            self._logger.debug(f"Получен адрес депозита для {coin.name}: {address}")
                        else:
                            self._logger.warning(f"Структура ответа для {coin.name}: {address_info}")
                    else:
                        address = str(address_info) if address_info else None
                        if address:
                            self._logger.debug(f"Получен адрес депозита для {coin.name}: {address}")

                    if not address:
                        self._logger.error(f"Адрес не найден в ответе биржи для {coin.name}. Ответ: {address_info}")
                        return None

                    return address
                
                except ccxt.NotSupported as e:
                    self._logger.warning(f"Получение адреса депозита не поддерживается для {coin.name}: {e}")
                except ccxt.ExchangeNotAvailable as e:
                    self._logger.warning(f"Биржа недоступна для получения адреса {coin.name}: {e}")
                except ccxt.AddressPending as e:
                    self._logger.info(f"Адрес депозита для {coin.name} в процессе генерации: {e}")
                except ccxt.InvalidAddress as e:
                    self._logger.error(f"Некорректный адрес депозита для {coin.name}: {e}")
                except ccxt.BadSymbol as e:
                    self._logger.error(f"Валюта {coin.name} не найдена на бирже: {e}")
                except ccxt.BadRequest as e:
                    error_msg = str(e).lower()
                    if "network" in error_msg:
                        self._logger.error(f"Требуется указать сеть для валюты {coin.name}: {e}")
                    else:
                        self._logger.error(f"Неверный запрос для получения адреса {coin.name}: {e}")
                except ccxt.PermissionDenied as e:
                    error_msg = str(e).lower()
                    if "deposit" in error_msg or "disabled" in error_msg:
                        self._logger.warning(f"Депозиты для {coin.name} временно отключены: {e}")
                    else:
                        self._logger.error(f"Доступ запрещен при получении адреса {coin.name}: {e}")
                except ccxt.ExchangeError as e:
                    error_msg = str(e).lower()
                    if "address" in error_msg and ("generate" in error_msg or "create" in error_msg):
                        self._logger.error(f"Ошибка генерации адреса депозита для {coin.name}: {e}")
                    elif "maintenance" in error_msg or "wallet" in error_msg:
                        self._logger.warning(f"Кошелек на техническом обслуживании для {coin.name}: {e}")
                    elif "not exist" in error_msg or "does not exist" in error_msg:
                        self._logger.warning(f"Адрес депозита для {coin.name} не существует: {e}")
                    elif "maximum" in error_msg and "address" in error_msg:
                        self._logger.error(f"Достигнут лимит адресов для {coin.name}: {e}")
                    else:
                        self._logger.error(f"Ошибка биржи при получении адреса {coin.name}: {e}")
                except Exception as e:
                    self._logger.error(f"Неожиданная ошибка при получении адреса депозита {coin.name}: {e}", exc_info=True)
        else:
            self._logger.warning(f"coin_address - {coin_address} is missing on this exchange")
            
        return None
    
    def _get_deposit_address_params(self, coin: Coin) -> tuple[COIN_NAME, dict]:
        params = {
            "network": coin.network
        }
        return coin.name, params
