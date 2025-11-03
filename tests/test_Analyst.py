import pytest
import asyncio
from core.services.Analytics.Analyst import Analyst

class DummyAnalyst(Analyst):
    async def start_analysis(self, exchange, coin) -> None:
        return None
    async def stop_analysis(self, exchange, coin) -> None:
        return None

@pytest.mark.asyncio
async def test_get_best_deal_returns_none_when_sorted_empty():
    exch = {"ex1": "ex1", "ex2": "ex2"}
    coins = {0: "BTC", 1: "ETH"}
    sell_comm = {
        "BTC": {"ex1": 0.01, "ex2": 0.02},
        "ETH": {"ex1": 0.01, "ex2": 0.02},
    }
    buy_comm = {
        "BTC": {"ex1": 0.01, "ex2": 0.02},
        "ETH": {"ex1": 0.01, "ex2": 0.02},
    }

    analyst = DummyAnalyst(exchenges=exch, _coin_pair=coins, sell_commissions=sell_comm, buy_commissions=buy_comm)
    # ensure sorted_coin is empty
    analyst.sorted_coin.clear()
    result = await analyst.get_best_deal()
    assert result is None

@pytest.mark.asyncio
async def test_get_best_deal_returns_highest_benefit_deal():
    exch = {"ex1": "ex1", "ex2": "ex2"}
    coins = {0: "BTC", 1: "ETH"}
    sell_comm = {
        "BTC": {"ex1": 0.01, "ex2": 0.02},
        "ETH": {"ex1": 0.01, "ex2": 0.02},
    }
    buy_comm = {
        "BTC": {"ex1": 0.01, "ex2": 0.02},
        "ETH": {"ex1": 0.01, "ex2": 0.02},
    }

    analyst = DummyAnalyst(exchenges=exch, _coin_pair=coins, sell_commissions=sell_comm, buy_commissions=buy_comm)
    # populate sorted_coin with two coins, BTC has higher benefit
    analyst.sorted_coin.clear()
    analyst.sorted_coin["ETH"] = ("ex2", "ex1", 0.1)
    analyst.sorted_coin["BTC"] = ("ex1", "ex2", 0.5)

    deal = await analyst.get_best_deal()
    assert deal is not None
    assert deal.coin == "BTC"
    assert deal.departure == "ex1"
    assert deal.destination == "ex2"
    assert deal.benefit == 0.5