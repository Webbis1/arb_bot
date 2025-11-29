import asyncio
from dataclasses import dataclass, field
import logging
import time
from contextlib import suppress
from typing import Dict, Iterable, Optional

import ccxt.pro as ccxtpro

from .config import api_keys as API
from core.interfaces import ExchangeConnectionError
from infrastructure.ExFactory import ExFactory
from infrastructure.observers import BalanceObserver, OkxObserver, RegularObserver


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ObserverRestartLimitExceeded(RuntimeError):
    """Исключение, возникающее при превышении лимита рестартов observer-а."""

    def __init__(self, observer_name: str, attempts: int, last_error: Optional[BaseException]):
        self.observer_name = observer_name
        self.attempts = attempts
        self.last_error = last_error
        message = (
            f"Observer '{observer_name}' превышает лимит рестартов ({attempts}). "
            "Требуется полная переинициализация."
        )
        if last_error:
            message += f" Последняя ошибка: {last_error!r}"
        super().__init__(message)


class ObserverSupervisor:
    """Следит за состоянием observer-ов и отвечает за их автоматический рестарт."""

    def __init__(
        self,
        observers: Iterable[BalanceObserver],
        *,
        stop_event: Optional[asyncio.Event] = None,
        restart_delay: float = 3.0,
        max_restart_delay: float = 30.0,
        max_restart_attempts: int = 5,
        reset_attempts_after: float = 60.0,
    ) -> None:
        self._observers = list(observers)
        self._stop_event = stop_event or asyncio.Event()
        self._restart_delay = restart_delay
        self._max_restart_delay = max_restart_delay
        self._max_restart_attempts = max_restart_attempts
        self._reset_attempts_after = reset_attempts_after

        self._tasks: Dict[BalanceObserver, asyncio.Task] = {}
        self._task_to_observer: Dict[asyncio.Task, BalanceObserver] = {}
        self._names: Dict[BalanceObserver, str] = {
            observer: getattr(getattr(observer, "ex", None), "id", observer.__class__.__name__)
            for observer in self._observers
        }
        self._running = False
        self._last_error: Optional[BaseException] = None

    async def run(self) -> None:
        if self._running:
            raise RuntimeError("ObserverSupervisor already running")

        self._running = True
        for observer in self._observers:
            self._start_observer_task(observer)

        try:
            while not self._stop_event.is_set():
                if not self._tasks:
                    break

                done, _ = await asyncio.wait(
                    self._tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for finished in done:
                    observer = self._task_to_observer.pop(finished, None)
                    if observer is None:
                        continue
                    self._tasks.pop(observer, None)

                    if finished.cancelled():
                        continue

                    exc = finished.exception()

                    if self._stop_event.is_set():
                        # Останавливаемся по запросу
                        continue

                    if exc is None:
                        logger.warning(
                            "Observer %s завершил работу без ошибок. Перезапуск...",
                            self._names.get(observer, repr(observer)),
                        )
                        self._start_observer_task(observer)
                        continue

                    if isinstance(exc, ObserverRestartLimitExceeded):
                        self._last_error = exc
                        logger.error(str(exc))
                        self.stop()
                        break

                    logger.warning(
                        "Observer %s завершился с ошибкой: %r. Перезапуск...",
                        self._names.get(observer, repr(observer)),
                        exc,
                    )
                    self._start_observer_task(observer)

            if self._last_error:
                raise self._last_error

        finally:
            await self._shutdown()
            self._running = False

    def stop(self) -> None:
        self._stop_event.set()

    async def _shutdown(self) -> None:
        # Останавливаем observer-ы корректно
        for observer in self._observers:
            with suppress(Exception):
                await observer.stop()

        # Отменяем все задачи
        for task in list(self._tasks.values()):
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

        self._tasks.clear()
        self._task_to_observer.clear()

    def _start_observer_task(self, observer: BalanceObserver) -> None:
        if self._stop_event.is_set():
            return

        task = asyncio.create_task(self._run_single_observer(observer))
        self._tasks[observer] = task
        self._task_to_observer[task] = observer

    async def _run_single_observer(self, observer: BalanceObserver) -> None:
        name = self._names.get(observer, observer.__class__.__name__)
        attempts = 0
        last_error: Optional[BaseException] = None

        while not self._stop_event.is_set():
            started_at = time.monotonic()
            try:
                await observer.start()
                last_error = RuntimeError(f"Observer {name} остановился без ошибки")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning("Observer %s получил исключение: %r", name, exc)

            runtime = time.monotonic() - started_at

            if runtime >= self._reset_attempts_after:
                attempts = 0
            else:
                attempts += 1

            if self._stop_event.is_set():
                break

            if self._max_restart_attempts and attempts > self._max_restart_attempts:
                raise ObserverRestartLimitExceeded(name, attempts, last_error)

            delay = min(self._restart_delay * (2 ** max(attempts - 1, 0)), self._max_restart_delay)
            logger.info("Перезапуск observer %s через %.1f секунд (попытка %d)", name, delay, attempts)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                break
            except asyncio.TimeoutError:
                continue




class BalanceLoggingSubscriber:
    """Простейший подписчик, логирующий обновления баланса."""

    def __init__(self, source_name: str = "BalanceLoggingSubscriber") -> None:
        self._source_name = source_name

    async def update_price(self, coin: str, change: float) -> None:
        logger.info("[%s] Coin=%s Change=%s", self._source_name, coin, change)


@dataclass
class AutoReconnectBot:
    """Оркестратор, обеспечивающий автоматическое переподключение при сбоях."""
    
    # Обязательные параметры
    _api_config: Dict[str, Dict]
    routes: Dict[str, Dict[int, Dict[str, str]]]
    
    # Параметры переподключения наблюдателя
    observer_restart_attempts: int = field(default=5)
    observer_restart_delay: float = field(default=3.0)
    observer_restart_delay_max: float = field(default=30.0)
    observer_reset_window: float = field(default=60.0)
    
    # Параметры переподключения цикла
    cycle_restart_delay: float = field(default=5.0)
    cycle_restart_delay_max: float = field(default=90.0)
    
    # Параметры сетевого пробы
    _network_probe_host: str = field(default="1.1.1.1")
    _network_probe_port: int = field(default=53)
    _network_probe_timeout: float = field(default=3.0)
    _network_probe_interval: float = field(default=5.0)
    
    # Внутренние состояния (не включаются в repr)
    _shutdown_event: asyncio.Event = field(init=False, repr=False, compare=False)
    _current_supervisor: Optional['ObserverSupervisor'] = field(
        init=False, repr=False, compare=False, default=None
    )
    
    def __post_init__(self):
        self._shutdown_event = asyncio.Event()

    async def run(self) -> None:
        restart_attempt = 0

        while not self._shutdown_event.is_set():
            try:
                await self._run_cycle()
                restart_attempt = 0
            except asyncio.CancelledError:
                raise
            except (ExchangeConnectionError, ObserverRestartLimitExceeded, ccxtpro.NetworkError) as exc:
                restart_attempt += 1
                delay = min(self.cycle_restart_delay * (2 ** max(restart_attempt - 1, 0)), self.cycle_restart_delay_max)
                logger.warning(
                    "Произошла ошибка работы ботa (%s). Попытка перезапуска №%d через %.1f секунд.",
                    exc,
                    restart_attempt,
                    delay,
                )
                await self._wait_for_network()
                if await self._wait_for_shutdown(delay):
                    break
            except Exception as exc:  # noqa: BLE001
                restart_attempt += 1
                delay = min(self.cycle_restart_delay * (2 ** max(restart_attempt - 1, 0)), self.cycle_restart_delay_max)
                logger.exception("Необработанная ошибка в цикле: %s", exc)
                await self._wait_for_network()
                if await self._wait_for_shutdown(delay):
                    break

        logger.info("AutoReconnectBot остановлен.")

    async def stop(self) -> None:
        self._shutdown_event.set()
        if self._current_supervisor:
            self._current_supervisor.stop()

    async def _run_cycle(self) -> None:
        async with ExFactory(self._api_config) as factory:
            observers = self._build_observers(factory)

            if not observers:
                logger.warning("Не обнаружено подключенных бирж. Ожидание новых подключений...")
                await self._wait_for_shutdown(self._network_probe_interval)
                return

            subscriber = BalanceLoggingSubscriber()
            for observer in observers:
                observer.subscribe(subscriber)

            supervisor = ObserverSupervisor(
                observers,
                stop_event=self._shutdown_event,
                restart_delay=self.observer_restart_delay,
                max_restart_delay=self.observer_restart_delay_max,
                max_restart_attempts=self.observer_restart_attempts,
                reset_attempts_after=self.observer_reset_window,
            )

            self._current_supervisor = supervisor
            try:
                await supervisor.run()
            finally:
                self._current_supervisor = None

    def _build_observers(self, factory: ExFactory) -> list[BalanceObserver]:
        observers: list[BalanceObserver] = []
        for exchange in factory:
            if getattr(exchange, "id", "").lower() == "okx":
                observers.append(OkxObserver(exchange))
            else:
                observers.append(RegularObserver(exchange))
        return observers

    async def _wait_for_network(self) -> None:
        while not self._shutdown_event.is_set():
            if await self._probe_network():
                return
            logger.info("Сеть недоступна. Повторная проверка через %.1f секунд.", self._network_probe_interval)
            if await self._wait_for_shutdown(self._network_probe_interval):
                break

    async def _probe_network(self) -> bool:
        """Проверяет доступность сети через TCP-соединение к DNS-серверу."""
        try:
            # Пытаемся подключиться к DNS-серверу
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._network_probe_host, 
                    self._network_probe_port
                ),
                timeout=self._network_probe_timeout
            )
            
            # Немедленно закрываем соединение
            writer.close()
            await writer.wait_closed()
            return True
            
        except (asyncio.TimeoutError, OSError, ConnectionError):
            # Конкретные сетевые ошибки
            return False
        except Exception as e:
            # Логируем неожиданные ошибки
            logger.debug(f"Unexpected network probe error: {e}")
            return False

    async def _wait_for_shutdown(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False


async def main() -> None:
    bot = AutoReconnectBot(API, {})
    try:
        await bot.run()
    except asyncio.CancelledError:
        raise
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки. Завершение работы...")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())

