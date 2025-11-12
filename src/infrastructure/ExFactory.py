import asyncio
import ccxt.pro as ccxtpro
import logging
import importlib
import os
from typing import Any, Optional, Union, ItemsView, ValuesView, KeysView, Type

from core.interfaces import ExchangeConnectionError, ExFactory as ExFactoryInterface, Exchange
from infrastructure.CcxtExchange import CcxtExchange
# from infrastructure.Exchenges.base_ccxt_exchange import CcxtExchange # Импортируем базовый класс

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)


class ExFactory(ExFactoryInterface):
    EXCHANGES_DIR = "infrastructure.Exchenges" # Путь к папке с реализациями

    def __init__(self, config: dict[str, dict[str, Any]]):
        self._config = config
        self._exchanges: dict[str, CcxtExchange] = {}
        self._validate_initial_config()
        logger.info("ExFactory initialized with provided configuration.")

    def _validate_initial_config(self) -> None:
        for ex_name, ex_config in self._config.items():
            if not all(k in ex_config for k in ['api_key', 'api_secret']):
                logger.warning(
                    f"Configuration for exchange '{ex_name}' is missing 'api_key' or 'api_secret'."
                )

    async def create_exchanges(self) -> None:
        logger.info("Attempting to create exchange connections...")
        tasks = [self._connect(ex_name, ex_config) for ex_name, ex_config in self._config.items()]
        results: list[Optional[ccxtpro.Exchange]] = await asyncio.gather(*tasks)

        for ex_name, exchange_instance in zip(self._config.keys(), results):
            if exchange_instance:
                # Динамическое определение класса биржи
                ExchangeClass: Type[CcxtExchange] = self._get_exchange_class(ex_name)
                self._exchanges[ex_name] = ExchangeClass(ex_name, exchange_instance)
                logger.info(f"✓ Exchange '{ex_name}' successfully connected.")
            else:
                logger.warning(f"✗ Exchange '{ex_name}' failed to connect. Check logs.")

    def _get_exchange_class(self, ex_name: str) -> Type[CcxtExchange]:
        """
        Динамически загружает специализированный класс биржи из подпапки Exchenges,
        если он существует, иначе возвращает базовый CcxtExchange.
        """
        module_name = f"{self.EXCHANGES_DIR}.{ex_name.lower()}" # Предполагаем имена файлов в нижнем регистре
        class_name = f"{ex_name.capitalize()}Exchange" # Предполагаем CamelCase для имени класса

        try:
            module = importlib.import_module(module_name)
            exchange_class = getattr(module, class_name, None)
            if exchange_class and issubclass(exchange_class, CcxtExchange):
                logger.debug(f"Loaded specialized class {class_name} for {ex_name}.")
                return exchange_class
            else:
                logger.warning(
                    f"Class {class_name} not found or is not a subclass of CcxtExchange in {module_name}. "
                    "Using base CcxtExchange."
                )
        except ImportError:
            logger.debug(f"No specialized module found for {ex_name} at {module_name}. Using base CcxtExchange.")
        except Exception as e:
            logger.error(f"Error loading specialized class for {ex_name}: {e}", exc_info=True)

        return CcxtExchange # Возвращаем базовый класс по умолчанию

    async def _connect(self, ex_name: str, ex_config: dict[str, Any]) -> Optional[ccxtpro.Exchange]:
        logger.debug(f"Connecting to '{ex_name}'...")
        try:
            exchange_class = getattr(ccxtpro, ex_name, None)
            if not exchange_class:
                logger.error(f"Exchange '{ex_name}' not supported by ccxt.pro.")
                return None
            if not all(k in ex_config for k in ['api_key', 'api_secret']):
                logger.error(f"Missing 'api_key' or 'api_secret' for '{ex_name}'.")
                return None

            params = {
                'apiKey': ex_config['api_key'],
                'secret': ex_config['api_secret'],
                'sandbox': ex_config.get('sandbox', False),
                'enableRateLimit': True,
                'timeout': 30000,
                'verify': False,
            }
            params.update({k: v for k, v in ex_config.items() if k not in ['api_key', 'api_secret', 'sandbox']})

            exchange = exchange_class(params)
            exchange.original_logger = logging.getLogger(f'ccxtpro.{ex_name}')
            await exchange.load_markets()
            logger.debug(f"Markets loaded for {ex_name}.")
            return exchange

        except ccxtpro.NetworkError as e:
            logger.error(f"✗ {ex_name}: Network error - {e}", exc_info=True)
        except ccxtpro.AuthenticationError as e:
            logger.error(f"✗ {ex_name}: Authentication error - {e}", exc_info=True)
        except ccxtpro.ExchangeError as e:
            logger.error(f"✗ {ex_name}: Exchange error - {e}", exc_info=True)
        except Exception as e:
            logger.error(f"✗ {ex_name}: Unexpected error - {e}", exc_info=True)
        return None

    # async def check_balances(self, currency: str = 'USDT') -> None:
    #     logger.info(f"Checking {currency} balances for all connected exchanges...")
    #     tasks = [self._check_single_balance(ex.name, ex.instance, currency) for ex in self._exchanges.values()]
    #     results: list[Union[float, BaseException]] = await asyncio.gather(*tasks, return_exceptions=True) # Исправлен тип

    #     error_exchanges: list[str] = []
    #     for i, (ex_name, result) in enumerate(zip(self._exchanges.keys(), results)):
    #         if isinstance(result, BaseException): # Проверка на BaseException
    #             error_exchanges.append(ex_name)
    #             logger.error(f"✗ {ex_name}: error fetching balance - {result}", exc_info=True)
    #         else:
    #             balance = result
    #             logger.debug(f"✓ {ex_name}: {currency} balance = {balance:.4f}")

    #     if error_exchanges:
    #         raise ExchangeConnectionError(
    #             f"Failed to fetch balances from: {', '.join(error_exchanges)}."
    #         )
    #     logger.info(f"{currency} balance check completed.")

    # async def _check_single_balance(self, ex_name: str, exchange: ccxtpro.Exchange, currency: str) -> float:
    #     balance_data = await exchange.fetch_balance()
    #     total_balance = balance_data['total']

    #     currency_lower = currency.lower()

    #     for key in total_balance.keys():
    #         if key.lower() == currency_lower:
    #             return float(total_balance[key])
    #     return 0.0

    async def close(self) -> None:
        logger.info("Closing all exchange connections...")
        if not self._exchanges:
            logger.info("No exchanges to close.")
            return

        tasks = [self._close_single_exchange(ex.name, ex.instance) for ex in list(self._exchanges.values())]
        await asyncio.gather(*tasks)
        self._exchanges.clear()
        logger.info("All exchange connections closed.")

    async def _close_single_exchange(self, ex_name: str, exchange: ccxtpro.Exchange) -> None:
        try:
            if hasattr(exchange, 'close'):
                await exchange.close()
            elif hasattr(exchange, '__del__'):
                exchange.__del__()
            logger.info(f"Exchange '{ex_name}' closed.")
        except asyncio.CancelledError:
            logger.debug(f"Exchange '{ex_name}': background tasks cancelled (expected for some exchanges).")
        except Exception as e:
            logger.warning(f"Error closing '{ex_name}': {e}")

    async def __aenter__(self) -> 'ExFactory':
        await self.create_exchanges()
        # await self.check_balances()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is asyncio.CancelledError:
            logger.info("👋 ExFactory: Корректное завершение по запросу отмены")
        elif exc_type:
            logger.error(f"❌ ExFactory: Непредвиденная ошибка", exc_info=True)
        else:
            logger.info("✅ ExFactory: Успешное завершение работы")
        
        await self.close()

    def __getitem__(self, ex_name: str) -> CcxtExchange:
        if ex_name not in self._exchanges:
            raise KeyError(f"Exchange '{ex_name}' not found or failed to connect.")
        return self._exchanges[ex_name]

    def __iter__(self) -> 'ExFactory':
        return self

    def __next__(self) -> CcxtExchange:
        raise NotImplementedError("Use .values() or iterate over .items() for exchanges.")

    def items(self) -> ItemsView[str, CcxtExchange]:
        return self._exchanges.items()

    def values(self) -> ValuesView[CcxtExchange]:
        return self._exchanges.values()

    def keys(self) -> KeysView[str]:
        return self._exchanges.keys()
    
    def get_exchange_obj_by_name(self, ex_name: str) -> Exchange | None:
        return self._exchanges.get(ex_name, None)

    @property
    def connected_exchanges(self) -> list[CcxtExchange]:
        return list(self._exchanges.values())

    @property
    def exchange_names(self) -> list[str]:
        return list(self._exchanges.keys())

    def __len__(self) -> int:
        return len(self._exchanges)

    def __contains__(self, ex_name: str) -> bool:
        return ex_name in self._exchanges