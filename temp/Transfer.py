import ccxt
import os
from decimal import Decimal

api_keys = {
    'binance': {
        'api_key': 'wMWuRuUvlORTAuRZAbqlmd7r8KIyL2UY2kd0gnNhyPUAxxOOUzXapYRsRZLZ9Auf',
        'api_secret': 'tJatzCwiGPWeulEwR48pkMqf8F5Exfj3FMV6QJFYC1xH9KL0xQU7AO2zScyPWDuT',
    },
    'okx': {
        'api_key': '7a9e7e40-0bc1-458f-b098-a7c8dae5f8c6',
        'api_secret': '74B2A62DE20C5F6415A7E917A3F9B220',
        'password': '@Arr1ess'
    },
    'bitget': {
        'api_key': 'bg_d2f35784890895eb13f84b393f211be5',
        'api_secret': '9be28baff7bde3464c84a3f52330ab123276877c46557a4b311950b6dfc2c0bf',
        'password': 'Ar1essTest'
    },
    'gate': {
        'api_key': '3c161daae69c4add254f58a221b3df3a',
        'api_secret': 'ac93d7767b2e652da91ee959bfce0e1a34873e632c17e1858986ba75e9d55b09',
    },
    'kucoin': {
        'api_key': '68eba1be03ad1c00011b0a37',  
        'api_secret': 'e3d6c2ad-6ac3-4ae7-a605-28b59d937453',
        'password': 'rABSQCS5XR5ubqh'
    },
}




