import asyncio
from typing import Optional, Iterable
from datetime import datetime

from core.interfaces import Exchange
from core.models.dto import Coins, CoinDict
from core.models import Coin


# Задача: реализовать методы sell и buy и withdraw, которые работают с вымышленным балансом, то есть делают вид, что операция выполнилась успешно, но на самом деле запрос на биржу не отпавляется.
# для withdraw сделать задержку перевода 
# соединить между собой биржи чтоб при переводе с одной на другую, баланс на первой уменьшается, а на второй увеличивается
# подготовить отчетность по выполненным операциям


class ExchangeFake(Exchange):
    """Обёртка над реальной биржей с модельным балансом и отчётностью.

    - Реальные вызовы используются для соединения и получения списка монет.
    - Балансы и операции buy/sell/withdraw моделируются локально (без отправки ордеров).
    - Переводы между биржами эмулируются через общий реестр депозитных адресов.
    """

    # Глобальный реестр депозитных адресов: address -> (exchange, coin)
    _deposit_registry: dict[str, tuple["ExchangeFake", Coin]] = {}

    def __init__(self, ex: Exchange, name: str) -> None:
        self._ex = ex
        self._name = name
        self._balances: dict[Coin, float] = {}
        self._report: list[dict] = []

    # Утилиты
    def _now(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    def _add_report(self, kind: str, data: dict) -> None:
        rec = {"ts": self._now(), "exchange": self._name, "type": kind}
        rec.update(data)
        self._report.append(rec)

    def seed_balance(self, items: Iterable[tuple[Coin, float]]) -> None:
        """Инициализировать модельный баланс монетами."""
        for coin, amount in items:
            self._balances[coin] = self._balances.get(coin, 0.0) + float(amount)

    def set_deposit_address(self, coin: Coin, address: str) -> None:
        """Зарегистрировать адрес депозита для симуляции приходов с переводов."""
        self._deposit_registry[address] = (self, coin)

    def get_report(self) -> list[dict]:
        return list(self._report)

    # Exchange API (частично проксируем реальную биржу)
    async def connect(self) -> None:
        await self._ex.connect()

    async def close(self) -> None:
        await self._ex.close()

    async def get_current_coins(self) -> Coins:
        return await self._ex.get_current_coins()

    # Optionally: смоделированный баланс как CoinDict
    async def get_balance(self) -> CoinDict:
        return dict(self._balances)

    # Подписки-заглушки (наблюдатели нам здесь не нужны)
    async def subscribe_price(self, coin: Coin, sub) -> None:  # type: ignore[override]
        return None

    async def unsubscribe_price(self, coin: Coin, sub) -> None:  # type: ignore[override]
        return None

    async def subscribe_balance(self, sub) -> None:  # type: ignore[override]
        return None

    async def unsubscribe_balance(self, sub) -> None:  # type: ignore[override]
        return None

    # Trader (модельные операции)
    async def sell(self, coin: Coin, amount: float) -> None:
        if amount <= 0:
            raise ValueError("amount must be > 0")
        cur = self._balances.get(coin, 0.0)
        if cur + 1e-12 < amount:
            raise ValueError(f"insufficient balance {cur} < {amount}")
        self._balances[coin] = cur - amount
        self._add_report("sell", {"coin": coin.name or coin.address, "amount": amount})

    async def buy(self, coin: Coin, amount: float) -> None:
        if amount <= 0:
            raise ValueError("amount must be > 0")
        self._balances[coin] = self._balances.get(coin, 0.0) + amount
        self._add_report("buy", {"coin": coin.name or coin.address, "amount": amount})

    async def withdraw(
        self,
        coin: Coin,
        amount: float,
        address: str,
        tag: Optional[str] = None,
        params: dict = {},
    ) -> None:
        if amount <= 0:
            raise ValueError("amount must be > 0")
        cur = self._balances.get(coin, 0.0)
        if cur + 1e-12 < amount:
            raise ValueError(f"insufficient balance {cur} < {amount}")

        # Задержка перевода (эмуляция сети)
        delay_sec = float(params.get("delay_sec", 1.0))
        self._add_report(
            "withdraw_initiated",
            {"coin": coin.name or coin.address, "amount": amount, "to": address, "delay_sec": delay_sec},
        )
        await asyncio.sleep(delay_sec)

        # Списание на бирже-отправителе
        self._balances[coin] = cur - amount

        # Зачисление на бирже-получателе по адресу, если зарегистрирован
        dest = self._deposit_registry.get(address)
        if dest is not None:
            dest_ex, dest_coin = dest
            dest_ex._balances[dest_coin] = dest_ex._balances.get(dest_coin, 0.0) + amount
            dest_ex._add_report(
                "deposit",
                {"from": self._name, "coin": dest_coin.name or dest_coin.address, "amount": amount, "addr": address},
            )

        self._add_report(
            "withdraw_completed",
            {"coin": coin.name or coin.address, "amount": amount, "to": address},
        )