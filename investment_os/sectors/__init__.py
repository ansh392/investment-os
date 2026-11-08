"""Sector plug-ins: extra diligence and non-XBRL KPIs a specific industry requires.

The platform is sector-agnostic. A plug-in only adds questions; it never supplies
numbers, because these KPIs are not available from standardized filings data.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectorPlugin:
    name: str
    sic_ranges: tuple[tuple[int, int], ...]
    kpis: tuple[str, ...]
    diligence: tuple[str, ...]
    catalysts: tuple[str, ...]


GENERIC = SectorPlugin(
    "General",
    (),
    ("Segment revenue and margin", "Customer concentration", "Pricing versus volume mix"),
    ("What is the competitive response if returns stay above the cost of capital?",
     "How much of recent growth is price rather than volume?"),
    ("Next periodic filing and earnings call", "Capital-allocation announcement"),
)

SECTORS: tuple[SectorPlugin, ...] = (
    SectorPlugin(
        "Energy & Power",
        ((1300, 1389), (2900, 2999), (4900, 4939)),
        ("Realized power or commodity price versus benchmark", "Hedged share of next-24-month generation",
         "Capacity auction clearing prices", "Fleet availability and heat rate", "Contracted data-center load (MW, term, price)"),
        ("What portion of forward earnings is hedged, and at what prices?",
         "How much of the operating-income swing is unrealized mark-to-market on hedges?",
         "Which new load contracts are signed versus announced as intentions?",
         "What are nuclear relicensing and plant retirement obligations?"),
        ("Capacity auction results", "New long-term power contract announcement", "Forward power curve move", "Regulatory ruling on co-located load"),
    ),
    SectorPlugin(
        "Semiconductors",
        ((3670, 3679),),
        ("Book-to-bill", "Customer concentration in hyperscalers", "Inventory days across the channel", "Foundry capacity commitments"),
        ("How much demand is double-ordering?", "What are export-control exposures by product?",
         "What share of purchase obligations is non-cancellable?"),
        ("Hyperscaler capex guidance", "Export-control rule change", "Next product-cycle ramp"),
    ),
    SectorPlugin(
        "Consumer & Retail",
        ((2000, 2399), (5200, 5999)),
        ("Same-store sales", "Traffic versus ticket", "Inventory turns", "Private-label penetration"),
        ("Is comparable growth driven by traffic or price?", "How exposed are margins to tariffs and freight?",
         "What is the store-level return on new units?"),
        ("Monthly retail sales data", "Holiday-quarter comparable sales", "Tariff decision"),
    ),
)


def plugin_for_sic(sic: str | int | None) -> SectorPlugin:
    try:
        code = int(sic)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return GENERIC
    for plugin in SECTORS:
        if any(low <= code <= high for low, high in plugin.sic_ranges):
            return plugin
    return GENERIC
