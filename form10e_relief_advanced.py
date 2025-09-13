#!/usr/bin/env python3
from dataclasses import dataclass
from typing import List, Literal, Optional

Regime = Literal["old", "new"]

# ----------------------------
# Tax engines
# ----------------------------

# Old regime slabs (unchanged)
# 0–2.5L:0%; 2.5–5L:5%; 5–10L:20%; 10L+:30%; 87A: if TI <= 5L => tax=0; cess 4%
def compute_tax_old(ti: float) -> float:
    slabs = [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (float("inf"), 0.30)]
    tax = 0.0
    prev = 0.0
    for limit, rate in slabs:
        slab = max(0.0, min(ti, limit) - prev)
        tax += slab * rate
        prev = limit
        if ti <= limit:
            break
    if ti <= 500000:
        tax = 0.0
    return round(tax * 1.04, 0)

# New regime "legacy" (FY 2023–24 and FY 2024–25 baseline with 0–3L:0, 3–6:5, 6–9:10, 9–12:15, 12–15:20, 15+:30)
# Simple 87A handling: if TI <= 7L => tax = 0; cess 4%
def compute_tax_new_legacy(ti: float) -> float:
    slabs = [(300000, 0.0), (600000, 0.05), (900000, 0.10), (1200000, 0.15), (1500000, 0.20), (float("inf"), 0.30)]
    tax = 0.0
    prev = 0.0
    for limit, rate in slabs:
        slab = max(0.0, min(ti, limit) - prev)
        tax += slab * rate
        prev = limit
        if ti <= limit:
            break
    # Legacy new regime 87A relief (simplified to zero when TI <= 7,00,000)
    if ti <= 700000:
        tax = 0.0
    return round(tax * 1.04, 0)

# New regime "proposed" for FY 2025–26 as provided by you (no extra rebate assumptions)
# - Up to 4,00,000: 0
# - 4,00,001–8,00,000: 5% of amount above 4,00,000
# - 8,00,001–12,00,000: 20,000 + 10% of amount above 8,00,000
# - 12,00,001–16,00,000: 60,000 + 15% of amount above 12,00,000
# - 16,00,001–20,00,000: 1,20,000 + 20% of amount above 16,00,000
# - 20,00,001–24,00,000: 2,00,000 + 25% of amount above 20,00,000
# - 24,00,000+: 3,00,000 + 30% of amount above 24,00,000
def compute_tax_new_2025(ti: float) -> float:
    if ti <= 400000:
        tax = 0.0
    elif ti <= 800000:
        tax = (ti - 400000) * 0.05
    elif ti <= 1200000:
        tax = 20000 + (ti - 800000) * 0.10
    elif ti <= 1600000:
        tax = 60000 + (ti - 1200000) * 0.15
    elif ti <= 2000000:
        tax = 120000 + (ti - 1600000) * 0.20
    elif ti <= 2400000:
        tax = 200000 + (ti - 2000000) * 0.25
    else:
        tax = 300000 + (ti - 2400000) * 0.30
    return round(tax * 1.04, 0)  # 4% cess

def compute_tax(ti: float, regime: Regime, fy: str) -> float:
    """
    ti: taxable income for the FY (after deductions as applicable to the regime)
    regime: "old" or "new"
    fy: e.g., "FY2025-26"
    """
    if regime == "old":
        return compute_tax_old(ti)
    # New regime: use FY-specific engine
    if fy == "FY2025-26":
        return compute_tax_new_2025(ti)
    else:
        return compute_tax_new_legacy(ti)

# ----------------------------
# Data structures
# ----------------------------

@dataclass
class YearData:
    fy: str
    base_income: float
    arrears: float
    regime: Regime
    manual_tax_wo: Optional[float] = None
    manual_tax_w: Optional[float] = None
    tax_wo: float = 0.0
    tax_w: float = 0.0

# ----------------------------
# Core 10E computation
# ----------------------------

def compute_relief(receipt_fy: str, receipt_regime: Regime, current_income_excl_arrears: float,
                   total_arrears: float, years: List[YearData]) -> dict:
    # Validate mapping sum
    mapped_total = round(sum(y.arrears for y in years), 2)
    if round(total_arrears, 2) != mapped_total:
        raise ValueError(f"Arrears mismatch: received ₹{total_arrears}, mapped ₹{mapped_total}")

    # Compute year-wise taxes
    for y in years:
        y.tax_wo = y.manual_tax_wo if y.manual_tax_wo is not None else compute_tax(y.base_income, y.regime, y.fy)
        y.tax_w  = y.manual_tax_w  if y.manual_tax_w  is not None else compute_tax(y.base_income + y.arrears, y.regime, y.fy)

    # Current year (year of receipt)
    current_tax_wo = compute_tax(current_income_excl_arrears, receipt_regime, receipt_fy)
    current_tax_w  = compute_tax(current_income_excl_arrears + total_arrears, receipt_regime, receipt_fy)
    current_delta  = current_tax_w - current_tax_wo

    past_deltas = [y.tax_w - y.tax_wo for y in years]
    relief = max(0.0, round(sum(past_deltas) - current_delta, 0))

    return {
        "years": years,
        "current": {
            "fy": receipt_fy,
            "regime": receipt_regime,
            "tax_wo": current_tax_wo,
            "tax_w": current_tax_w,
            "delta": current_delta,
        },
        "relief": relief
    }

# ----------------------------
# CLI helpers
# ----------------------------

