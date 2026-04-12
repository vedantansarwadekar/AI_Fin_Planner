# src/tools/calculators.py
"""
Indian financial calculators for ATOM Finance Agent.

Tools:
  - sip_calculator()       SIP maturity value + wealth gained
  - lumpsum_calculator()   One-time investment maturity
  - emi_calculator()       Loan EMI + total interest paid
  - income_tax_calculator() New tax regime (FY 2024-25)
  - fd_calculator()        Fixed deposit maturity
  - budget_plan()          50/30/20 budget split
  - savings_goal()         How much to save per month
"""

import math


# ── SIP Calculator ────────────────────────────────────────────────────────────

def sip_calculator(
    monthly_investment: float,
    annual_return_pct:  float,
    years:              int,
) -> dict:
    """
    Calculate SIP (Systematic Investment Plan) maturity value.

    Formula: M = P × {[(1 + r)^n - 1] / r} × (1 + r)
      where r = monthly rate, n = total months
    """
    r = annual_return_pct / 100 / 12      # monthly rate
    n = years * 12                         # total months

    if r == 0:
        maturity = monthly_investment * n
    else:
        maturity = monthly_investment * (((1 + r) ** n - 1) / r) * (1 + r)

    invested       = monthly_investment * n
    wealth_gained  = maturity - invested

    return {
        "type":                 "SIP Calculator",
        "monthly_investment":   f"₹{monthly_investment:,.0f}",
        "annual_return":        f"{annual_return_pct}%",
        "duration":             f"{years} years ({n} months)",
        "total_invested":       f"₹{invested:,.0f}",
        "maturity_value":       f"₹{maturity:,.0f}",
        "wealth_gained":        f"₹{wealth_gained:,.0f}",
        "returns_multiple":     f"{maturity/invested:.2f}x",
        "tip": (
            "Increase SIP by 10% every year (Step-Up SIP) "
            "to significantly boost your corpus."
        ),
    }


# ── Lumpsum Calculator ────────────────────────────────────────────────────────

def lumpsum_calculator(
    principal:         float,
    annual_return_pct: float,
    years:             int,
) -> dict:
    """Calculate one-time (lumpsum) investment maturity value."""
    r        = annual_return_pct / 100
    maturity = principal * ((1 + r) ** years)
    gained   = maturity - principal

    return {
        "type":            "Lumpsum Calculator",
        "principal":       f"₹{principal:,.0f}",
        "annual_return":   f"{annual_return_pct}%",
        "duration":        f"{years} years",
        "maturity_value":  f"₹{maturity:,.0f}",
        "wealth_gained":   f"₹{gained:,.0f}",
        "returns_multiple": f"{maturity/principal:.2f}x",
    }


# ── EMI Calculator ────────────────────────────────────────────────────────────

def emi_calculator(
    principal:        float,
    annual_rate_pct:  float,
    tenure_months:    int,
) -> dict:
    """
    Calculate loan EMI using reducing balance method.

    EMI = P × r × (1+r)^n / [(1+r)^n - 1]
    """
    r = annual_rate_pct / 100 / 12    # monthly rate

    if r == 0:
        emi = principal / tenure_months
    else:
        emi = principal * r * ((1 + r) ** tenure_months) / (((1 + r) ** tenure_months) - 1)

    total_payment  = emi * tenure_months
    total_interest = total_payment - principal

    return {
        "type":             "EMI Calculator",
        "loan_amount":      f"₹{principal:,.0f}",
        "interest_rate":    f"{annual_rate_pct}% per annum",
        "tenure":           f"{tenure_months} months ({tenure_months//12} years {tenure_months%12} months)",
        "monthly_emi":      f"₹{emi:,.0f}",
        "total_payment":    f"₹{total_payment:,.0f}",
        "total_interest":   f"₹{total_interest:,.0f}",
        "interest_ratio":   f"{(total_interest/principal*100):.1f}% of principal",
        "tip": (
            "Making one extra EMI per year can reduce your tenure "
            f"by approximately {tenure_months//24} months."
        ),
    }


# ── Income Tax Calculator (New Regime FY 2025-26) ────────────────────────────

