import asyncio
import ccxt
import ccxt.pro as ccxtpro
import logging
import importlib
import os
from typing import Any, Optional, Union, ItemsView, ValuesView, KeysView, Type

from core.interfaces import ExchangeConnectionError, ExFactory as ExFactoryInterface, Exchange
from core.models.dto.ExchangeParams import ExchangeParams
from core.models.types import EXCHANGE_NAME
# from infrastructure.CcxtExchange import CcxtExchange
from infrastructure.CCXT2 import CcxtExchange
from infrastructure.Connection import Connection
# from infrastructure.Exchenges.base_ccxt_exchange import CcxtExchange # Импортируем базовый класс

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)


class ExFactory(ExFactoryInterface):
    EXCHANGES_DIR = "infrastructure.Exchenges" # Путь к папке с реализациями

    def __init__(self, config: dict[EXCHANGE_NAME, ExchangeParams]):
        self._config = config
        self._exchanges: dict[str, CcxtExchange] = {}
        # self._validate_initial_config()
        logger.info("ExFactory initialized with provided configuration.")
    
    async def create_exchanges(self) -> None:
        logger.info("Attempting to create exchange connections...")
        tasks = [self._connect(ex_name, ex_config) for ex_name, ex_config in self._config.items()]
        results: list[Optional[ccxtpro.Exchange]] = await asyncio.gather(*tasks)

        for ex_name, exchange_instance in zip(self._config.keys(), results):
            if exchange_instance:
                ExchangeClass: Type[CcxtExchange] = self._get_exchange_class(ex_name)
                self._exchanges[ex_name] = ExchangeClass(ex_name, exchange_instance)
                logger.info(f"✓ Exchange '{ex_name}' successfully connected.")
            else:
                logger.warning(f"✗ Exchange '{ex_name}' failed to connect. Check logs.")

    def _get_exchange_class(self, ex_name: str) -> Type[CcxtExchange]:
        module_name = f"{self.EXCHANGES_DIR}.{ex_name.lower()}"
        class_name = f"{ex_name.capitalize()}Exchange"

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

        return CcxtExchange 
    
    
    
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

    def __getitem__(self, ex_name: str) -> CcxtExchange | None:
        if ex_name not in self._exchanges:
            if params := self._config.get(ex_name):
                inst = Connection(ex_name, params)
                self._exchanges[ex_name] = CcxtExchange(ex_name, inst)
        
        return self._exchanges.get(ex_name)

    def items(self) -> ItemsView[str, CcxtExchange]:
        return self._exchanges.items()

    def values(self) -> ValuesView[CcxtExchange]:
        return self._exchanges.values()

    def keys(self) -> KeysView[str]:
        return self._exchanges.keys()

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