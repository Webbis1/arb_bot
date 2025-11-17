
import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
import functools


import asyncio
import functools

class Test:
    def __init__(self) -> None:
        self._is_running = asyncio.Event()
        # Устанавливаем событие, чтобы код работал
        # self._is_running.set()
    
    
    @property
    def working(self):
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                if self._is_running.is_set():
                    return await func("qqq", *args, **kwargs)
                else:
                    return "lox"        
            return wrapper
        return decorator
    

    async def test(self):
        print("start")
        @self.working
        async def ttt():
            return "Working"
            
        print(await ttt())
        
        self._is_running.set()
        print(await ttt())
        return "done"

obj = Test()
# Использование

@obj.working
async def main(aaa = "IIII"):
    # result = await obj.test()
    print(aaa)

asyncio.run(main())

obj._is_running.set()

asyncio.run(main())

# @asynccontextmanager
# async def async_context1():+
#     try:
#         yield "1"
#     except Exception as e:
#         print(f" 1 - ex - {e}")
#     finally:
#         print(" end 1")
        
# @asynccontextmanager
# async def async_context2():
#     try:
#         yield "2"
#     except Exception as e:
#         print(f" 2 - ex - {e}")
#         raise e
#     finally:
#         print(" end 2")


    
# async def test_multiple_contexts():
#     async with async_context1() as ctx1, async_context2() as ctx2:
#         print(f"{ctx1} ----  {ctx2}")
#         raise Exception("Test")
        
        
# async def test_exit_stack():
#     async with AsyncExitStack() as stack:
#         ctx1 = await stack.enter_async_context(async_context1())
#         ctx2 = await stack.enter_async_context(async_context2())
#         print(f"{ctx1} ---- {ctx2}")
#         raise Exception("Test")
        
# if __name__ == "__main__":
#     # Запуск демонстрации
#     # asyncio.run(test_exit_stack())
#     asyncio.run(test_multiple_contexts())
    