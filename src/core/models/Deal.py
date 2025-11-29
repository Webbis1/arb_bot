from dataclasses import dataclass



from core.models.ExchangeBase import ExchangeBase
from core.models.types import COIN_ID, COIN_NAME, AMOUNT

@dataclass
class Deal:
    """
    Represent an arbitrage deal between two exchanges.
    Attributes:
        coin (Coin): The cryptocurrency or token involved in the deal.
        departure (Exchange): The exchange where the asset is sourced (bought or taken from).
        destination (Exchange): The exchange where the asset is sent or sold.
        benefit (float): Expected profit from executing the deal. Positive values indicate expected gain.
            The unit (absolute quote-currency amount or percentage) should be documented where the value
            is computed. This value should typically account for fees, estimated slippage, and transfer
            costs if available.
    Notes:
        - This class is a lightweight data container and does not execute trades or validate market
          conditions. Use a separate service/function to compute and verify benefit before acting.
        - When comparing deals, prefer those with higher net benefit after realistic costs and risks.
        - Consider including timestamps, liquidity, and confidence metrics externally if needed.
    Example:
        >>> Deal(coin=btc, departure=exchange_a, destination=exchange_b, benefit=12.5)
    """
    
    coin_id: COIN_ID
    departure: ExchangeBase
    destination: ExchangeBase
    benefit: float
    
    def __str__(self) -> str:
        return f"coin_id: {self.coin_id}, departure: {self.departure.name}, destination: {self.destination.name}, benefit: {self.benefit}"