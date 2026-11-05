import numpy as np
from pathlib import Path
import tempfile
import uuid
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from data import CONFIG, get_portfolio, load_prices, prepare_purchase_basis, get_price_status
from database import refresh_database, query_current_holdings, query_allocation, query_sector_concentration, query_daily_analytics
from metrics import (
    daily_portfolio_returns, annualised_return, annualised_volatility, sharpe_geometric,
    sharpe_standard, drawdown_series, maximum_drawdown, maximum_drawdown_date,
    correlation_matrix, beta_vs_benchmark, cumulative_growth, historical_var,
    historical_var_10d, rolling_volatility, tracking_error, information_ratio,
    best_worst_day, portfolio_snapshot, stress_test,
)
from profiles import PROFILES, check_suitability, rebalancing_observation
from explain import (
    explain_return, explain_volatility, explain_sharpe, explain_drawdown,
    explain_beta, explain_var, explain_tracking_error, explain_information_ratio, explain_best_worst,
    explain_rolling_volatility, explain_correlation,
)
from styles import C, PLOTLY_TEMPLATE, inject_styles

st.set_page_config(page_title="Portfolio Analytics | Research Note", layout="wide")
inject_styles()
st.title("Portfolio Analytics & Suitability")
st.markdown('<div class="eyebrow">Portfolio research note · India · INR</div>', unsafe_allow_html=True)

if "quantities" not in st.session_state:
    st.session_state.quantities = dict(zip(get_portfolio().ticker, get_portfolio().quantity))

with st.sidebar:
    st.markdown("### Mandate")
    profile = st.selectbox("Investor profile", list(PROFILES), index=1)
    st.caption(PROFILES[profile]["description"])
    st.markdown("---")
    st.markdown("### Position sizing")
    st.caption("Session-only edits; source quantities are unchanged.")
    for r in get_portfolio().itertuples(index=False):
        st.session_state.quantities[r.ticker] = st.number_input(
            r.name, min_value=0.0, value=float(st.session_state.quantities[r.ticker]),
            step=1.0, key="qty_"+r.ticker,
        )
    if st.button("Refresh market prices"):
        st.cache_data.clear()
        st.rerun()

portfolio = get_portfolio()
portfolio["quantity"] = portfolio.ticker.map(st.session_state.quantities).astype(float)

