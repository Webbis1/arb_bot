import asyncio
import logging
import importlib
import sys
from pathlib import Path


# Обеспечиваем добавление `src` и `Crypto` в sys.path при запуске из корня проекта
PROJECT_ROOT = Path(__file__).parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
CRYPTO_PATH = PROJECT_ROOT / "Crypto"
if str(CRYPTO_PATH) not in sys.path:
    sys.path.insert(0, str(CRYPTO_PATH))


from app.config import api_keys as API  # noqa: E402
from core.interfaces import ExchangeConnectionError  # noqa: E402
from infrastructure.ExFactory import ExFactory  # noqa: E402
# Импортируем наблюдателей из устоявшегося кода в папке Crypto динамически,
# чтобы избежать проблем статического анализа путей
_okx_module = importlib.import_module("Exchange2.Observers.OkxObserver")
OkxObserver = getattr(_okx_module, "OkxObserver")
_reg_module = importlib.import_module("Exchange2.Observers.RegularObserver")
RegularObserver = getattr(_reg_module, "RegularObserver")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test")


SYMBOLS_TO_SCAN = (
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
)
SPREAD_THRESHOLD_PCT = 0.05  # минимальный спред в %, при котором показываем возможность
TOP_N = 5


async def get_usdt_balance(exchange) -> float:
    """Получить баланс USDT (или близких вариантов) с биржи ccxt.pro."""
    try:
        balance_data = await exchange.fetch_balance()
        total = balance_data.get("total", {}) or {}
        for key in ("USDT", "usdt", "Usdt", "usd"):
            if key in total:
                try:
                    return float(total[key])
                except (TypeError, ValueError):
                    return 0.0
        return 0.0
    except Exception as e:
        logger.error("%s: error fetching balance: %s", getattr(exchange, "id", "unknown"), e)
        return 0.0


def get_taker_fee(exchange, symbol: str) -> float:
    """Получить taker fee из загруженных рынков, если доступно."""
    try:
        m = exchange.markets.get(symbol) if hasattr(exchange, "markets") else None
        if not m:
            return 0.0
        fee = m.get("taker")
        if isinstance(fee, (int, float)) and fee >= 0:
            return float(fee)
    except Exception:
        pass
    return 0.0


async def get_usdt_withdrawal_fee(exchange) -> float:
    """Оценить комиссию вывода USDT как величину в USDT (если доступно через биржу)."""
    try:
        if hasattr(exchange, "fetchDepositWithdrawFees"):
            fees = await exchange.fetchDepositWithdrawFees(["USDT"])  # type: ignore[attr-defined]
            # Ожидаемый формат ccxt: { info, withdraw: { USDT: { networks: { NET: { withdraw: { fee } } } } } }
            withdraw = (fees or {}).get("withdraw", {})
            usdt = withdraw.get("USDT") if isinstance(withdraw, dict) else None
            networks = (usdt or {}).get("networks") if isinstance(usdt, dict) else None
            best = None
            if isinstance(networks, dict):
                for net, data in networks.items():
                    fee = (((data or {}).get("withdraw") or {}).get("fee"))
                    if isinstance(fee, (int, float)) and fee >= 0:
                        if best is None or fee < best:
                            best = float(fee)
            if isinstance(best, (int, float)):
                return float(best)
        # fallback для некоторых бирж
        if hasattr(exchange, "fees"):
            w = getattr(exchange, "fees", {}).get("withdraw", {})
            fee = w.get("USDT") if isinstance(w, dict) else None
            if isinstance(fee, (int, float)) and fee >= 0:
                return float(fee)
    except Exception:
        return 0.0
    return 0.0


async def fetch_ticker_safe(exchange, symbol: str) -> dict | None:
    """Безопасно получить тикер по символу; вернуть None при ошибке."""
    try:
        return await exchange.fetch_ticker(symbol)
    except Exception as e:
        logger.debug("%s: fetch_ticker failed for %s: %s", getattr(exchange, "id", "unknown"), symbol, e)
        return None


