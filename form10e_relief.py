#!/usr/bin/env python3
from dataclasses import dataclass
from typing import List

# --- Slab definitions (Old Regime) ---
SLABS = [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (float("inf"), 0.30)]

def compute_tax(taxable_income):
    tax = 0.0
    prev_limit = 0.0
    for limit, rate in SLABS:
        slab = max(0, min(taxable_income, limit) - prev_limit)
        tax += slab * rate
        prev_limit = limit
        if taxable_income <= limit:
            break
    # 87A rebate
    if taxable_income <= 500000:
        tax = 0.0
    return round(tax * 1.04, 0)  # 4% cess

@dataclass
class YearData:
    fy: str
    base_income: float
    arrears: float
    tax_without_arrears: float = 0.0
    tax_with_arrears: float = 0.0

def input_float(prompt):
    while True:
        try:
            return float(input(prompt + " ₹"))
        except ValueError:
            print("Invalid number. Try again.")

def input_year(prompt):
    while True:
        fy = input(prompt + " (e.g., FY2021-22): ").strip()
        if fy.startswith("FY") and len(fy) == 9:
            return fy
        print("Invalid format. Try again.")

def main():
    print("\n🧮 Form 10E Relief Calculator — Section 89(1)")
    receipt_year = input_year("Enter the Financial Year in which arrears were received")
    current_income = input_float("Enter taxable income for that year (excluding arrears)")
    total_arrears = input_float("Enter total arrears received")

    n_years = int(input_float("How many years do these arrears relate to"))
    year_data: List[YearData] = []

    print("\n📅 Enter details for each affected year:")
    for i in range(n_years):
        print(f"\nYear {i+1}:")
        fy = input_year("  Financial Year")
        base = input_float("  Taxable income (excluding arrears)")
        arrears = input_float("  Arrears for this year")
        year_data.append(YearData(fy=fy, base_income=base, arrears=arrears))

    mapped_total = round(sum(y.arrears for y in year_data), 2)
    if round(total_arrears, 2) != mapped_total:
        print(f"\n❌ Arrears mismatch: received ₹{total_arrears}, mapped ₹{mapped_total}")
        return

    print("\n📊 Computing tax for each year...")
    for y in year_data:
        y.tax_without_arrears = compute_tax(y.base_income)
        y.tax_with_arrears = compute_tax(y.base_income + y.arrears)

    current_tax_without = compute_tax(current_income)
    current_tax_with = compute_tax(current_income + total_arrears)

    past_deltas = [y.tax_with_arrears - y.tax_without_arrears for y in year_data]
    current_delta = current_tax_with - current_tax_without
    relief = max(0.0, round(sum(past_deltas) - current_delta, 0))

    print("\n📋 Year-wise Tax Comparison:")
    for y in year_data:
        print(f"  {y.fy}: Tax w/o arrears = ₹{y.tax_without_arrears}, Tax with arrears = ₹{y.tax_with_arrears}, Δ = ₹{y.tax_with_arrears - y.tax_without_arrears}")

    print(f"\n  {receipt_year} (Year of receipt): Tax w/o arrears = ₹{current_tax_without}, Tax with arrears = ₹{current_tax_with}, Δ = ₹{current_delta}")
    print(f"\n✅ Relief under Section 89(1): ₹{relief}")

if __name__ == "__main__":
    main()