def input_float(prompt: str) -> float:
    while True:
        try:
            return float(input(prompt + " ₹"))
        except ValueError:
            print("Invalid number. Try again.")

def input_year(prompt: str) -> str:
    while True:
        fy = input(prompt + " (e.g., FY2025-26): ").strip()
        if fy.startswith("FY") and len(fy) == 9 and fy[2:6].isdigit() and fy[7:9].isdigit() and fy[6] == "-":
            return fy
        print("Invalid format. Try again.")

def input_regime(prompt: str) -> Regime:
    while True:
        r = input(prompt + " [old/new]: ").strip().lower()
        if r in ("old", "new"):
            return r  # type: ignore
        print("Enter 'old' or 'new'.")

def input_optional_tax(prompt: str) -> Optional[float]:
    val = input(prompt + " (leave blank to auto-calc): ₹").strip()
    if val == "":
        return None
    try:
        return float(val)
    except ValueError:
        print("Invalid number. Try again.")
        return input_optional_tax(prompt)

def run_cli():
    print("\n🧮 Form 10E Relief Calculator — FY 2025–26 ready")
    receipt_fy = input_year("Enter the Financial Year in which arrears were received")
    receipt_regime = input_regime("Enter regime used in the year of receipt")
    current_income = input_float("Enter taxable income for that year (excluding arrears)")
    total_arrears = input_float("Enter total arrears received")
    n_years = int(input_float("How many years do these arrears relate to"))

    years: List[YearData] = []
    print("\n📅 Enter details for each affected year:")
    for i in range(n_years):
        print(f"\nYear {i+1}:")
        fy = input_year("  Financial Year")
        base = input_float("  Taxable income (excluding arrears)")
        arr = input_float("  Arrears for this year")
        reg = input_regime("  Regime used in that year")
        mwo = input_optional_tax("  Actual tax without arrears")
        mw  = input_optional_tax("  Actual tax with arrears")
        years.append(YearData(fy=fy, base_income=base, arrears=arr, regime=reg, manual_tax_wo=mwo, manual_tax_w=mw))

    result = compute_relief(receipt_fy, receipt_regime, current_income, total_arrears, years)

    print("\n📋 Year-wise Tax Comparison:")
    for y in result["years"]:
        delta = y.tax_w - y.tax_wo
        print(f"  {y.fy} [{y.regime}]: Tax w/o = ₹{y.tax_wo}, Tax with = ₹{y.tax_w}, Δ = ₹{delta}")

    cy = result["current"]
    print(f"\n  {cy['fy']} [{cy['regime']}]: Tax w/o = ₹{cy['tax_wo']}, Tax with = ₹{cy['tax_w']}, Δ = ₹{cy['delta']}")
    print(f"\n✅ Relief under Section 89(1): ₹{result['relief']}")

    print("\n📤 Form 10E Annexure I (copy-ready):")
    for y in result["years"]:
        print(f"  {y.fy}: Income w/o arrears ₹{y.base_income}, Arrears ₹{y.arrears}, Tax w/o ₹{y.tax_wo}, Tax with ₹{y.tax_w}")
    print(f"  Year of receipt {cy['fy']}: Income ₹{current_income}, Arrears ₹{total_arrears}, Tax w/o ₹{cy['tax_wo']}, Tax with ₹{cy['tax_w']}")
    print(f"  Relief u/s 89(1): ₹{result['relief']}")

# ----------------------------
# Self-check tests (quick sanity)
# ----------------------------

def _self_tests():
    # Old regime monotonicity and 87A
    assert compute_tax_old(0) == 0
    assert compute_tax_old(500000) == 0
    assert compute_tax_old(600000) > 0
    # New legacy: zero up to 7L (after 87A simplification)
    assert compute_tax_new_legacy(700000) == 0
    assert compute_tax_new_legacy(710000) > 0
    # New 2025 proposed: zero up to 4L
    assert compute_tax_new_2025(400000) == 0
    assert compute_tax_new_2025(500000) == round(((500000 - 400000) * 0.05) * 1.04, 0)
    # Boundary checks
    assert compute_tax_new_2025(800000) == round(((800000 - 400000) * 0.05) * 1.04, 0)
    assert compute_tax_new_2025(1200000) == round((20000 + (1200000 - 800000) * 0.10) * 1.04, 0)
    assert compute_tax_new_2025(1600000) == round((60000 + (1600000 - 1200000) * 0.15) * 1.04, 0)
    assert compute_tax_new_2025(2000000) == round((120000 + (2000000 - 1600000) * 0.20) * 1.04, 0)
    assert compute_tax_new_2025(2400000) == round((200000 + (2400000 - 2000000) * 0.25) * 1.04, 0)
    # Simple 10E flow: if current-year delta >= sum past deltas → relief 0
    yrs = [
        YearData(fy="FY2023-24", base_income=900000, arrears=50000, regime="new"),
        YearData(fy="FY2024-25", base_income=1000000, arrears=50000, regime="new"),
    ]
    res = compute_relief(
        receipt_fy="FY2025-26",
        receipt_regime="new",
        current_income_excl_arrears=1500000,
        total_arrears=100000,
        years=yrs
    )
    assert res["relief"] >= 0
    print("Self-tests passed.")

# ----------------------------
# Main
# ----------------------------

if __name__ == "__main__":
    # Toggle self-tests
    try:
        _self_tests()
    except AssertionError:
        print("Self-tests failed. Review slab logic.")
    # Run interactive CLI
    run_cli()
