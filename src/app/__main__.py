import asyncio
import logging

from infrastructure.CcxtExchangeModel import CcxtExchangModel
from infrastructure.Connection import Connection
from infrastructure.services.BalanceObserver import BalanceObserver
from infrastructure.services.PriceObserver import PriceObserver
from .logger import start_trading_monitor



# from infrastructure.services import BalanceObserver
from .config import api_keys as API




monitor = start_trading_monitor()
logger = logging.getLogger(__name__)


async def main():
    try:
        conn_tasks = []
        for ex_name, params in API.items():
            conn: Connection = Connection(ex_name, params)
            conn_tasks.append(conn.connection())
            
            model: CcxtExchangModel = CcxtExchangModel(ex_name, conn)
            
            balance_obs: BalanceObserver = BalanceObserver(model)
            
            price_obs: PriceObserver = PriceObserver(model)
            
            conn_tasks.append(balance_obs.launch())
            conn_tasks.append(price_obs.launch())
            
        if conn_tasks:
            await asyncio.gather(*conn_tasks, return_exceptions=True)


        
    except Exception as e:
        logger.error(f"Другая ошибка: {e}")
    finally:
        
        # Отменяем все задачи
        for worker in conn_tasks:
            worker.cancel()
        
        # Ждем завершения всех задач
        await asyncio.gather(*conn_tasks, return_exceptions=True)

if __name__ == "__main__":
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped manually.")
    finally: 
        monitor.stop()
        