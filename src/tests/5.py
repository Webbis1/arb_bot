import asyncio
from contextlib import asynccontextmanager
import functools
from typing import Any, Callable, Awaitable, TypeVar

F = TypeVar('F', bound=Callable[..., Any])

class Cex:
    def __init__(self) -> None:
        self.name = "fff"
        self._is_running = asyncio.Event()
        self._is_running.set()
    
    def working(self, func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Первый аргумент - self экземпляра
            self_instance = args[0]
            if self_instance._is_running.is_set():
                return await func(*args, **kwargs)
            else:
                return "lox"
        return wrapper  # type: ignore
    
    @working
    async def buy(self) -> str:
        return f"Buy executed for {self.name}"
    
    
    


class Instance:
    def __init__(self) -> None:
        self.ins = "conn"
        self.working = True
        
    async def recon(self):
        await asyncio.sleep(5)
        self.working = True
    
    
    @property
    @asynccontextmanager
    async def conn(self):
        if not self.working: yield None
        
        
        try:
            yield self.ins
        
        except Exception as e:
            print(e)
            self.working = False
            asyncio.create_task(self.recon())
        
        finally:
            print("pidor")
            
async def test():
    ins = Instance()
    async with ins.conn as conn:
        if not conn: return
        
        print("work imitation")
        
