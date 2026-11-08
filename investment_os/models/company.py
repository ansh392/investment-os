from __future__ import annotations

from dataclasses import dataclass

from investment_os.models.valuation import valuation_multiples


@dataclass(frozen=True)
class CompanySnapshot:
    ticker: str
    market_cap: float
    debt: float
    cash: float
    ebitda: float
    fcf: float

    def metrics(self) -> dict[str, float]:
        return valuation_multiples(
            market_cap=self.market_cap,
            debt=self.debt,
            cash=self.cash,
            ebitda=self.ebitda,
            fcf=self.fcf,
        )
