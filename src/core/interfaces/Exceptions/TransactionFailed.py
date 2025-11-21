import time


class TransactionFailed(Exception):
    """Кастомная ошибка, которая ведет себя как None"""
    
    def __init__(self, ex_name: str, reason: str | None = None, code: str = "UNKNOWN"):
        self.reason = reason or ""
        self.ex_name = ex_name
        self.code = code
        self.timestamp = time.time()
        super().__init__(reason)
    
    # Поведение как None
    def __bool__(self):
        return False
    
    def __len__(self):
        return 0
    
    def __str__(self):
        return f"TransactionFailed: {self.reason}"
    
    def __repr__(self):
        return f"TransactionFailed(reason={self.reason}, code={self.code})"
    
    # Сравнение с None
    def __eq__(self, other):
        return other is None or (isinstance(other, TransactionFailed) and self.reason == other.reason)
    
    # Дополнительные методы
    def is_expired(self, timeout_seconds=3600):
        return time.time() - self.timestamp > timeout_seconds
    
    def to_dict(self):
        return {"reason": self.reason, "code": self.code, "timestamp": self.timestamp}