async def collect_tickers(factory, symbols: tuple[str, ...]) -> dict:
    """Собрать тикеры для набора символов по всем подключённым биржам.

    Возвращает структуру: { symbol: { ex_name: ticker_dict } }.
    """
    result: dict[str, dict[str, dict]] = {}
    for symbol in symbols:
        tasks = []
        exchanges = []
        for ex_name, ex in factory.items():
            exchanges.append((ex_name, ex))
            tasks.append(fetch_ticker_safe(ex, symbol))
        tickers = await asyncio.gather(*tasks)
        symbol_map: dict[str, dict] = {}
        for (ex_name, _), t in zip(exchanges, tickers):
            if t is not None:
                symbol_map[ex_name] = t
        result[symbol] = symbol_map
    return result


def find_best_opportunities(tickers_by_symbol: dict) -> list[dict]:
    """Найти лучшие варианты обмена (купить на бирже с лучшим ask, продать на бирже с лучшим bid).

    Возвращает список словарей: {symbol, buy_ex, buy_ask, sell_ex, sell_bid, spread_pct}.
    """
    opportunities: list[dict] = []
    for symbol, ex_map in tickers_by_symbol.items():
        if not ex_map:
            continue
        best_ask = None
        best_ask_ex = None
        best_bid = None
        best_bid_ex = None
        for ex_name, t in ex_map.items():
            ask = t.get("ask")
            bid = t.get("bid")
            if isinstance(ask, (int, float)) and ask > 0:
                if best_ask is None or ask < best_ask:
                    best_ask = ask
                    best_ask_ex = ex_name
            if isinstance(bid, (int, float)) and bid > 0:
                if best_bid is None or bid > best_bid:
                    best_bid = bid
                    best_bid_ex = ex_name
        if best_ask is None or best_bid is None:
            continue
        if best_bid_ex == best_ask_ex:
            continue
        spread_pct = (best_bid - best_ask) / best_ask * 100.0
        if spread_pct >= SPREAD_THRESHOLD_PCT:
            opportunities.append({
                "symbol": symbol,
                "buy_ex": best_ask_ex,
                "buy_ask": best_ask,
                "sell_ex": best_bid_ex,
                "sell_bid": best_bid,
                "spread_pct": spread_pct,
            })
    # сортируем по убыванию спреда
    opportunities.sort(key=lambda x: x["spread_pct"], reverse=True)
    return opportunities[:TOP_N]


async def refine_with_fees(factory, opportunities: list[dict]) -> list[dict]:
    """Для каждого варианта посчитать нетто-спред с учётом taker fee и вывода USDT.

    Модель (dry-run):
      net_spread_pct ≈ ((sell_bid*(1 - taker_sell)) - (buy_ask*(1 + taker_buy)) - transfer_cost_usdt) / buy_ask * 100
    где transfer_cost_usdt — минимальная комиссия вывода USDT с биржи покупки.
    """
    if not opportunities:
        return []
    # Предрасчёт комиссий вывода USDT по биржам
    usdt_withdraw_fee_by_ex: dict[str, float] = {}
    for ex_name, ex in factory.items():
        usdt_withdraw_fee_by_ex[ex_name] = await get_usdt_withdrawal_fee(ex)

    refined: list[dict] = []
    for opp in opportunities:
        symbol = opp["symbol"]
        buy_ex_name = opp["buy_ex"]
        sell_ex_name = opp["sell_ex"]
        buy_ask = opp["buy_ask"]
        sell_bid = opp["sell_bid"]
        buy_ex = dict(factory.items()).get(buy_ex_name)
        sell_ex = dict(factory.items()).get(sell_ex_name)
        taker_buy = get_taker_fee(buy_ex, symbol) if buy_ex else 0.0
        taker_sell = get_taker_fee(sell_ex, symbol) if sell_ex else 0.0
        transfer_cost_usdt = usdt_withdraw_fee_by_ex.get(buy_ex_name, 0.0)

        gross = sell_bid - buy_ask
        fees_value = (sell_bid * taker_sell) + (buy_ask * taker_buy) + transfer_cost_usdt
        net = gross - fees_value
        net_pct = (net / buy_ask) * 100.0

        new_item = dict(opp)
        new_item.update({
            "taker_buy": taker_buy,
            "taker_sell": taker_sell,
            "usdt_withdraw_fee": transfer_cost_usdt,
            "net_spread_pct": net_pct,
        })
        refined.append(new_item)

    refined.sort(key=lambda x: x["net_spread_pct"], reverse=True)
    return refined


