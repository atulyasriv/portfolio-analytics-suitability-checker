"""Short numeric interpretations for portfolio and investor mandate metrics."""
import numpy as np


def explain_return(p, b):
    if not np.isfinite(p):
        return "Portfolio annualised return is unavailable from verified price history."
    if np.isfinite(b):
        gap = p-b
        return f"Annualised portfolio return is {p:.1%} versus {b:.1%} for Nifty 50, a {abs(gap):.1%} {'outperformance' if gap >= 0 else 'shortfall'} over the same dates."
    return f"Annualised portfolio return is {p:.1%}; benchmark comparison is unavailable."


def explain_volatility(v, benchmark_v, profile, limit):
    if not np.isfinite(v):
        return "Annualised volatility is unavailable because verified return history is insufficient."
    comparison = f" Nifty 50 volatility is {benchmark_v:.1%}." if np.isfinite(benchmark_v) else " Nifty 50 volatility is unavailable."
    fit = f" It exceeds the {limit:.1%} ceiling for {profile}, so it fluctuates more than this investor's stated limit." if v > limit else f" It is within the {limit:.1%} ceiling for {profile}."
    return f"Portfolio volatility is {v:.1%}.{comparison}{fit}"


def explain_sharpe(value, method):
    return f"{method} Sharpe ratio is {value:.2f}; it measures excess annual return per unit of annualised volatility." if np.isfinite(value) else f"{method} Sharpe ratio is unavailable; verify the risk-free rate and return history."


def explain_drawdown(value, date, profile, loss_limit):
    if not np.isfinite(value) or date is None:
        return "Maximum drawdown is unavailable."
    comparison = "within" if abs(value) <= loss_limit else "above"
    return f"Maximum drawdown was {value:.1%} on {date:%d %b %Y}; it is the largest fall from a prior cumulative-value peak and is {comparison} the {loss_limit:.1%} illustrative loss tolerance for {profile}."


def explain_beta(value, profile):
    if not np.isfinite(value):
        return "Beta is unavailable because aligned observations are insufficient."
    direction = "more sensitive" if value > 1 else "less sensitive" if value < 1 else "similarly sensitive"
    return f"Beta is {value:.2f}; historically, a 1% Nifty 50 move was associated with an estimated {value:.2f}% portfolio move. The portfolio was {direction} than the benchmark, which {profile} investors should consider when assessing market exposure."


def explain_var(value, horizon):
    return f"{horizon}-day historical 95% VaR is {value:.1%}; this is the empirical loss threshold exceeded by about 5% of sample observations." if np.isfinite(value) else f"{horizon}-day historical VaR is unavailable."


def explain_tracking_error(value):
    return f"Annualised tracking error is {value:.1%}; it measures volatility of daily portfolio-minus-Nifty returns." if np.isfinite(value) else "Tracking error is unavailable."


def explain_information_ratio(value):
    return f"Information ratio is {value:.2f}; it is average annualised active return divided by tracking error." if np.isfinite(value) else "Information ratio is unavailable."


def explain_best_worst(best, worst):
    return f"Best day was {best:.1%} and worst day was {worst:.1%}; these are the largest observed one-day gain and loss." if np.isfinite(best) and np.isfinite(worst) else "Best and worst daily returns are unavailable."



def explain_rolling_volatility(latest_value, profile, limit):
    """Explain current rolling volatility against the selected profile's annual volatility ceiling."""
    if not np.isfinite(latest_value):
        return "Rolling 60-day volatility is unavailable until 60 daily portfolio returns are present."
    if latest_value > limit:
        return f"Latest 60-day annualised volatility is {latest_value:.1%}, above the {limit:.1%} ceiling for {profile}; recent fluctuations exceed this investor's stated limit."
    return f"Latest 60-day annualised volatility is {latest_value:.1%}, within the {limit:.1%} ceiling for {profile}."


def explain_correlation(matrix):
    """Explain the observed correlation range and why co-movement matters for diversification."""
    if matrix.empty or matrix.shape[1] < 2:
        return "Holding correlation is unavailable because fewer than two priced holdings are present."
    upper = matrix.where(np.triu(np.ones(matrix.shape), k=1).astype(bool)).stack()
    if upper.empty:
        return "Holding correlation is unavailable."
    low, high = float(upper.min()), float(upper.max())
    return f"Pairwise daily-return correlations range from {low:.2f} to {high:.2f}; holdings with correlations near +1 have tended to move together, reducing the diversification benefit."