class CrossExchangeTransfer:
    def __init__(self):
        # Инициализация бирж
        self.kucoin = ccxt.kucoin({
            'apiKey': api_keys['kucoin']['api_key'],
            'secret': api_keys['kucoin']['api_secret'],
            'password': api_keys['kucoin']['password'],
            'sandbox': False,
        })
        
        self.bitget = ccxt.bitget({
            'apiKey': api_keys['bitget']['api_key'],
            'secret': api_keys['bitget']['api_secret'],
            'password': api_keys['bitget']['password'],
            'sandbox': False,
        })
        
        # Правильные названия сетей для каждой биржи
        self.networks = {
            'kucoin': 'BSC',  # KuCoin использует BSC для BEP20
            'bitget': 'BEP20'  # BitGet использует BEP20
        }
        self.usdt_symbol = 'USDT'

    def get_balance(self, exchange, symbol='USDT'):
        """Получить баланс на бирже"""
        try:
            balance = exchange.fetch_balance()
            return Decimal(str(balance['total'].get(symbol, 0)))
        except Exception as e:
            print(f"Ошибка получения баланса: {e}")
            return Decimal('0')

    def get_available_balance(self, exchange, symbol='USDT'):
        """Получить доступный баланс (free) на бирже"""
        try:
            balance = exchange.fetch_balance()
            return Decimal(str(balance['free'].get(symbol, 0)))
        except Exception as e:
            print(f"Ошибка получения доступного баланса: {e}")
            return Decimal('0')

    def get_withdrawal_info(self, exchange, symbol='USDT', network='BSC'):
        """Получить информацию о выводе: комиссию, минимальную и максимальную сумму"""
        try:
            currencies = exchange.fetch_currencies()
            if symbol in currencies:
                currency_info = currencies[symbol]
                if network in currency_info.get('networks', {}):
                    network_info = currency_info['networks'][network]
                    fee = Decimal(str(network_info.get('fee', 0)))
                    min_amount = Decimal(str(network_info.get('limits', {}).get('withdraw', {}).get('min', 0)))
                    max_amount = Decimal(str(network_info.get('limits', {}).get('withdraw', {}).get('max', 0)))
                    
                    return {
                        'fee': fee,
                        'min_amount': min_amount,
                        'max_amount': max_amount
                    }
            
            # # Значения по умолчанию если не удалось получить информацию
            # if exchange == self.kucoin:
            #     return {
            #         'fee': Decimal('0.8'),
            #         'min_amount': Decimal('10'),
            #         'max_amount': Decimal('100000')
            #     }
            # else:
            #     return {
            #         'fee': Decimal('1.0'),
            #         'min_amount': Decimal('5'),
            #         'max_amount': Decimal('100000')
            #     }
                
        except Exception as e:
            print(f"Ошибка получения информации о выводе: {e}")
            # Безопасные значения по умолчанию
            return {
                'fee': Decimal('1.0'),
                'min_amount': Decimal('10'),
                'max_amount': Decimal('100000')
            }

    def get_available_networks(self, exchange, symbol='USDT'):
        """Получить доступные сети для вывода"""
        try:
            currencies = exchange.fetch_currencies()
            if symbol in currencies:
                currency_info = currencies[symbol]
                networks = currency_info.get('networks', {})
                print(f"Доступные сети для {exchange.name}: {list(networks.keys())}")
                return networks
            return {}
        except Exception as e:
            print(f"Ошибка получения сетей: {e}")
            return {}

    def transfer_usdt(self, direction, amount, address=None):
        """
        Перевод USDT между KuCoin и BitGet
        
        Args:
            direction (str): 'kucoin_to_bitget' или 'bitget_to_kucoin'
            amount (float): количество USDT для перевода
            address (str): целевой адрес (опционально)
        """
        
        try:
            amount_decimal = Decimal(str(amount))
            
            if direction == 'kucoin_to_bitget':
                return self._transfer_kucoin_to_bitget(amount_decimal, address)
            elif direction == 'bitget_to_kucoin':
                return self._transfer_bitget_to_kucoin(amount_decimal, address)
            else:
                return {'success': False, 'error': 'Неверное направление. Используйте: kucoin_to_bitget или bitget_to_kucoin'}
                
        except Exception as e:
            return {'success': False, 'error': f'Ошибка при переводе: {str(e)}'}

    def _transfer_kucoin_to_bitget(self, amount, bitget_address=None):
        """Перевод с KuCoin на BitGet"""
        print(f"Начинаем перевод {amount} USDT с KuCoin на BitGet...")
        
        # Получаем доступный баланс KuCoin
        kucoin_balance = self.get_available_balance(self.kucoin)
        print(f"Доступный баланс на KuCoin: {kucoin_balance} USDT")
        
        # Получаем информацию о выводе
        withdrawal_info = self.get_withdrawal_info(self.kucoin, self.usdt_symbol, self.networks['kucoin'])
        fee = withdrawal_info['fee']
        min_amount = withdrawal_info['min_amount']
        max_amount = withdrawal_info['max_amount']
        
        print(f"Комиссия вывода с KuCoin: {fee} USDT")
        print(f"Минимальная сумма вывода: {min_amount} USDT")
        print(f"Максимальная сумма вывода: {max_amount} USDT")
        
        # Проверяем минимальную сумму
        if amount < min_amount:
            return {'success': False, 'error': f'Сумма меньше минимальной. Минимум: {min_amount} USDT, указано: {amount} USDT'}
        
        # Проверяем максимальную сумму
        if amount > max_amount:
            return {'success': False, 'error': f'Сумма больше максимальной. Максимум: {max_amount} USDT, указано: {amount} USDT'}
        
        # Проверяем баланс
        if kucoin_balance < amount:
            return {'success': False, 'error': f'Недостаточно средств на KuCoin. Доступно: {kucoin_balance} USDT'}
        
        # Получаем адрес BitGet если не указан
        if not bitget_address:
            bitget_address = self._get_bitget_deposit_address()
            if not bitget_address:
                return {'success': False, 'error': 'Не удалось получить адрес депозита BitGet'}
        
        # Проверяем, что сумма с учетом комиссии доступна
        total_amount = amount + fee
        if kucoin_balance < total_amount:
            return {'success': False, 'error': f'Недостаточно средств с учетом комиссии. Нужно: {total_amount} USDT, доступно: {kucoin_balance} USDT'}
        
        try:
            # Выполняем вывод с KuCoin используя сеть BSC
            print(f"Вывод с KuCoin на адрес: {bitget_address}, сеть: {self.networks['kucoin']}")
            
            withdrawal = self.kucoin.withdraw(
                code=self.usdt_symbol,
                amount=float(amount),
                address=bitget_address,
                tag=None,
                params={'chain': self.networks['kucoin'].lower()}
            )
            
            return {
                'success': True,
                'id': withdrawal['id'],
                'amount': float(amount),
                'fee': float(fee),
                'from': 'kucoin',
                'to': 'bitget',
                'address': bitget_address,
                'network': self.networks['kucoin'],
                'total_cost': float(total_amount)
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Ошибка вывода с KuCoin: {str(e)}'}

    def _transfer_bitget_to_kucoin(self, amount, kucoin_address=None):
        """Перевод с BitGet на KuCoin"""
        print(f"Начинаем перевод {amount} USDT с BitGet на KuCoin...")
        
        # Получаем доступный баланс BitGet
        bitget_balance = self.get_available_balance(self.bitget)
        print(f"Доступный баланс на BitGet: {bitget_balance} USDT")
        
        # Получаем информацию о выводе
        withdrawal_info = self.get_withdrawal_info(self.bitget, self.usdt_symbol, self.networks['bitget'])
        fee = withdrawal_info['fee']
        min_amount = withdrawal_info['min_amount']
        max_amount = withdrawal_info['max_amount']
        
        print(f"Комиссия вывода с BitGet: {fee} USDT")
        print(f"Минимальная сумма вывода: {min_amount} USDT")
        print(f"Максимальная сумма вывода: {max_amount} USDT")
        
        # Проверяем минимальную сумму
        if amount < min_amount:
            return {'success': False, 'error': f'Сумма меньше минимальной. Минимум: {min_amount} USDT, указано: {amount} USDT'}
        
        # Проверяем максимальную сумму
        if amount > max_amount:
            return {'success': False, 'error': f'Сумма больше максимальной. Максимум: {max_amount} USDT, указано: {amount} USDT'}
        
        # Проверяем баланс
        if bitget_balance < amount:
            return {'success': False, 'error': f'Недостаточно средств на BitGet. Доступно: {bitget_balance} USDT'}
        
        # Получаем адрес KuCoin если не указан
        if not kucoin_address:
            kucoin_address = self._get_kucoin_deposit_address_advanced()
            if not kucoin_address:
                # Предлагаем ручной ввод
                print("Не удалось автоматически получить адрес KuCoin.")
                print("Пожалуйста, получите адрес депозита USDT-BSC вручную из приложения KuCoin")
                return {'success': False, 'error': 'Не удалось получить адрес депозита KuCoin. Получите его вручную из приложения KuCoin'}
        
        # Проверяем, что сумма с учетом комиссии доступна
        total_amount = amount + fee
        if bitget_balance < total_amount:
            return {'success': False, 'error': f'Недостаточно средств с учетом комиссии. Нужно: {total_amount} USDT, доступно: {bitget_balance} USDT'}
        
        try:
            # Выполняем вывод с BitGet с явным указанием сети
            print(f"Вывод с BitGet на адрес: {kucoin_address}, сеть: {self.networks['bitget']}")
            
            # Для BitGet используем правильный формат параметров
            withdrawal = self.bitget.withdraw(
                code=self.usdt_symbol,
                amount=float(amount),
                address=kucoin_address,
                tag=None,
                params={
                    'chain': self.networks['bitget'],
                    'network': self.networks['bitget']  # Явно указываем network
                }
            )
            
            return {
                'success': True,
                'id': withdrawal['id'],
                'amount': float(amount),
                'fee': float(fee),
                'from': 'bitget',
                'to': 'kucoin',
                'address': kucoin_address,
                'network': self.networks['bitget'],
                'total_cost': float(total_amount)
            }
            
        except Exception as e:
            print(f"Подробная ошибка BitGet: {e}")
            return {'success': False, 'error': f'Ошибка вывода с BitGet: {str(e)}'}

    def _get_kucoin_deposit_address_advanced(self):
        """Расширенный метод получения адреса депозита KuCoin"""
        print("Пытаемся получить адрес депозита KuCoin...")
        
        try:
            # Сначала пробуем получить список всех адресов депозита
            try:
                deposit_addresses = self.kucoin.fetch_deposit_addresses()
                print(f"Найдено {len(deposit_addresses)} адресов депозита")
                
                # Ищем USDT адрес с сетью BSC
                for currency, addresses in deposit_addresses.items():
                    if currency == 'USDT':
                        for address_info in addresses:
                            network = address_info.get('network')
                            address = address_info.get('address')
                            print(f"Найден адрес USDT: сеть={network}, адрес={address}")
                            if network in ['BSC', 'BEP20', 'BNB']:
                                print(f"Используем адрес для сети: {network}")
                                return address
            except Exception as e:
                print(f"Ошибка при получении списка адресов: {e}")

            # Если не нашли через fetch_deposit_addresses, пробуем традиционный метод
            networks_to_try = ['BSC', 'BEP20', 'BNB', 'BSC(BEP20)', 'ERC20']
            
            for network in networks_to_try:
                try:
                    print(f"Пробуем сеть: {network}")
                    deposit_address = self.kucoin.fetch_deposit_address(
                        'USDT', 
                        params={'chain': network.lower()}
                    )
                    if deposit_address and deposit_address.get('address'):
                        print(f"Успешно! Найден адрес KuCoin для сети: {network}")
                        return deposit_address['address']
                except Exception as e:
                    print(f"Не удалось для сети {network}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            print(f"Общая ошибка получения адреса KuCoin: {e}")
            return None

    def _get_bitget_deposit_address(self):
        """Получить адрес депозита BitGet для USDT BEP20"""
        try:
            # Пробуем разные варианты сетей
            networks_to_try = ['BEP20', 'BSC', 'BNB']
            
            for network in networks_to_try:
                try:
                    deposit_address = self.bitget.fetch_deposit_address(
                        'USDT', 
                        params={'chain': network}
                    )
                    print(f"Найден адрес BitGet для сети: {network}")
                    return deposit_address['address']
                except Exception as e:
                    print(f"Не удалось для сети {network}: {e}")
                    continue
            
            # Если ни одна сеть не сработала, пробуем без указания сети
            try:
                deposit_address = self.bitget.fetch_deposit_address('USDT')
                print("Найден адрес BitGet (без указания сети)")
                return deposit_address['address']
            except Exception as e:
                print(f"Ошибка получения адреса BitGet: {e}")
                return None
                
        except Exception as e:
            print(f"Общая ошибка получения адреса BitGet: {e}")
            return None

    def get_manual_kucoin_address(self):
        """Ручной ввод адреса KuCoin"""
        print("\n=== РУЧНОЙ ВВОД АДРЕСА KUCOIN ===")
        print("1. Откройте приложение KuCoin")
        print("2. Перейдите в 'Assets' -> 'Deposit'")
        print("3. Выберите USDT")
        print("4. Выберите сеть BSC (BEP20)")
        print("5. Скопируйте адрес депозита")
        
        address = input("Введите адрес депозита KuCoin: ").strip()
        if address and len(address) > 20:  # Базовая проверка
            return address
        else:
            print("Неверный адрес")
            return None

    def check_balances(self):
        """Проверить балансы на обеих биржах"""
        kucoin_total = self.get_balance(self.kucoin)
        kucoin_free = self.get_available_balance(self.kucoin)
        bitget_total = self.get_balance(self.bitget)
        bitget_free = self.get_available_balance(self.bitget)
        
        print(f"Баланс KuCoin: Всего: {kucoin_total} USDT, Доступно: {kucoin_free} USDT")
        print(f"Баланс BitGet: Всего: {bitget_total} USDT, Доступно: {bitget_free} USDT")
        
        return {
            'kucoin': {'total': float(kucoin_total), 'free': float(kucoin_free)},
            'bitget': {'total': float(bitget_total), 'free': float(bitget_free)}
        }

    def check_withdrawal_limits(self):
        """Проверить лимиты вывода для обеих бирж"""
        print("=== ЛИМИТЫ ВЫВОДА ===")
        
        kucoin_info = self.get_withdrawal_info(self.kucoin, self.usdt_symbol, self.networks['kucoin'])
        bitget_info = self.get_withdrawal_info(self.bitget, self.usdt_symbol, self.networks['bitget'])
        
        print(f"KuCoin - Мин: {kucoin_info['min_amount']} USDT, Комиссия: {kucoin_info['fee']} USDT")
        print(f"BitGet - Мин: {bitget_info['min_amount']} USDT, Комиссия: {bitget_info['fee']} USDT")
        
        recommended_min = max(kucoin_info['min_amount'], bitget_info['min_amount'])
        print(f"Рекомендуемый минимум для переводов: {recommended_min} USDT")
        
        return {
            'kucoin': kucoin_info,
            'bitget': bitget_info,
            'recommended_min': recommended_min
        }

# Пример использования
def main():
    # Инициализация трансфера
    transfer = CrossExchangeTransfer()
    
    # Проверяем доступные сети
    print("=== ДОСТУПНЫЕ СЕТИ ===")
    transfer.get_available_networks(transfer.bitget)
    transfer.get_available_networks(transfer.kucoin)
    
    # Проверяем лимиты вывода
    print("\n=== ПРОВЕРКА ЛИМИТОВ ===")
    limits = transfer.check_withdrawal_limits()
    
    # Проверяем балансы
    print("\n=== ПРОВЕРКА БАЛАНСОВ ===")
    balances = transfer.check_balances()
    
    # Получаем адрес BitGet
    print("\n=== ПОЛУЧЕНИЕ АДРЕСА BITGET ===")
    bitget_addr = transfer._get_bitget_deposit_address()
    print(f"BitGet адрес: {bitget_addr}")
    
    # Используем рекомендованную минимальную сумму
    test_amount = float(limits['recommended_min'] + Decimal('1'))

    # # Тест BitGet -> KuCoin (с ручным вводом адреса)
    # if balances['bitget']['free'] >= test_amount:
    #     print(f"\n=== ТЕСТ ПЕРЕВОДА BitGet -> KuCoin ({test_amount} USDT) ===")
        
    #     # Получаем адрес KuCoin вручную
    #     kucoin_addr = transfer.get_manual_kucoin_address()
    #     if kucoin_addr:
    #         result2 = transfer.transfer_usdt('bitget_to_kucoin', test_amount, kucoin_addr)
    #         print(f"Результат: {result2}")
    #     else:
    #         print("Не удалось получить адрес KuCoin")
    # else:
    #     print(f"\nНедостаточно доступных средств на BitGet для теста. Нужно: {test_amount}, доступно: {balances['bitget']['free']}")

if __name__ == "__main__":
    main()