async def simulate_trade_and_transfer(exchange) -> None:
    """Смоделировать покупку/перевод/продажу с паузами (без реальных ордеров)."""
    ex_id = getattr(exchange, "id", "unknown")
    logger.info("[%s] Simulate BUY BTC/USDT amount=0.001 ...", ex_id)
    await asyncio.sleep(1.0)
    logger.info("[%s] Simulate TRANSFER USDT 10.0 to internal wallet ...", ex_id)
    await asyncio.sleep(1.0)
    logger.info("[%s] Simulate SELL BTC/USDT amount=0.001 ...", ex_id)
    await asyncio.sleep(1.0)


async def main():
    try:
        async with ExFactory(API) as factory:
            logger.info("Connected exchanges: %s", ", ".join(factory.exchange_names) or "<none>")

            # Проверяем балансы по каждой бирже
            for ex_name, exchange in factory.items():
                usdt = await get_usdt_balance(exchange)
                logger.info("%s: USDT balance = %.6f", ex_name, usdt)

            # Запускаем реальные наблюдатели за балансами через WebSocket для каждой биржи
            observers = []
            for ex in factory:
                if getattr(ex, "id", "").lower() == "okx":
                    observers.append(OkxObserver(ex))
                else:
                    observers.append(RegularObserver(ex))

            # Запускаем наблюдение параллельно и даём поработать N секунд
            observer_tasks = [asyncio.create_task(obs.start()) for obs in observers]
            try:
                # Даём время на получение нескольких событий баланса
                await asyncio.sleep(10)
            finally:
                for obs in observers:
                    await obs.stop()
                for t in observer_tasks:
                    if not t.done():
                        t.cancel()
                # Ждём корректного завершения задач
                await asyncio.gather(*observer_tasks, return_exceptions=True)

            logger.info("Balance observation finished. Proceed to simulated trade/transfer actions...")

            # Сбор тикеров и поиск лучших вариантов для обмена
            logger.info("Собираем тикеры по символам: %s", ", ".join(SYMBOLS_TO_SCAN))
            tickers_by_symbol = await collect_tickers(factory, SYMBOLS_TO_SCAN)
            opportunities = find_best_opportunities(tickers_by_symbol)
            if opportunities:
                logger.info("Топ вариантов обмена (валовой спред >= %.4f%%):", SPREAD_THRESHOLD_PCT)
                for opp in opportunities:
                    logger.info(
                        "%s: BUY@%s ask=%.6f -> SELL@%s bid=%.6f | spread=%.4f%%",
                        opp["symbol"], opp["buy_ex"], opp["buy_ask"], opp["sell_ex"], opp["sell_bid"], opp["spread_pct"],
                    )

                # Дополнительно считаем нетто-спред с учётом комиссий (dry-run)
                refined = await refine_with_fees(factory, opportunities)
                if refined:
                    logger.info("Нетто варианты с учётом taker и вывода USDT:")
                    for opp in refined[:TOP_N]:
                        logger.info(
                            "%s: BUY@%s ask=%.6f (taker=%.4f) -> SELL@%s bid=%.6f (taker=%.4f); withdraw(USDT@%s)=%.6f | net=%.4f%%",
                            opp["symbol"], opp["buy_ex"], opp["buy_ask"], opp["taker_buy"], opp["sell_ex"], opp["sell_bid"], opp["taker_sell"], opp["buy_ex"], opp["usdt_withdraw_fee"], opp["net_spread_pct"],
                        )
                else:
                    logger.info("Нетто-варианты не найдены.")
            else:
                logger.info("Подходящих вариантов обмена не найдено при заданном пороге спреда.")

            # Дополнительно: моделируем торговлю/перевод (без реальных ордеров), если нужно
            sim_tasks = [simulate_trade_and_transfer(exchange) for exchange in factory.values()]
            if sim_tasks:
                await asyncio.gather(*sim_tasks)
            else:
                logger.warning("No connected exchanges for simulation.")

            logger.info("Test completed. Closing connections...")

    except ExchangeConnectionError as e:
        logger.error("Exchange connection error: %s", e)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception("Unexpected error: %s", e)


if __name__ == "__main__":
    asyncio.run(main())