def income_tax_calculator(annual_income: float, regime: str = "new") -> dict:
    """
    Calculate Indian income tax.

    New regime slabs (FY 2025-26, post Budget 2024):
      0 – 3,00,000        : 0%
      3,00,001 – 7,00,000 : 5%
      7,00,001 – 10,00,000: 10%
      10,00,001 – 12,00,000: 15%
      12,00,001 – 15,00,000: 20%
      Above 15,00,000     : 30%

    Old regime slabs:
      0 – 2,50,000        : 0%
      2,50,001 – 5,00,000 : 5%
      5,00,001 – 10,00,000: 20%
      Above 10,00,000     : 30%
    """
    if regime.lower() == "old":
        slabs = [
            (250000,  0.00),
            (250000,  0.05),
            (500000,  0.20),
            (float('inf'), 0.30),
        ]
        standard_deduction = 50000
        regime_label = "Old Regime"
    else:
        slabs = [
            (300000,  0.00),
            (400000,  0.05),
            (300000,  0.10),
            (200000,  0.15),
            (300000,  0.20),
            (float('inf'), 0.30),
        ]
        standard_deduction = 75000   # Budget 2024
        regime_label = "New Regime"

    taxable = max(0, annual_income - standard_deduction)
    tax     = 0.0
    remaining = taxable

    breakdown = []
    for slab_limit, rate in slabs:
        if remaining <= 0:
            break
        taxable_in_slab = min(remaining, slab_limit)
        tax_in_slab     = taxable_in_slab * rate
        if rate > 0:
            breakdown.append(
                f"  {rate*100:.0f}% on ₹{taxable_in_slab:,.0f} = ₹{tax_in_slab:,.0f}"
            )
        tax       += tax_in_slab
        remaining -= taxable_in_slab

    # Rebate u/s 87A (taxable income ≤ 7L in new regime / ≤ 5L in old)
    rebate_limit = 700000 if regime.lower() == "new" else 500000
    rebate = 0.0
    if taxable <= rebate_limit:
        rebate = tax
        tax    = 0.0

    # 4% Health & Education Cess
    cess = tax * 0.04
    total_tax = tax + cess

    effective_rate = (total_tax / annual_income * 100) if annual_income > 0 else 0

    return {
        "type":               "Income Tax Calculator",
        "regime":             regime_label,
        "gross_income":       f"₹{annual_income:,.0f}",
        "standard_deduction": f"₹{standard_deduction:,.0f}",
        "taxable_income":     f"₹{taxable:,.0f}",
        "tax_breakdown":      breakdown,
        "rebate_87A":         f"₹{rebate:,.0f}" if rebate > 0 else "Not applicable",
        "income_tax":         f"₹{tax:,.0f}",
        "cess_4pct":          f"₹{cess:,.0f}",
        "total_tax":          f"₹{total_tax:,.0f}",
        "effective_rate":     f"{effective_rate:.2f}%",
        "monthly_take_home":  f"₹{(annual_income - total_tax) / 12:,.0f}",
        "tip": (
            "Compare both regimes — old regime may be better "
            "if you have 80C/80D/HRA deductions above ₹2.5L."
        ),
    }


# ── FD Calculator ─────────────────────────────────────────────────────────────

def fd_calculator(
    principal:         float,
    annual_rate_pct:   float,
    years:             int,
    compounding:       str = "quarterly",  # quarterly / monthly / annually
) -> dict:
    """Calculate Fixed Deposit maturity with compounding."""
    freq_map = {"monthly": 12, "quarterly": 4, "annually": 1}
    n = freq_map.get(compounding.lower(), 4)
    r = annual_rate_pct / 100

    maturity = principal * ((1 + r / n) ** (n * years))
    interest = maturity - principal

    return {
        "type":          "FD Calculator",
        "principal":     f"₹{principal:,.0f}",
        "interest_rate": f"{annual_rate_pct}% per annum",
        "duration":      f"{years} years",
        "compounding":   compounding.capitalize(),
        "maturity":      f"₹{maturity:,.0f}",
        "interest":      f"₹{interest:,.0f}",
        "note":          "TDS of 10% applies if interest > ₹40,000/year (₹50,000 for seniors).",
    }


# ── Budget Plan ───────────────────────────────────────────────────────────────

def budget_plan(income: float, fixed: float = None, variable: float = None) -> dict:
    """50/30/20 budget split."""
    needs   = round(income * 0.50)
    wants   = round(income * 0.30)
    savings = round(income * 0.20)

    return {
        "type":          "Budget Plan (50/30/20 Rule)",
        "monthly_income": f"₹{income:,.0f}",
        "needs_50pct":   f"₹{needs:,.0f}  (rent, groceries, EMIs, utilities)",
        "wants_30pct":   f"₹{wants:,.0f}  (dining, entertainment, shopping)",
        "savings_20pct": f"₹{savings:,.0f} (SIP, emergency fund, investments)",
        "annual_savings": f"₹{savings*12:,.0f}",
        "tip": (
            "Keep 3-6 months of expenses as an emergency fund "
            f"(₹{needs*3:,.0f} – ₹{needs*6:,.0f}) before aggressive investing."
        ),
    }


# ── Savings Goal ──────────────────────────────────────────────────────────────

def savings_goal(target: float, months: int, current_savings: float = 0) -> dict:
    """How much to save per month to hit a target."""
    remaining   = max(0, target - current_savings)
    per_month   = round(remaining / months, 2) if months > 0 else remaining

    return {
        "type":             "Savings Goal Planner",
        "target_amount":    f"₹{target:,.0f}",
        "current_savings":  f"₹{current_savings:,.0f}",
        "remaining":        f"₹{remaining:,.0f}",
        "months":           months,
        "monthly_required": f"₹{per_month:,.0f}",
        "tip":              "Park savings in a liquid mutual fund to earn ~7% while staying accessible.",
    }