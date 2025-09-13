#!/usr/bin/env python
# coding: utf-8

# In[1]:


#!/usr/bin/env python3
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal

Year = str  # e.g., "FY2021-22" for FY 2021-22 (AY 2022-23)
Mode = Literal["manual-tax", "slab-mode"]

# --- Slab tables (OLD regime) for common years (basic; surcharge not applied) ---
# Amounts in INR. These cover many salaried cases; for high incomes needing surcharge,
# use manual-tax mode or extend surcharge logic as needed.
SLABS_OLD = {
    "FY2019-20": [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (float("inf"), 0.30)],
    "FY2020-21": [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (float("inf"), 0.30)],
    "FY2021-22": [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (float("inf"), 0.30)],
    "FY2022-23": [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (float("inf"), 0.30)],
    "FY2023-24": [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (float("inf"), 0.30)],
    "FY2024-25": [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (float("inf"), 0.30)],
}

REBATE_87A = {
    # Simplified 87A rules (old regime focus). Adjust if using new regime years.
    "FY2019-20": (500000, True),  # rebate up to 12,500 if TI <= 5L
    "FY2020-21": (500000, True),
    "FY2021-22": (500000, True),
    "FY2022-23": (500000, True),
    "FY2023-24": (500000, True),
    "FY2024-25": (500000, True),
}

def tax_old_regime(ti: float, fy: Year) -> float:
    """
    Basic slab-only tax with 4% cess; ignores surcharge and special-rate incomes.
    'ti' should be taxable income after chapter VI-A etc.
    """
    slabs = SLABS_OLD.get(fy)
    if not slabs:
        raise ValueError(f"No slabs for {fy}. Use manual-tax mode or add slabs.")
    tax = 0.0
    prev = 0.0
    for limit, rate in slabs:
        slab_amt = max(0.0, min(ti, limit) - prev)
        tax += slab_amt * rate
        prev = limit
        if ti <= limit:
            break
    # 87A rebate (simplified)
    rebate_rule = REBATE_87A.get(fy)
    if rebate_rule and ti <= rebate_rule[0]:
        tax = 0.0
    cess = tax * 0.04
    return round(tax + cess, 0)

@dataclass
class YearInput:
    fy: Year
    base_taxable_without_arrears: float  # your taxable income for that FY (excl arrears)
    arrears_for_this_year: float         # part of arrears attributable to this FY
    manual_tax_without_arrears: Optional[float] = None  # if known from records
    manual_tax_with_arrears: Optional[float] = None

@dataclass
class TenEInput:
    receipt_fy: Year                          # FY in which arrears were received
    current_year_base_taxable_excl_arrears: float
    arrears_total_received: float
    affected_years: List[YearInput]           # each past FY the arrears belong to
    mode: Mode = "slab-mode"                  # "manual-tax" preferred for precision

@dataclass
class YearCalc:
    fy: Year
    tax_without_arrears: float
    tax_with_arrears: float
    delta: float

@dataclass
class TenEResult:
    past_years: List[YearCalc] = field(default_factory=list)
    current_year: YearCalc = None
    relief: float = 0.0

def compute_tax_for_year(fy: Year, taxable: float, mode: Mode,
                         manual_override: Optional[float]) -> float:
    if mode == "manual-tax" and manual_override is not None:
        return float(manual_override)
    return tax_old_regime(taxable, fy)

def compute_10e(data: TenEInput) -> TenEResult:
    # Validate mapping sum
    mapped = round(sum(y.arrears_for_this_year for y in data.affected_years), 2)
    if round(data.arrears_total_received, 2) != mapped:
        raise ValueError(f"Arrears mapping mismatch: received={data.arrears_total_received}, mapped={mapped}")

    past_deltas: List[YearCalc] = []
    for y in data.affected_years:
        tax_wo = compute_tax_for_year(
            y.fy,
            y.base_taxable_without_arrears,
            data.mode,
            y.manual_tax_without_arrears
        )
        tax_w = compute_tax_for_year(
            y.fy,
            y.base_taxable_without_arrears + y.arrears_for_this_year,
            data.mode,
            y.manual_tax_with_arrears
        )
        past_deltas.append(YearCalc(fy=y.fy, tax_without_arrears=tax_wo, tax_with_arrears=tax_w, delta=tax_w - tax_wo))

    # Current year deltas
    cy_tax_wo = compute_tax_for_year(
        data.receipt_fy,
        data.current_year_base_taxable_excl_arrears,
        data.mode,
        None  # manual override can be added if needed
    )
    cy_tax_w = compute_tax_for_year(
        data.receipt_fy,
        data.current_year_base_taxable_excl_arrears + data.arrears_total_received,
        data.mode,
        None
    )
    cy_calc = YearCalc(fy=data.receipt_fy, tax_without_arrears=cy_tax_wo, tax_with_arrears=cy_tax_w, delta=cy_tax_w - cy_tax_wo)

    # Relief per Rule 21A method: sum(past deltas) - current delta
    past_sum = sum(p.delta for p in past_deltas)
    relief = max(0.0, round(past_sum - cy_calc.delta, 0))

    return TenEResult(past_years=past_deltas, current_year=cy_calc, relief=relief)

if __name__ == "__main__":
    # Minimal demo
    demo = TenEInput(
        receipt_fy="FY2024-25",
        current_year_base_taxable_excl_arrears=900000,
        arrears_total_received=120000,
        affected_years=[
            YearInput(fy="FY2021-22", base_taxable_without_arrears=700000, arrears_for_this_year=70000),
            YearInput(fy="FY2022-23", base_taxable_without_arrears=650000, arrears_for_this_year=50000),
        ],
        mode="slab-mode"
    )
    result = compute_10e(demo)
    print("Past years:")
    for r in result.past_years:
        print(r)
    print("Current year:", result.current_year)
    print("Relief (Section 89(1)):", result.relief)


# In[ ]:




