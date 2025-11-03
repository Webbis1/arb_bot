import asyncio
import ccxt.pro as ccxtpro
import logging


from core.interfaces import ExchangeConnectionError
from core.interfaces import ExFactory as ExFactoryInterface

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ExFactory(ExFactoryInterface):
    def __init__(self, config: dict[str, dict]):
        self.exchanges: dict[str, ccxtpro.Exchange] = {}
        self.config = config
        self._validate_initial_config()
        logger.info("ExFactory initialized with provided configuration.")
        
    def _validate_initial_config(self):
        for ex_name, ex_config in self.config.items():
            if 'api_key' not in ex_config or 'api_secret' not in ex_config:
                logger.warning(
                    f"Configuration for exchange '{ex_name}' is missing 'api_key' or 'api_secret'. "
                    "This exchange might not connect properly."
                )
    
    async def create_exchanges(self) -> None:
        logger.info("Attempting to create exchange connections...")
        tasks = [self._connect(ex_name, self.config[ex_name]) for ex_name in self.config]
        
        results = await asyncio.gather(*tasks)
        
        for ex_name, exchange in zip(self.config.keys(), results):
            if exchange:
                self.exchanges[ex_name] = exchange
                logger.info(f"✓ Exchange '{ex_name}' successfully connected.")
            else:
                logger.warning(f"✗ Exchange '{ex_name}' failed to connect. See previous logs for details.")
    
    async def check_balances(self) -> None:
        logger.info("Checking USDT balances for all connected exchanges...")
        has_errors = False
        error_exchanges = []
        
        balance_check_tasks = [self._check_single_balance(ex_name, exchange) 
                               for ex_name, exchange in self.exchanges.items()]
        
        results = await asyncio.gather(*balance_check_tasks, return_exceptions=True)
        
        for ex_name, result in zip(self.exchanges.keys(), results):
            if isinstance(result, Exception):
                has_errors = True
                error_exchanges.append(ex_name)
                logger.error(f"✗ {ex_name}: error fetching balance - {result}", exc_info=True)
            else:
                usdt_balance = result
                if usdt_balance > 0:
                    logger.info(f"✓ {ex_name}: USDT balance = {usdt_balance:.4f}")
                else:
                    logger.info(f"✓ {ex_name}: No USDT balance detected (0.0)")
        
        if has_errors:  
            error_msg = f"Failed to fetch balances from exchanges: {', '.join(error_exchanges)}. Check logs for details."
            raise ExchangeConnectionError(error_msg)
        logger.info("USDT balance check completed.")

    async def _check_single_balance(self, ex_name: str, exchange: ccxtpro.Exchange) -> float:
        balance_data = await exchange.fetch_balance()
        usdt_balance = 0.0
        usdt_variants = ['USDT', 'usdt', 'Usdt', 'usd']
        
        for variant in usdt_variants:
            if variant in balance_data['total']:
                usdt_balance = float(balance_data['total'][variant])
                break
        return usdt_balance
        
    async def _connect(self, ex_name: str, ex_config: dict) -> ccxtpro.Exchange | None:
        logger.debug(f"Attempting to connect to '{ex_name}'...")
        try:
            if not hasattr(ccxtpro, ex_name):
                logger.error(f"Exchange '{ex_name}' is not supported in ccxt.pro.")
                return None
            
            if 'api_key' not in ex_config or 'api_secret' not in ex_config:
                logger.error(f"Missing required 'api_key' or 'api_secret' for exchange '{ex_name}'.")
                return None
            
            sandbox_mode = ex_config.get('sandbox', False) 

            exchange_params = {
                'apiKey': ex_config.get('api_key'),
                'secret': ex_config.get('api_secret'),
                'sandbox': sandbox_mode,
                'enableRateLimit': True,
                'timeout': 30000,
                'verify': False,  # Отключить проверку SSL
                # 'verbose': True,
            }
            
            optional_params = ['password', 'uid', 'privateKey', 'walletAddress', 'options']
            for param in optional_params:
                if param in ex_config and ex_config[param] is not None:
                    exchange_params[param] = ex_config[param]
            
            exchange_class = getattr(ccxtpro, ex_name)
            exchange = exchange_class(exchange_params)
            
            await exchange.load_markets()
            logger.debug(f"Successfully loaded markets for {ex_name}.")
            return exchange
            
        except ccxtpro.NetworkError as e:
            logger.error(f"✗ {ex_name}: Network error during connection - {e}", exc_info=True)
            return None
        except ccxtpro.AuthenticationError as e:
            logger.error(f"✗ {ex_name}: Authentication error (invalid API keys/secret/password) - {e}", exc_info=True)
            return None
        except ccxtpro.ExchangeError as e:
            logger.error(f"✗ {ex_name}: Exchange specific error - {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"✗ {ex_name}: An unexpected error occurred during connection - {e}", exc_info=True)
            return None
    
    def __getitem__(self, ex_name: str) -> ccxtpro.Exchange:
        if ex_name not in self.exchanges:
            raise KeyError(f"Exchange '{ex_name}' not found or failed to connect.")
        return self.exchanges[ex_name]
    
    async def close(self) -> None:
        logger.info("Closing all exchange connections...")
        if not self.exchanges:
            logger.info("No exchanges to close.")
            return

        tasks = [self._close_single_exchange(ex_name, exchange) 
                 for ex_name, exchange in list(self.exchanges.items())]
        await asyncio.gather(*tasks)
        self.exchanges.clear()
        logger.info("All exchange connections closed.")

    async def _close_single_exchange(self, ex_name: str, exchange: ccxtpro.Exchange):
        try:
            await exchange.close()
            logger.info(f"Exchange '{ex_name}' closed successfully.")
        except asyncio.CancelledError:
            # Это нормально - фоновые задачи KuCoin отменяются
            logger.debug(f"Exchange '{ex_name}': background tasks were cancelled")
        except Exception as e:
            logger.warning(f"Error closing exchange '{ex_name}': {e}")
    
    async def __aenter__(self):
        await self.create_exchanges()
        await self.check_balances() 
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"Exiting ExFactory due to an exception: {exc_val}", exc_info=(exc_type, exc_val, exc_tb))
        await self.close()
        
        
        
    def __iter__(self):
        """Итерация по экземплярам бирж (без имен)"""
        return iter(self.exchanges.values()) #ccxtpro.Exchange
    
    def items(self):
        """Итерация по парам (имя, экземпляр)"""
        return self.exchanges.items()
    
    def values(self):
        """Итерация только по экземплярам бирж"""
        return self.exchanges.values()
    
    def keys(self):
        """Итерация только по именам бирж"""
        return self.exchanges.keys()
    
    @property
    def connected_exchanges(self) -> list[ccxtpro.Exchange]:
        """Список всех подключенных бирж"""
        return list(self.exchanges.values())
    
    @property
    def exchange_names(self) -> list[str]:
        """Список имен всех подключенных бирж"""
        return list(self.exchanges.keys())
    
    def __len__(self):
        """Количество подключенных бирж"""
        return len(self.exchanges)
    
    def __contains__(self, ex_name: str):
        """Проверка наличия биржи"""
        return ex_name in self.exchanges