try:
    with st.spinner("Loading adjusted close history..."):
        prices, failed, source = load_prices(portfolio)
    complete, missing = get_price_status(portfolio, prices, failed)
    if prices.empty:
        st.warning("No verified market prices are available. Holdings remain visible; calculated metrics are unavailable until live prices or a verified snapshot are supplied.")
        st.dataframe(portfolio[["name","ticker","asset_class","quantity"]], use_container_width=True, hide_index=True)
        st.stop()
    if not complete:
        st.warning("PARTIAL PRICE DATA — unavailable tickers: "+", ".join(missing)+". Full-portfolio metrics are marked PARTIAL; suitability is not assessed.")
    elif source.startswith("Stored snapshot as of "):
        st.info("Using stored prices as of " + source.split("Stored snapshot as of ", 1)[1] + ".")
    else:
        st.caption("Price source: " + source)

    portfolio = prepare_purchase_basis(portfolio, prices)
    # Refresh SQLite from the selected price source and the current session quantities.
    if "db_id" not in st.session_state:
        st.session_state.db_id = uuid.uuid4().hex
    db_path = Path(tempfile.gettempdir()) / f"portfolio_{st.session_state.db_id}.db"
    refresh_database(portfolio, prices, PROFILES, db_path, CONFIG["bond_yield"])
    snapshot = query_current_holdings(db_path, CONFIG["bond_yield"])
    daily_sql = query_daily_analytics(db_path, CONFIG["bond_yield"])
    st.caption("SQLite analytics layer · Holdings, allocation, sector exposure, daily returns and drawdowns are queried from SQL.")
    if daily_sql.empty:
        complete = False
        st.warning("No common trading dates are available across all market-priced holdings. Full-portfolio metrics and suitability are withheld.")
    values = daily_sql["portfolio_value"].rename("Portfolio value") if not daily_sql.empty else pd.Series(dtype=float)
    returns = daily_sql["daily_return"].dropna() if complete and not daily_sql.empty else pd.Series(dtype=float)
    bench = prices[CONFIG["benchmark_ticker"]].pct_change().dropna() if CONFIG["benchmark_ticker"] in prices else pd.Series(dtype=float)
    ar = annualised_return(returns, CONFIG["trading_days"]) if complete else np.nan
    vol = annualised_volatility(returns, CONFIG["trading_days"]) if complete else np.nan
    rf = CONFIG["risk_free_rate"]
    sg = sharpe_geometric(returns, rf, CONFIG["trading_days"]) if complete else np.nan
    ss = sharpe_standard(returns, rf, CONFIG["trading_days"]) if complete else np.nan
    mdd = float(daily_sql["drawdown"].min()) if complete and not daily_sql.empty else np.nan
    mdd_date = daily_sql["drawdown"].idxmin() if complete and not daily_sql.empty else None
    br = annualised_return(bench, CONFIG["trading_days"]) if len(bench) else np.nan
    bv = annualised_volatility(bench, CONFIG["trading_days"]) if len(bench) else np.nan
    beta = beta_vs_benchmark(returns, bench) if complete and len(bench) else np.nan
    total_value = snapshot.current_value.sum(min_count=1)
    invested = snapshot.cost.sum(min_count=1)
    # Never present a subtotal as the complete portfolio value when any holding is unpriced.
    display_total_value = total_value if complete else np.nan
    display_invested = invested if complete else np.nan
    since_return = total_value/invested-1 if complete and invested else np.nan
    suitability = check_suitability(snapshot, profile, vol, partial=not complete)

    def indian_grouping(value):
        sign = "-" if value < 0 else ""
        whole = str(int(round(abs(value))))
        if len(whole) <= 3:
            grouped = whole
        else:
            last3, rest = whole[-3:], whole[:-3]
            chunks = []
            while rest:
                chunks.insert(0, rest[-2:])
                rest = rest[:-2]
            grouped = ",".join(chunks + [last3])
        return sign + grouped

    def money(x):
        return f"₹{indian_grouping(x)}" if np.isfinite(x) else "PARTIAL / N.A."

    def indian_rupees(x):
        return f"₹{indian_grouping(x)}" if pd.notna(x) else "N.A."
    def pct(x, n=1):
        return f"{x*100:,.{n}f}%" if np.isfinite(x) else "PARTIAL / N.A."

    reconciliation_ok = None
    if complete and len(returns):
        compounded_return = (1 + returns).prod() - 1
        annualised_reconciled = (1 + ar) ** (len(returns) / CONFIG["trading_days"]) - 1
        reconciliation_ok = (
            np.isclose(compounded_return, since_return, atol=1e-8)
            and np.isclose(annualised_reconciled, since_return, atol=1e-8)
        )

    st.markdown(f"""<div class="facts">
    <div class="fact"><div class="flabel">Portfolio value</div><div class="fvalue">{money(display_total_value)}</div></div>
    <div class="fact"><div class="flabel">Invested basis</div><div class="fvalue">{money(display_invested)}</div></div>
    <div class="fact"><div class="flabel">Return since basis</div><div class="fvalue">{pct(since_return)}</div></div>
    <div class="fact"><div class="flabel">Volatility</div><div class="fvalue">{pct(vol)}</div></div>
    <div class="fact"><div class="flabel">Sharpe · geometric</div><div class="fvalue">{f'{sg:.2f}' if np.isfinite(sg) else 'N.A.'}</div></div>
    <div class="fact"><div class="flabel">Max drawdown</div><div class="fvalue">{pct(mdd)}</div></div></div>""", unsafe_allow_html=True)
    st.caption("Buy-and-hold, no rebalancing, no cash flows. Full-portfolio metrics require complete market prices.")
    if reconciliation_ok is True:
        st.caption("Return reconciliation: passed.")
    elif reconciliation_ok is False:
        st.warning("Return reconciliation check failed. Treat the headline return and annualised return as unverified until the data alignment is reviewed.")

    tab_overview, tab_risk, tab_suit = st.tabs(["Overview","Risk & Performance","Suitability"])
    with tab_overview:
        st.header("Portfolio composition")
        left,right=st.columns(2)
        alloc=query_allocation(db_path, CONFIG["bond_yield"])
        with left:
            st.subheader("Asset-class allocation")
            fig=go.Figure(go.Bar(x=alloc.weight*100,y=alloc.asset_class,orientation="h",
                marker_color=[C["teal"] if a in ("Equity","Equity ETF") else "#9A9A94" for a in alloc.asset_class],
                text=[f"{v:.1f}%" for v in alloc.weight*100],textposition="outside"))
            fig.update_layout(template=PLOTLY_TEMPLATE,showlegend=False,
                              xaxis=dict(title="Weight (%)",range=[0, max(float(alloc.weight.max()*125), 1)]),
                              yaxis_title="",height=300)
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
            st.subheader("Equity mandate range")
            equity_weight = snapshot.loc[snapshot.asset_class.isin(["Equity","Equity ETF"]),"current_value"].sum()/total_value*100
            mandate = PROFILES[profile]
            range_fig = go.Figure()
            range_fig.add_shape(type="rect", x0=mandate["equity_min_pct"], x1=mandate["equity_max_pct"],
                                y0=-0.38, y1=0.38, fillcolor="rgba(15,92,92,0.14)",
                                line=dict(width=0), layer="below")
            range_fig.add_trace(go.Bar(x=[equity_weight], y=["Equity exposure"], orientation="h",
                                       marker_color=C["teal"], text=[f"{equity_weight:.1f}%"],
                                       textposition="outside", width=0.34))
            range_fig.update_layout(template=PLOTLY_TEMPLATE, showlegend=False,
                                    xaxis=dict(range=[0,100], title="Portfolio weight (%)"),
                                    yaxis=dict(showticklabels=False), height=130)
            st.plotly_chart(range_fig,use_container_width=True,config={"displayModeBar":False})
        with right:
            st.subheader("Equity sector exposure (% of portfolio)")
            sec=query_sector_concentration(db_path, CONFIG["bond_yield"])
            fig=go.Figure(go.Bar(x=sec.weight*100,y=sec.sector,orientation="h",marker_color=C["teal"],
                text=[f"{v:.1f}%" for v in sec.weight*100],textposition="outside"))
            fig.update_layout(template=PLOTLY_TEMPLATE,showlegend=False,
                              xaxis=dict(title="Weight (%)",range=[0, max(float(sec.weight.max()*125), 1)]),
                              yaxis_title="",height=300)
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        st.header("Holdings")
        table=snapshot.rename(columns={"name":"Holding","ticker":"Ticker","asset_class":"Asset class","sector":"Sector","quantity":"Quantity","purchase_date":"Purchase date","cost":"Cost basis (₹)","current_value":"Current value (₹)","return_pct":"Return (%)"})
        table["Purchase date"] = table["Purchase date"].fillna("—")
        table["Weight"]=table["Current value (₹)"]/total_value
        styled_table = table[["Holding","Ticker","Asset class","Sector","Quantity","Purchase date","Cost basis (₹)","Current value (₹)","Return (%)","Weight"]].style.format({
            "Cost basis (₹)":indian_rupees,"Current value (₹)":indian_rupees,
            "Return (%)":"{:.1f}","Weight":"{:.1%}","Quantity":"{:,.0f}"
        },na_rep="N.A.").map(
            lambda v: f"color: {C['brick']}" if pd.notna(v) and v < 0 else "",
            subset=["Return (%)"]
        )
        st.dataframe(styled_table,use_container_width=True,hide_index=True)

    with tab_risk:
        st.header("Risk and performance")
        st.write(explain_return(ar,br))
        st.write(explain_volatility(vol,bv,profile,PROFILES[profile]["max_volatility"]))
        st.write(explain_sharpe(sg,"Geometric"))
        if rf is None:
            st.info("Sharpe ratios are unavailable until the Indian 10-year G-sec risk-free rate is verified and entered in data.py. TODO: cite source and observation date.")
        st.caption("Primary Sharpe: (geometric annualised return − annual rf) / annualised volatility. Standard daily-excess Sharpe is calculated separately.")
        st.caption(f"Standard daily-excess Sharpe: {ss:.2f}" if np.isfinite(ss) else "Standard daily-excess Sharpe: unavailable.")
        st.write(explain_drawdown(mdd,mdd_date,profile,PROFILES[profile]['max_tolerable_loss']))
        st.write(explain_beta(beta,profile))
        if complete and len(bench):
            st.subheader("Cumulative growth of ₹1")
            growth=pd.concat([cumulative_growth(returns,"Portfolio"),cumulative_growth(bench,"Nifty 50")],axis=1).dropna()
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=growth.index,y=growth.Portfolio,name="Portfolio",line=dict(color=C["teal"],width=2.5)))
            fig.add_trace(go.Scatter(x=growth.index,y=growth["Nifty 50"],name="Nifty 50",line=dict(color="#8A8F98",width=1.7)))
            fig.update_layout(template=PLOTLY_TEMPLATE,height=330,yaxis_title="Growth of ₹1")
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
            st.subheader("Drawdown")
            dd=drawdown_series(returns)
            fig=go.Figure(go.Scatter(x=dd.index,y=dd*100,fill="tozeroy",line=dict(color=C["brick"],width=1.5)))
            if mdd_date is not None:
                fig.add_annotation(x=mdd_date,y=mdd*100,text=f"Worst: {mdd:.1%} · {mdd_date:%d %b %Y}",showarrow=True)
            fig.update_layout(template=PLOTLY_TEMPLATE,height=260,yaxis_title="Drawdown (%)")
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
            st.subheader("Additional risk measures")
            var1,var10=historical_var(returns),historical_var_10d(returns)
            te,ir=tracking_error(returns,bench),information_ratio(returns,bench)
            best,worst=best_worst_day(returns)
            a,b,c=st.columns(3)
            a.metric("Historical VaR · 1 day",pct(var1)); b.metric("Historical VaR · 10 day",pct(var10)); c.metric("Tracking error",pct(te))
            st.write(explain_var(var1,1)); st.write(explain_var(var10,10)); st.write(explain_tracking_error(te))
            st.write(explain_information_ratio(ir)); st.write(explain_best_worst(best,worst))
            st.metric("Information ratio",f"{ir:.2f}" if np.isfinite(ir) else "N.A.")
            st.subheader("Rolling 60-day volatility")
            roll=rolling_volatility(returns,60,CONFIG["trading_days"])
            latest_roll = roll.dropna().iloc[-1] if roll.notna().any() else np.nan
            st.write(explain_rolling_volatility(latest_roll, profile, PROFILES[profile]["max_volatility"]))
            fig=go.Figure(go.Scatter(x=roll.index,y=roll*100,line=dict(color=C["teal"],width=1.8)))
            fig.update_layout(template=PLOTLY_TEMPLATE,height=250,yaxis_title="Annualised volatility (%)")
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
            st.subheader("Holding return correlation")
            hvals=pd.DataFrame(index=prices.index)
            for r in portfolio[portfolio.asset_class.isin(["Equity","Equity ETF","Commodity"])].itertuples(index=False):
                if r.ticker in prices: hvals[r.name]=prices[r.ticker]*r.quantity
            corr=correlation_matrix(hvals)
            if not corr.empty:
                st.write(explain_correlation(corr))
                fig=px.imshow(corr,zmin=-1,zmax=1,aspect="auto",
                    color_continuous_scale=[[0,C["brick"]],[.5,C["paper"]],[1,C["teal"]]])
                fig.update_layout(template=PLOTLY_TEMPLATE,height=400)
                st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
        else:
            st.warning("Risk metrics and benchmark comparison are PARTIAL or unavailable.")
        st.subheader("Hypothetical stress tests")
        st.caption("Assumed shocks, not forecasts: equity −20%; equity crash −35%; equity −10% with gold +10%; bond −5%.")
        if complete:
            scenarios={"Equities −20%":{"equity":-.20},"Equity crash −35%":{"equity":-.35},
                "Equity −10%, gold +10%":{"equity":-.10,"gold":.10},"Bond value −5%":{"bond":-.05}}
            stress=stress_test(snapshot,scenarios)
            loss_limit=PROFILES[profile]["max_tolerable_loss"]
            stress["Profile loss limit breached"]=stress["Change (%)"].apply(
                lambda x:"Yes" if np.isfinite(x) and -x>loss_limit else "No")
            st.dataframe(stress.style.format({
                "Change (₹)": lambda x: f"₹{indian_grouping(x)}",
                "Change (%)": "{:.1%}",
                "Stressed value (₹)": lambda x: f"₹{indian_grouping(x)}",
            }),use_container_width=True,hide_index=True)
        else:
            st.warning("Stress results are withheld because market prices are incomplete.")

    with tab_suit:
        st.header("Mandate assessment")
        st.success("Status: OK") if suitability["status"]=="OK" else st.warning("Status: Review")
        st.dataframe(suitability["table"],use_container_width=True,hide_index=True)
        for reason in suitability["reasons"]: st.write(reason)
        st.write(rebalancing_observation(suitability,profile))
        st.caption("Concentration checks apply only to Equity and Equity ETF. Gold/Commodity has a separate limit. Bond and Cash are excluded.")

    st.header("Methodology and assumptions")
    st.markdown(f"""
    - Lookback: {CONFIG['lookback_years']} years; daily adjusted close from {CONFIG['price_source']}.
    - Benchmark: Nifty 50 ({CONFIG['benchmark_ticker']}); annualisation: {CONFIG['trading_days']} trading days.
    - Bond: principal compounded at assumed {CONFIG['bond_yield']:.1%}; cash: fixed principal at 0%.
    - Risk-free rate: {rf:.2%} annual proxy; provisional secondary-source figure, TODO verify the latest official CCIL/FBIL/RBI 10-year G-sec observation and date.
    - Buy-and-hold, no rebalancing, no cash flows; current quantities assumed constant across the history.
    - Market purchase basis: adjusted close on the first common trading date available for all market-priced holdings; not a verified personal transaction price.
    - Snapshot file: {CONFIG["snapshot_file"]}; latest price date in the selected data source: {prices.index.max().date()}.
    - 10-day VaR uses overlapping compounded ten-day returns; stress shocks and profile limits are illustrative assumptions.
    - Limitations: no fees, taxes, slippage, external cash flows, actual bond pricing, duration, investor liabilities or goals.
    - Partial market data prevents a definitive suitability result and full-portfolio risk metrics.
    """)
    st.markdown(f'<div class="foot">Illustrative portfolio. Prices: {source}, as of {prices.index.max().date()}. Not investment advice.</div>',unsafe_allow_html=True)

except Exception as exc:
    st.error("Analysis could not be completed. Holdings and the app remain available; review the data status and retry.")
    st.exception(exc)
    st.info("TODO: verify network access, yfinance ticker availability, and the committed snapshot file.")
