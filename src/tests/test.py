import asyncio
import logging
import sys
from pathlib import Path


# Обеспечиваем добавление `src` в sys.path при запуске из корня проекта
PROJECT_ROOT = Path(__file__).parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


from app.config import api_keys as API  # noqa: E402
from core.interfaces import ExchangeConnectionError  # noqa: E402
from infrastructure.ExFactory import ExFactory  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test")


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

            # Моделируем действия по каждой бирже
            tasks = [simulate_trade_and_transfer(exchange) for exchange in factory.values()]
            if tasks:
                await asyncio.gather(*tasks)
            else:
                logger.warning("No connected exchanges to simulate actions.")

            logger.info("All simulations completed. Closing connections...")

    except ExchangeConnectionError as e:
        logger.error("Exchange connection error: %s", e)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception("Unexpected error: %s", e)


if __name__ == "__main__":
    asyncio.run(main())


