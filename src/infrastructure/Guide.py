from dataclasses import dataclass
from typing import Dict
from .Types import Coin, Exchange

@dataclass
class Guide:
    sell_commission: Dict[Coin, Dict[Exchange, float]]
    buy_commission: Dict[Coin, Dict[Exchange, float]] 
    transfer_commission: Dict[Coin, Dict[Exchange, Dict[Exchange, float]]]
    transfer_time: Dict[Coin, Dict[Exchange, Dict[Exchange, float]]]

    def __str__(self):
        lines = ["Guide:"]
        
        # Sell Commission
        if self.sell_commission:
            lines.append("\nSell Commission:")
            for coin, exchanges in self.sell_commission.items():
                lines.append(f"  {coin}:")
                for exchange, commission in exchanges.items():
                    lines.append(f"    {exchange}: {commission:.4f}")
        else:
            lines.append("\nSell Commission: None")
        
        # Buy Commission
        if self.buy_commission:
            lines.append("\nBuy Commission:")
            for coin, exchanges in self.buy_commission.items():
                lines.append(f"  {coin}:")
                for exchange, commission in exchanges.items():
                    lines.append(f"    {exchange}: {commission:.4f}")
        else:
            lines.append("\nBuy Commission: None")
        
        # Transfer Commission
        if self.transfer_commission:
            lines.append("\nTransfer Commission:")
            for coin, exchanges in self.transfer_commission.items():
                lines.append(f"  {coin}:")
                for from_exchange, to_exchanges in exchanges.items():
                    lines.append(f"    From {from_exchange}:")
                    for to_exchange, commission in to_exchanges.items():
                        lines.append(f"      To {to_exchange}: {commission:.4f}")
        else:
            lines.append("\nTransfer Commission: None")
        
        # Transfer Time
        if self.transfer_time:
            lines.append("\nTransfer Time:")
            for coin, exchanges in self.transfer_time.items():
                lines.append(f"  {coin}:")
                for from_exchange, to_exchanges in exchanges.items():
                    lines.append(f"    From {from_exchange}:")
                    for to_exchange, time in to_exchanges.items():
                        lines.append(f"      To {to_exchange}: {time:.2f}")
        else:
            lines.append("\nTransfer Time: None")
        
        return "\n".join(lines)