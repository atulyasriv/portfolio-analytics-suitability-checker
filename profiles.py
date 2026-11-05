"""Fictional investor mandates. Bond and cash are excluded from equity concentration tests."""
import numpy as np
import pandas as pd

ASSET_CLASS_MAP = {
    "Equity": "equity", "Equity ETF": "equity",
    "Commodity": "gold", "Bond": "defensive", "Cash": "defensive",
}

PROFILES = {
    "A — Conservative": {
        "description": "Capital protection and lower portfolio fluctuations.",
        "equity_min_pct": 0, "equity_max_pct": 30, "max_single_holding_pct": 10,
        "max_sector_pct": 20, "min_debt_cash_pct": 70, "max_volatility": .10,
        "max_gold_pct": 5, "max_tolerable_loss": .10,
    },
    "B — Moderate": {
        "description": "Balanced growth with a meaningful defensive allocation.",
        "equity_min_pct": 30, "equity_max_pct": 65, "max_single_holding_pct": 20,
        "max_sector_pct": 30, "min_debt_cash_pct": 35, "max_volatility": .18,
        "max_gold_pct": 10, "max_tolerable_loss": .18,
    },
    "C — Aggressive": {
        "description": "Long-term growth with higher tolerance for fluctuations.",
        "equity_min_pct": 50, "equity_max_pct": 100, "max_single_holding_pct": 35,
        "max_sector_pct": 45, "min_debt_cash_pct": 0, "max_volatility": .30,
        "max_gold_pct": 20, "max_tolerable_loss": .30,
    },
}


def check_suitability(snapshot, profile_name, annual_volatility, partial=False):
    """Return rule table and reasons; partial prices force Review and no suitability conclusion."""
    rules = PROFILES[profile_name]
    if partial or snapshot["current_value"].isna().any():
        return {
            "status": "Review", "partial": True,
            "reasons": ["Partial data: one or more market holdings have no verified current value. Suitability has not been assessed."],
            "table": pd.DataFrame([{"Rule":"Data completeness","Limit":"All holdings priced","Actual":"Partial","Status":"Breach"}]),
        }
    total = float(snapshot["current_value"].sum())
    if total <= 0:
        return {"status":"Review","partial":False,"reasons":["Portfolio value is unavailable."],"table":pd.DataFrame()}
    # Map each holding to an explicit exposure bucket before applying any mandate rule.
    buckets = snapshot["asset_class"].map(ASSET_CLASS_MAP)
    eq = snapshot[buckets == "equity"]
    gold = snapshot[buckets == "gold"]
    defensive = snapshot[buckets == "defensive"]
    equity_pct = float(eq.current_value.sum() / total * 100)
    gold_pct = float(gold.current_value.sum() / total * 100)
    debt_cash_pct = float(defensive.current_value.sum() / total * 100)
    largest = float(eq.current_value.max() / total * 100) if not eq.empty else 0
    sector_max = float(eq.groupby("sector").current_value.sum().max() / total * 100) if not eq.empty else 0

    checks = [
        ("Equity allocation", f"{rules['equity_min_pct']}–{rules['equity_max_pct']}%", equity_pct, "range", rules["equity_min_pct"], rules["equity_max_pct"]),
        ("Largest equity holding", f"≤ {rules['max_single_holding_pct']}%", largest, "max", rules["max_single_holding_pct"], None),
        ("Largest equity sector", f"≤ {rules['max_sector_pct']}%", sector_max, "max", rules["max_sector_pct"], None),
        ("Debt + cash", f"≥ {rules['min_debt_cash_pct']}%", debt_cash_pct, "min", rules["min_debt_cash_pct"], None),
        ("Gold / commodity", f"≤ {rules['max_gold_pct']}%", gold_pct, "max", rules["max_gold_pct"], None),
    ]
    if np.isfinite(annual_volatility):
        checks.append(("Annualised volatility", f"≤ {rules['max_volatility']:.1%}", annual_volatility*100, "max", rules["max_volatility"]*100, None))
    rows = []
    for name, limit, actual, kind, low, high in checks:
        if kind == "range":
            status = "Breach" if actual < low or actual > high else (
                "Watch" if actual <= low + (high-low)*.10 or actual >= high - (high-low)*.10 else "OK"
            )
        elif kind == "min":
            status = "Breach" if actual < low else ("Watch" if low > 0 and actual <= low*1.10 else "OK")
        else:
            status = "Breach" if actual > low else ("Watch" if low > 0 and actual >= low*.90 else "OK")
        rows.append({"Rule":name,"Limit":limit,"Actual":f"{actual:.1f}%","Status":status})
    table = pd.DataFrame(rows)
    reasons = [f"{r['Rule']}: actual {r['Actual']} against {r['Limit']} ({r['Status']})."
               for r in rows if r["Status"] != "OK"]
    return {
        "status": "Review" if (table.Status != "OK").any() else "OK",
        "partial":False, "reasons":reasons or ["All measured exposures are within the selected illustrative mandate."],
        "table":table, "equity_pct":equity_pct, "gold_pct":gold_pct,
        "debt_cash_pct":debt_cash_pct, "total_value":total,
    }


def rebalancing_observation(result, profile_name):
    """Estimate value shift to the nearest equity range edge; this is an observation, not advice."""
    if result.get("partial") or "equity_pct" not in result:
        return "No allocation observation is available until all holdings have verified prices."
    rule = PROFILES[profile_name]
    actual, total = result["equity_pct"], result["total_value"]
    if actual > rule["equity_max_pct"]:
        amount = total * (actual-rule["equity_max_pct"]) / 100
        return f"Observation: approximately ₹{amount:,.0f} of value would need to move out of equity exposure to reach the {rule['equity_max_pct']}% upper boundary."
    if actual < rule["equity_min_pct"]:
        amount = total * (rule["equity_min_pct"]-actual) / 100
        return f"Observation: approximately ₹{amount:,.0f} of value would need to move into equity exposure to reach the {rule['equity_min_pct']}% lower boundary."
    return f"Observation: equity exposure is within the {rule['equity_min_pct']}–{rule['equity_max_pct']}% range; ₹0 needs to move to meet the equity allocation range. Other Review flags may remain."
