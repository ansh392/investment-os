"""Source-linked IC memo: Markdown and self-contained HTML, with citation validation."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from investment_os.core.evidence import EvidenceKind, EvidenceLedger
from investment_os.pipeline import ResearchBundle
from investment_os.research.thesis_lab import ThesisReport, contradictory_findings
from investment_os.research.workflow import ValuationPackage

CITATION = re.compile(r"\[([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)\]")
JUDGMENT = "[Judgment]"
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?\]])\s+(?=[A-Z])")
LONG_THRESHOLD, SHORT_THRESHOLD = 0.20, -0.20
MATERIAL_PEER_GAP = 0.10
LEDGER_HEADING = "## Evidence Ledger"
MEMO_SCOPE_NOTE = (
    "> Automated research output for analysis of a process, not investment advice. "
    "Default assumptions are mechanical placeholders until an analyst overrides them."
)


@dataclass(frozen=True)
class CitationReport:
    uncited: list[str]
    unknown_ids: list[str]
    citations_checked: int

    @property
    def ok(self) -> bool:
        return not self.uncited and not self.unknown_ids


def _claims_in(markdown: str) -> list[str]:
    """Sentences and table rows subject to the citation rule."""
    body = markdown.split(LEDGER_HEADING)[0]
    out: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ">")) or re.fullmatch(r"\|?[\s:|-]+\|?", line):
            continue
        if line.startswith("|"):
            if not line.startswith("| Line") and not line.startswith("| Item") and not line.startswith("| Scenario"):
                out.append(line)
            continue
        text = re.sub(r"^(?:[-*]|\d+\.)\s+", "", line)
        out.extend(s for s in _SENTENCE_SPLIT.split(text) if s.strip())
    return out


def validate_citations(markdown: str, ledger: EvidenceLedger) -> CitationReport:
    """Each claim must cite known evidence ids or be explicitly labeled as judgment."""
    uncited, unknown, checked = [], [], 0
    for claim in _claims_in(markdown):
        ids = CITATION.findall(claim.replace(JUDGMENT, ""))
        checked += len(ids)
        unknown.extend(i for i in ids if i not in ledger)
        if not ids and JUDGMENT not in claim:
            uncited.append(claim)
    return CitationReport(uncited, sorted(set(unknown)), checked)


def _peer_upside(valuation: ValuationPackage) -> float | None:
    """Peer-median EV/EBITDA value versus price, if a usable comparison exists."""
    if valuation.comps_implied.empty or "M.price" not in valuation.ledger:
        return None
    rows = valuation.comps_implied.dropna(subset=["implied_price"])
    rows = rows[rows["method"] == "ev_ebitda"]
    return None if rows.empty else float(rows["implied_price"].iloc[0]) / valuation.ledger.get("M.price").value - 1


def recommendation_for(valuation: ValuationPackage | None, report: ThesisReport) -> tuple[str, str]:
    """Mechanical rating; (label, rationale). It is a screen, not a decision."""
    if valuation is None or valuation.upside is None:
        return "NO RATING: VALUATION NOT APPLICABLE", "The valuation model could not be applied with the available data."
    upside = valuation.upside
    contradicted = report.status_counts()["contradicted"]
    peer_upside = _peer_upside(valuation)
    if peer_upside is not None and peer_upside * upside < 0 and abs(upside) >= LONG_THRESHOLD and abs(peer_upside) >= MATERIAL_PEER_GAP:
        return "WATCH: DCF AND PEER MULTIPLES CONFLICT", (
            f"Rule-based rating: probability-weighted DCF versus price is {upside:+.0%}, while peer-median EV/EBITDA implies {peer_upside:+.0%}. "
            "The methods disagree in direction, so no directional rating is issued until the assumptions are replaced with company-specific estimates."
        )
    if upside >= LONG_THRESHOLD and contradicted <= 1:
        label = "LONG CANDIDATE, SUBJECT TO DILIGENCE"
    elif upside <= SHORT_THRESHOLD:
        label = "AVOID / SHORT CANDIDATE, SUBJECT TO DILIGENCE"
    else:
        label = "WATCH"
    return label, (
        f"Rule-based rating: probability-weighted DCF versus price is {upside:+.0%} "
        f"with thresholds of {LONG_THRESHOLD:+.0%} and {SHORT_THRESHOLD:+.0%}, and {contradicted} thesis claim(s) contradicted."
    )


def _money(value: float) -> str:
    return f"${value / 1e9:,.1f}B"


def _bullets(items: list[str]) -> list[str]:
    return [f"- {i}" for i in items] or ["- None identified. [Judgment]"]


def _judged(text: str) -> str:
    """Label every sentence, so that a multi-sentence note cannot carry an unlabeled claim."""
    return " ".join(f"{part.strip().rstrip('.')}. {JUDGMENT}" for part in _SENTENCE_SPLIT.split(text.strip()) if part.strip())


def build_memo(bundle: ResearchBundle, valuation: ValuationPackage | None, report: ThesisReport) -> str:
    ledger = valuation.ledger if valuation else bundle.ledger
    label, rationale = recommendation_for(valuation, report)
    m = bundle.market
    lines = [
        f"# Investment Committee Memo: {bundle.name} ({bundle.ticker})", "",
        f"> Data retrieved {bundle.retrieved_at}. Sector module: {report.sector}. CIK {bundle.cik}.",
        MEMO_SCOPE_NOTE, "",
        "## Recommendation", "", f"**{label}** {JUDGMENT}", "", _judged(rationale), "",
        "## Thesis", "", _judged(f"Hypothesis under test: {report.hypothesis}"), "",
    ]
    counts = report.status_counts()
    lines += [_judged(f"Claim status across {len(report.claims)} tests: {counts['supported']} supported, {counts['mixed']} mixed, {counts['contradicted']} contradicted, {counts['inconclusive']} inconclusive"), ""]
    for c in report.claims:
        lines += [f"### {c.id}. {c.statement}", "", f"Status: **{c.status}**. {JUDGMENT}", ""]
        lines += [f"- Supporting: {f.text}. {f.citation}" for f in c.supporting]
        lines += [f"- Contradicting: {f.text}. {f.citation}" for f in c.contradicting]
        lines += [""]

    lines += ["## Variant Perception", ""]
    if report.priced_in:
        lines += [f"- {f.text}. {f.citation}" for f in report.priced_in]
        lines += ["", _judged("The variant view exists only where sourced operating evidence differs from these market-implied requirements"), ""]
    else:
        lines += [_judged("Market-implied expectations could not be computed, so no variant view can be stated"), ""]

    lines += ["## Valuation", ""]
    if valuation:
        if m.get("market_cap") and "D.enterprise_value" in ledger:
            lines += [f"Market capitalization is {_money(m['market_cap'])} [D.market_cap] and enterprise value is {_money(m['enterprise_value'])} [D.enterprise_value], at a share price of ${m['price']:,.2f} [M.price].", ""]
        lines += [
            "| Scenario | Probability | Value per share | Terminal share of EV | Evidence |", "|---|---|---|---|---|",
            *[f"| {r.name.title()} | {r.assumptions.probability:.0%} | ${r.implied_price:,.2f} | {r.terminal_share:.0%} | [D.value.{r.name}] [A.scenario.{r.name}] |" for r in valuation.results.values()],
            f"| Weighted | 100% | ${valuation.weighted_price:,.2f} | n/a | [D.value.weighted] |", "",
        ]
        base = valuation.results["base"].bridge
        lines += [
            "### Base-case bridge from assumptions to free cash flow (USD billions)", "",
            "| Line | " + " | ".join(f"Y{int(y)}" for y in base["year"]) + " |", "|---|" + "---|" * len(base),
        ]
        cited = {"revenue": "A.growth_anchor", "ebit": "A.ebit_margin", "taxes": "A.tax_rate", "nopat": "A.tax_rate", "dna": "A.dna_pct", "capex": "A.capex_pct", "delta_nwc": "A.nwc_pct", "fcff": "D.value.base"}
        lines += [f"| {k} [{e}] | " + " | ".join(f"{v / 1e9:,.2f}" for v in base[k]) + " |" for k, e in cited.items()]
        lines += [""]
        if not valuation.comps_implied.empty:
            rows = valuation.comps_implied.dropna(subset=["implied_price"])
            lines += [f"- Peer-median {r.method} of {r.peer_median:.1f}x implies ${r.implied_price:,.2f} per share. [D.comps.{r.method}]" for r in rows.itertuples()]
            lines += [""]
    else:
        lines += [_judged("Valuation is not applicable with the available data"), ""]

    lines += ["## Catalysts", "", *_bullets([_judged(c) for c in report.catalysts]), ""]

    lines += ["## Bear Case", ""]
    contra = contradictory_findings(report)
    lines += [f"- ({cid}) {f.text}. {f.citation}" for cid, f in contra] or [_judged("No contradictory evidence surfaced among the tested metrics, which reflects limited test coverage rather than absence of risk")]
    if valuation:
        bear = valuation.results["bear"]
        lines += [f"- The bear scenario values the shares at ${bear.implied_price:,.2f}. [D.value.bear]"]
    lines += [""]

    lines += ["## Risks", "", *_bullets([_judged(r) for r in (*report.limitations, *bundle.warnings[:8], *(valuation.warnings if valuation else []))]), ""]
    lines += ["## Falsification Conditions", "", *_bullets([_judged(f"{c.id}: {t}") for c in report.claims for t in c.falsified_if]), ""]
    lines += ["## Unanswered Diligence", "", *_bullets([_judged(d) for d in report.diligence]), ""]

    lines += ["## Model Assumptions Appendix", ""]
    assumptions = ledger.by_kind(EvidenceKind.ASSUMED)
    if assumptions:
        lines += ["| Item | Value | Basis | Evidence |", "|---|---|---|---|"]
        lines += [f"| {a.claim} | {a.value} | {a.notes.replace('|', '/')} | [{a.id}] |" for a in assumptions]
    else:
        lines += [_judged("No model assumptions were used")]
    lines += ["", LEDGER_HEADING, "", ledger.markdown(), ""]
    return "\n".join(lines)


_CSS = """
:root{--ink:#1a2233;--muted:#5d6b82;--line:#dfe4ec;--bg:#fff;--accent:#1f4e8c;--panel:#f6f8fb}
@media (prefers-color-scheme:dark){:root{--ink:#e7ebf2;--muted:#9aa7bb;--line:#2c3545;--bg:#10151e;--accent:#8ab4ee;--panel:#181f2b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 Georgia,'Times New Roman',serif}
main{max-width:920px;margin:0 auto;padding:40px 24px 80px}
h1,h2,h3{font-family:system-ui,'Segoe UI',sans-serif;line-height:1.25}h1{font-size:28px}
h2{font-size:19px;margin-top:40px;padding-bottom:6px;border-bottom:2px solid var(--ink)}h3{font-size:15px;margin-top:24px}
blockquote{margin:0 0 8px;padding:6px 12px;background:var(--panel);color:var(--muted);font:13px system-ui,sans-serif}
.tbl{overflow-x:auto}table{border-collapse:collapse;width:100%;font:13px system-ui,sans-serif;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--muted)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}.cite{font:11px system-ui,sans-serif;white-space:nowrap}
.j{font:11px system-ui,sans-serif;color:var(--muted);font-style:italic}.k{font-weight:600;text-transform:uppercase;font-size:11px}
tr:target{background:var(--panel)}
"""


def _inline(text: str) -> str:
    out = html.escape(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = out.replace(JUDGMENT, '<span class="j">[Judgment]</span>')
    return CITATION.sub(lambda m: f'<a class="cite" href="#{html.escape(m.group(1))}">[{html.escape(m.group(1))}]</a>', out)


def _ledger_table(ledger: EvidenceLedger) -> str:
    rows = []
    for item in ledger.items():
        value = f"{item.value:,.4g}" if isinstance(item.value, float) and abs(item.value) < 1000 else (f"{item.value:,.0f}" if isinstance(item.value, float) else str(item.value))
        link = f'<a href="{html.escape(item.source)}" rel="noopener">{html.escape(item.form or "source")}</a>' if item.source.startswith("http") else html.escape(item.source)
        inputs = " ".join(f'<a class="cite" href="#{html.escape(i)}">[{html.escape(i)}]</a>' for i in item.inputs)
        rows.append(
            f'<tr id="{html.escape(item.id)}"><td>{html.escape(item.id)}</td><td class="k">{item.kind.value}</td>'
            f"<td>{html.escape(item.claim)}</td><td>{html.escape(value)} {html.escape(item.unit)}</td>"
            f"<td>{html.escape(item.period)}</td><td>{link} {inputs}</td><td>{html.escape(item.retrieved_at)}</td></tr>"
        )
    return (
        '<div class="tbl"><table><thead><tr><th>ID</th><th>Type</th><th>Claim</th><th>Value</th><th>Period</th><th>Source / inputs</th><th>Retrieved</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table></div>"
    )


def memo_to_html(markdown: str, ledger: EvidenceLedger, *, title: str = "IC Memo", force_light: bool = False) -> str:
    """Render the memo; citations link to the ledger, and the ledger links to filings."""
    body = markdown.split(LEDGER_HEADING)[0]
    parts: list[str] = []
    table: list[str] = []
    bullets: list[str] = []

    def flush() -> None:
        nonlocal table, bullets
        if bullets:
            parts.append("<ul>" + "".join(f"<li>{_inline(b)}</li>" for b in bullets) + "</ul>")
            bullets = []
        if table:
            head, *rest = [[c.strip() for c in row.strip().strip("|").split("|")] for row in table if not re.fullmatch(r"\|[\s:|-]+\|?", row.strip())]
            parts.append(
                '<div class="tbl"><table><thead><tr>' + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rest) + "</tbody></table></div>"
            )
            table = []

    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith("|"):
            table.append(line)
            continue
        if line.startswith("- "):
            bullets.append(line[2:])
            continue
        flush()
        if not line:
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            parts.append(f"<h{level}>{_inline(line[level:].strip())}</h{level}>")
        elif line.startswith(">"):
            parts.append(f"<blockquote>{_inline(line[1:].strip())}</blockquote>")
        else:
            parts.append(f"<p>{_inline(line)}</p>")
    flush()
    parts += ["<h2>Evidence Ledger</h2>", _ledger_table(ledger)]
    css = re.sub(r"@media \(prefers-color-scheme:dark\)\{.*?\}\}\n", "", _CSS, flags=re.S) if force_light else _CSS
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{css}</style></head><body><main>{''.join(parts)}</main></body></html>"
    )


def export_memo(bundle: ResearchBundle, valuation: ValuationPackage | None, report: ThesisReport, output_dir: Path) -> tuple[Path, Path, CitationReport]:
    """Write memo.md and memo.html; refuses to export a memo that fails validation."""
    ledger = valuation.ledger if valuation else bundle.ledger
    markdown = build_memo(bundle, valuation, report)
    check = validate_citations(markdown, ledger)
    if not check.ok:
        raise ValueError(f"Memo failed citation validation: uncited={check.uncited[:3]} unknown={check.unknown_ids[:5]}")
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path, html_path = output_dir / "memo.md", output_dir / "memo.html"
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(memo_to_html(markdown, ledger, title=f"{bundle.ticker} IC Memo"), encoding="utf-8")
    return md_path, html_path, check
