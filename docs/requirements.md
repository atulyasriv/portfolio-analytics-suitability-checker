# Product requirements — Portfolio Analytics & Suitability Checker

## Purpose and scope

The application provides an educational research view of an illustrative Indian-market portfolio. It helps a user inspect holdings, historical performance, risk, benchmark-relative behaviour, and rule-based checks against fictional investor mandates. It is not an investment-advice or regulated suitability product.

## Users

- **Portfolio analyst / student user:** reviews portfolio values, performance, risk, and concentration.
- **Reviewer / interviewer:** evaluates the implementation, assumptions, SQL usage, data handling, and test coverage.

## User stories and acceptance criteria

### US-01 — View portfolio valuation

**As a** portfolio analyst, **I want** to see the current value and weight of each holding, **so that** I can understand the portfolio composition.

Acceptance criteria:
- The application displays each configured holding, its asset class, quantity, current value, and portfolio weight when complete prices are available.
- Market holdings are valued using a common available trading date.
- Bond and cash positions are shown separately using the documented illustrative assumptions.
- If a required market price is missing, the application does not present a partial subtotal as the complete portfolio value.

### US-02 — Inspect historical performance against a benchmark

**As a** portfolio analyst, **I want** to compare portfolio performance with the Nifty 50, **so that** I can understand historical relative performance.

Acceptance criteria:
- Portfolio and benchmark observations are aligned by date before comparison.
- The application reports annualised portfolio and benchmark returns when sufficient observations exist.
- The benchmark is identified as Nifty 50 (`^NSEI`).
- Missing or insufficient benchmark data is labelled unavailable rather than silently substituted.

### US-03 — Understand portfolio risk

**As a** portfolio analyst, **I want** to inspect volatility, Sharpe ratio, drawdown, beta, and VaR, **so that** I can evaluate historical risk characteristics.

Acceptance criteria:
- Risk metrics use documented formulas and annualisation conventions.
- Maximum drawdown is calculated from a cumulative wealth series and its running peak.
- Beta and active-risk measures use aligned portfolio and benchmark returns.
- Metrics that cannot be calculated from available observations are displayed as unavailable.

### US-04 — Review allocation and concentration

**As a** portfolio analyst, **I want** to see asset-class allocation, sector concentration, and holding correlations, **so that** I can identify concentration and diversification patterns.

Acceptance criteria:
- Asset-class weights reconcile to the total portfolio value when all required values are present.
- Sector weights use the total portfolio as the denominator and include only the documented equity/equity-ETF sector exposures in the numerator.
- Correlation is calculated from holding return series and unavailable when there are insufficient observations.

### US-05 — Check an illustrative investor mandate

**As a** portfolio analyst, **I want** to select a fictional Conservative, Moderate, or Aggressive profile, **so that** I can see whether the portfolio meets the sample thresholds.

Acceptance criteria:
- Each profile exposes its limits for equity allocation, largest equity holding, sector concentration, debt/cash, gold, and volatility.
- Each rule is labelled OK, Watch, or Breach according to the configured thresholds.
- Incomplete price data forces a Review result and prevents a suitability conclusion.
- The interface clearly states that the profiles and thresholds are illustrative and not regulatory advice.

### US-06 — Edit quantities safely within a session

**As a** user, **I want** to change holding quantities during my session, **so that** I can explore hypothetical portfolio compositions without changing the source portfolio.

Acceptance criteria:
- Quantity edits are held in Streamlit session state and do not rewrite the source holdings file.
- SQL analytics refresh from the current session quantities and selected price source.
- Each active Streamlit session receives a distinct temporary SQLite database path.
- The displayed outputs update after quantity changes or a market-price refresh.

## Non-functional requirements

- **Reproducibility:** assumptions and calculation methods are documented in the repository.
- **Data integrity:** the fallback CSV must contain `date`, `ticker`, and `adjusted_close`; missing data must not be presented as a complete portfolio result.
- **Maintainability:** data access, SQL persistence, metrics, profiles, explanations, and UI are separated into modules.
- **Testability:** metric and SQL logic is covered by offline pytest tests using synthetic inputs.
- **Usability:** financial values, statuses, and unavailable metrics should be clearly labelled.
- **Privacy:** the demo uses fictional holdings and no personal or client financial information.

## Out of scope

- Brokerage execution, order placement, or trade recommendations.
- Production client onboarding, identity management, or persistent multi-user account storage.
- Regulatory suitability determinations or compliance sign-off.
- Full bond pricing, tax calculations, transaction costs, and cash-flow-aware performance attribution.
