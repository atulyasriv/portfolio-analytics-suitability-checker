"""Shared research-note stylesheet and Plotly theme."""
import streamlit as st
import plotly.graph_objects as go

C = {"paper":"#FAF8F4","ink":"#1B1F2A","teal":"#0F5C5C","brick":"#A63D2F","muted":"#6B7280","rule":"#D9D6CF"}
PLOTLY_TEMPLATE = go.layout.Template(layout=go.Layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="IBM Plex Sans, sans-serif", color=C["ink"], size=12),
    colorway=[C["teal"],"#8A8F98","#C4C1B9"],
    xaxis=dict(showgrid=True,gridcolor=C["rule"],zeroline=False),
    yaxis=dict(showgrid=True,gridcolor=C["rule"],zeroline=False),
    margin=dict(l=8,r=18,t=10,b=8),
))


def inject_styles():
    """Inject the custom factsheet design system once."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:wght@400;500;600&display=swap');
    :root{--paper:#FAF8F4;--ink:#1B1F2A;--teal:#0F5C5C;--brick:#A63D2F;--muted:#6B7280;--rule:#D9D6CF}
    html,body,[data-testid="stAppViewContainer"]{background:var(--paper);color:var(--ink);font-family:'IBM Plex Sans',sans-serif}
    [data-testid="stHeader"],#MainMenu,footer{visibility:hidden;height:0}
    .block-container{max-width:1440px;padding-top:1.8rem;padding-bottom:2rem}
    h1,h2,h3{font-family:'Source Serif 4',serif!important;color:var(--ink)!important;font-weight:500!important}
    h1{font-size:2.2rem!important;letter-spacing:-.02em}
    h2{font-size:1.5rem!important;border-bottom:1px solid var(--rule);padding-bottom:.4rem}
    h3{font-family:'Source Serif 4',serif!important;font-size:1.05rem!important;font-weight:600!important}
    [data-testid="stMetricLabel"]{color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-size:.68rem}
    [data-testid="stMetricValue"]{font-family:'IBM Plex Mono',monospace;font-size:1.35rem}
    [data-testid="stTabs"] button{border-radius:0;color:var(--muted);border-bottom:1px solid var(--rule)}
    [data-testid="stTabs"] button[aria-selected="true"]{color:var(--teal);border-bottom:2px solid var(--teal);background:transparent}
    [data-testid="stDataFrame"]{border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
    [data-baseweb="input"],[data-baseweb="select"]>div{border-radius:2px!important}
    .facts{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin:1rem 0 1.2rem}
    .fact{padding:.7rem .7rem .7rem 0;border-right:1px solid var(--rule);margin-right:.7rem}
    .fact:last-child{border:0}.flabel{color:var(--muted);font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;min-height:2.2em}
    .fvalue{font-family:'IBM Plex Mono',monospace;font-size:1.05rem;margin-top:.3rem;white-space:nowrap}
    .eyebrow{color:var(--muted);font-size:.68rem;letter-spacing:.12em;text-transform:uppercase}
    .foot{border-top:1px solid var(--rule);margin-top:2rem;padding-top:.7rem;color:var(--muted);font-size:.76rem}
    @media(max-width:900px){.facts{grid-template-columns:repeat(3,1fr)}}
    </style>""", unsafe_allow_html=True)
