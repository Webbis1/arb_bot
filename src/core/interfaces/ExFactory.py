from abc import ABC, abstractmethod
from core.interfaces import IExchange

class ExFactory(ABC):
    @abstractmethod
    async def close(self) -> None: ...
    
    @abstractmethod
    async def __aenter__(self): ...
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb): ...
    
    @abstractmethod
    def __iter__(self) -> IExchange: ...