from dataclasses import dataclass



class CoinCreateError(ValueError):
    """Ошибка создания монеты"""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Coin validation failed: {', '.join(errors)}")

@dataclass(frozen=True)
class Coin:
    address: str
    name: str
    network: str
    fee: float
    min_amount: float
    
    def __post_init__(self):
        errors: list[str] = []
        
        # Валидация name
        if not isinstance(self.name, str) or not self.name.strip():
            errors.append(f"incorrect name - '{self.name}'")
        
        # Address МОЖЕТ быть пустым для нативных монет
        if not isinstance(self.address, str):
            errors.append(f"address must be string - '{self.address}'")
        
        # Валидация network (критически важна для нативных монет)
        if not isinstance(self.network, str) or not self.network.strip():
            errors.append(f"incorrect network - '{self.network}'")
        
        # Для токенов адрес обязателен
        # if self.network not in ['BTC', 'ETH', 'BNB', 'TRX', 'MATIC'] and not self.address.strip():
        #     errors.append(f"token must have contract address - {self.name} on {self.network}")
        
        # Остальная валидация...
        if not isinstance(self.fee, (int, float)) or self.fee < 0:
            errors.append(f"incorrect fee - {self.fee}")
        
        if not isinstance(self.min_amount, (int, float)) or self.min_amount < 0:
            errors.append(f"incorrect min_amount - {self.min_amount}")
        
        if errors:
            raise CoinCreateError(errors)
        