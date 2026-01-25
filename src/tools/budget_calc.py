def budget_plan(income: float, fixed: float, variable: float):
    savings = income - (fixed + variable)
    savings_rate = (savings / income) * 100 if income else 0

    return {
        "income": income,
        "fixed_costs": fixed,
        "variable_costs": variable,
        "savings_possible": savings,
        "savings_rate_percent": round(savings_rate, 2),
    }
