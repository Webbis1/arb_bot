from dataclasses import dataclass

@dataclass
class Coin:
    _address: str
    name: str = ''
    chain: str = ''
    fee: float = -1.0
    
    def __eq__(self, other):
        if isinstance(other, Coin): return self._address == other._address
        elif isinstance(other, str): return self._address == other
        else: return False
    
    def __hash__(self):
        return hash(self._address)
    
    def _is_unknown_fee(self, fee):
        """Проверяет, является ли комиссия неизвестной"""
        return fee == -1.0
    
    # Методы для сравнения по fee
    def __lt__(self, other):
        """Меньше чем - для min() и сортировки"""
        if isinstance(other, Coin):
            # Если обе комиссии неизвестны - равны
            if self._is_unknown_fee(self.fee) and self._is_unknown_fee(other.fee):
                return False
            # Если наша комиссия неизвестна - мы "больше" (хуже) любой известной
            if self._is_unknown_fee(self.fee):
                return False
            # Если комиссия другого неизвестна - мы "меньше" (лучше)
            if self._is_unknown_fee(other.fee):
                return True
            # Обе комиссии известны - обычное сравнение
            return self.fee < other.fee
            
        elif isinstance(other, (int, float)):
            if self._is_unknown_fee(self.fee):
                return False  # неизвестная комиссия "больше" любой известной
            return self.fee < other
            
        return NotImplemented
    
    def __le__(self, other):
        """Меньше или равно"""
        if isinstance(other, Coin):
            if self._is_unknown_fee(self.fee) and self._is_unknown_fee(other.fee):
                return True
            if self._is_unknown_fee(self.fee):
                return False
            if self._is_unknown_fee(other.fee):
                return True
            return self.fee <= other.fee
            
        elif isinstance(other, (int, float)):
            if self._is_unknown_fee(self.fee):
                return False
            return self.fee <= other
            
        return NotImplemented
    
    def __gt__(self, other):
        """Больше чем - для max()"""
        if isinstance(other, Coin):
            # Если обе комиссии неизвестны - равны
            if self._is_unknown_fee(self.fee) and self._is_unknown_fee(other.fee):
                return False
            # Если наша комиссия неизвестна - мы "больше" (хуже) любой известной
            if self._is_unknown_fee(self.fee):
                return True
            # Если комиссия другого неизвестна - мы "меньше" (лучше)
            if self._is_unknown_fee(other.fee):
                return False
            # Обе комиссии известны - обычное сравнение
            return self.fee > other.fee
            
        elif isinstance(other, (int, float)):
            if self._is_unknown_fee(self.fee):
                return True  # неизвестная комиссия "больше" любой известной
            return self.fee > other
            
        return NotImplemented
    
    def __ge__(self, other):
        """Больше или равно"""
        if isinstance(other, Coin):
            if self._is_unknown_fee(self.fee) and self._is_unknown_fee(other.fee):
                return True
            if self._is_unknown_fee(self.fee):
                return True
            if self._is_unknown_fee(other.fee):
                return False
            return self.fee >= other.fee
            
        elif isinstance(other, (int, float)):
            if self._is_unknown_fee(self.fee):
                return True
            return self.fee >= other
            
        return NotImplemented
    
    @property
    def has_known_fee(self):
        """Возвращает True если комиссия известна"""
        return not self._is_unknown_fee(self.fee)
    
    @property
    def address(self):
        return self._address
    
    @address.setter
    def address(self, value):
        raise AttributeError(f"{self._address}: the address cannot be changed")

    def __str__(self):
        return f"address is {self._address} - name is {self.name} - network is {self.chain} - fee is {self.fee}\n"
    
    def to_csv(self) -> str:
        """Конвертирует объект Coin в CSV строку"""
        # Экранируем кавычки и запятые в полях
        address = self._address.replace('"', '""')
        name = self.name.replace('"', '""')
        chain = self.chain.replace('"', '""')
        
        # Формируем CSV строку
        return f'"{address}","{name}","{chain}",{self.fee}'
    
    @classmethod
    def csv_header(cls) -> str:
        """Возвращает заголовок CSV файла"""
        return '"address","name","chain","fee"'