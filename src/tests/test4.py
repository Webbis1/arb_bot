import asyncio
from contextlib import asynccontextmanager
from enum import Enum, auto

class ExchangeState(Enum):
    DISABLED = auto()
    DISCONNECTED = auto()
    CONNECTING = auto()  
    CONNECTED = auto()


class Test:
    def __init__(self) -> None:
        self.__ex = "connected"
        self._lock = asyncio.Lock()
        self.state: ExchangeState = ExchangeState.CONNECTED
    
    async def reconnect(self):
        """Запускает переподключение в фоне, не блокируя вызов"""
        async with self._lock:
            if self.state == ExchangeState.DISCONNECTED:
                self.state = ExchangeState.CONNECTING
                print("🔄 Запуск переподключения в фоне...")
                # Запускаем переподключение в фоне, не ждем его
                asyncio.create_task(self._reconnect_background())
    
    async def _reconnect_background(self):
        """Фоновая задача переподключения"""
        await asyncio.sleep(4)  # имитация долгого переподключения
        async with self._lock:
            self.__ex = "connected"
            self.state = ExchangeState.CONNECTED
            print("✅ Подключение восстановлено")
    
    @property
    async def conn(self):
        async with self._lock:
            return self.__ex
        
    async def disconnect(self):
        async with self._lock:
            self.__ex = "disconnected"
            self.state = ExchangeState.DISCONNECTED
            print("❌ Отключено")
    
    
    @property
    @asynccontextmanager
    async def instance(self):
        print("🔓 Проверка состояния соединения...")
        
        # Если отключены - запускаем переподключение в фоне
        if self.state == ExchangeState.DISCONNECTED:
            print("⚠️ Соединение разорвано, запуск переподключения в фоне")
            await self.reconnect()
            print("🔒 Пропускаем выполнение блока - ожидание переподключения")
            yield None
            return
        
        # Если в процессе подключения - просто пропускаем выполнение
        elif self.state == ExchangeState.CONNECTING:
            print("⏳ Идет процесс переподключения, пропускаем выполнение")
            yield None
            return
        
        # Если подключены - выполняем блок кода
        elif self.state == ExchangeState.CONNECTED:
            try:
                connection = await self.conn
                print("✅ Соединение установлено, выполняем блок кода")
                yield connection
            except Exception as e:
                print(f"⚠️ Ошибка во время выполнения: {e}")
                if self.state == ExchangeState.CONNECTED:
                    await self.disconnect()
                await self.reconnect()
                raise
            finally:
                print("🔒 Завершение блока кода")
        else:
            # Для других состояний (DISABLED)
            print("🚫 Соединение отключено, пропускаем выполнение")
            yield None


async def main():
    test = Test()
    
    # Первое использование - должно работать
    print("=== Первое использование (подключено) ===")
    async with test.instance as ex:
        if ex is not None:
            print(f"Выполняем работу с: {ex}")
            # Имитация полезной работы
            await asyncio.sleep(1)
        else:
            print("Блок не выполнен - нет соединения")
    
    # Имитируем разрыв соединения
    print("\n=== Имитация разрыва соединения ===")
    await test.disconnect()
    
    # Использование после разрыва - должно пропустить выполнение
    print("\n=== Использование после разрыва ===")
    async with test.instance as ex:
        if ex is not None:
            print(f"Выполняем работу с: {ex}")
            await asyncio.sleep(1)
        else:
            print("Блок не выполнен - нет соединения")
    
    # Еще одно использование сразу после - все еще переподключается
    print("\n=== Использование во время переподключения ===")
    async with test.instance as ex:
        if ex is not None:
            print(f"Выполняем работу с: {ex}")
            await asyncio.sleep(1)
        else:
            print("Блок не выполнен - нет соединения")
    
    # Ждем завершения переподключения и пробуем снова
    print("\n=== Ожидание переподключения... ===")
    await asyncio.sleep(5)
    
    print("\n=== Использование после переподключения ===")
    async with test.instance as ex:
        if ex is not None:
            print(f"Выполняем работу с: {ex}")
            await asyncio.sleep(1)
        else:
            print("Блок не выполнен - нет соединения")
    
    print("\nПрограмма завершена")


if __name__ == "__main__":
    asyncio.run(main())