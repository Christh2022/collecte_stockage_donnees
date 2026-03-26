"""
Page Temporel — Analyse temporelle & fraîcheur (layout + callbacks).
"""

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, dcc, html

from src.visualization.components import (
    chart_card, empty_fig, make_kpi_card, make_skeleton_chart,
    section_title, styled_fig,
)
from src.visualization.config import PALETTE
from src.visualization.data import JOUR_FR, _read_store


def layout():
    return [

    section_title("fa-solid fa-clock", "Analyse Temporelle & Fraîcheur"),

    html.Div(id="kpi-row-temporel", style={"minHeight": "100px"}),

    dbc.Row([
        dbc.Col(
            chart_card("Jour de publication préféré",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("350px"),
                           children=dcc.Graph(id="chart-pub-weekday",
                                              config={"displayModeBar": False}),
                       )),
            lg=6, md=12, className="mb-4",
        ),
        dbc.Col(
            chart_card("Volume de publications par heure",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("350px"),
                           children=dcc.Graph(id="chart-pub-hour",
                                              config={"displayModeBar": False}),
                       )),
            lg=6, md=12, className="mb-4",
        ),
    ]),

    dbc.Row([
        dbc.Col(
            chart_card("Cumul d'offres dans le temps",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("350px"),
                           children=dcc.Graph(id="chart-cumulative",
                                              config={"displayModeBar": False}),
                       )),
            lg=6, md=12, className="mb-4",
        ),
        dbc.Col(
            chart_card("Fraîcheur des offres (âge en jours)",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("350px"),
                           children=dcc.Graph(id="chart-freshness",
                                              config={"displayModeBar": False}),
                       )),
            lg=6, md=12, className="mb-4",
        ),
    ]),

    ]


def register_callbacks(app):

    # ── KPIs ──────────────────────────────────────────────

    @app.callback(Output("kpi-row-temporel", "children"), Input("filtered-data", "data"))
    def update_kpis_temporel(data):
        df = _read_store(data)
        ts = df.dropna(subset=["published_at"])
        if ts.empty:
            return dbc.Row([
                make_kpi_card("fa-solid fa-calendar-days", "Jours couverts", "0"),
                make_kpi_card("fa-solid fa-chart-line", "Moy./jour", "0"),
                make_kpi_card("fa-solid fa-arrow-up", "Jour pic", "N/A"),
                make_kpi_card("fa-solid fa-clock", "Offres < 7j", "0"),
            ], className="g-4 mb-4")
        ts = ts.copy()
        ts["date"] = ts["published_at"].dt.date
        n_days = ts["date"].nunique()
        avg_day = len(ts) / max(n_days, 1)
        peak_day = ts["date"].value_counts().idxmax()
        now = pd.Timestamp.now(tz="UTC")
        recent = (ts["published_at"] >= now - pd.Timedelta(days=7)).sum()
        return dbc.Row([
            make_kpi_card("fa-solid fa-calendar-days", "Jours couverts", f"{n_days}"),
            make_kpi_card("fa-solid fa-chart-line", "Moy. / jour", f"{avg_day:.1f}"),
            make_kpi_card("fa-solid fa-arrow-up", "Jour pic", str(peak_day)),
            make_kpi_card("fa-solid fa-clock", "Offres < 7 jours", f"{recent}"),
        ], className="g-4 mb-4")

    # ── Weekday ───────────────────────────────────────────

    @app.callback(Output("chart-pub-weekday", "figure"), Input("filtered-data", "data"))
    def update_pub_weekday(data):
        df = _read_store(data)
        ts = df.dropna(subset=["published_at"])
        if ts.empty:
            return empty_fig("Aucune date de publication")
        ts = ts.copy()
        ts["dow"] = ts["published_at"].dt.dayofweek
        counts = ts["dow"].value_counts().reindex(range(7), fill_value=0)
        labels = [JOUR_FR[i] for i in range(7)]
        colors = [PALETTE["primary"] if v == counts.max() else PALETTE["primary_light"]
                  for v in counts.values]

        fig = go.Figure(go.Bar(
            x=labels, y=counts.values,
            marker_color=colors,
            text=counts.values, textposition="outside",
            textfont=dict(family="Inter", size=12, color=PALETTE["dark"]),
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=30, b=40, l=50, r=20), height=370,
            yaxis=dict(title="Nombre d'offres"),
        )
        peak_day = JOUR_FR[counts.idxmax()]
        fig.add_annotation(
            x=peak_day, y=counts.max(), text=f"Pic : {peak_day}",
            showarrow=True, arrowhead=2, arrowcolor=PALETTE["danger"],
            font=dict(color=PALETTE["danger"], size=12, family="Inter"),
            yshift=15,
        )
        return fig

    # ── Hour ──────────────────────────────────────────────

    @app.callback(Output("chart-pub-hour", "figure"), Input("filtered-data", "data"))
    def update_pub_hour(data):
        df = _read_store(data)
        ts = df.dropna(subset=["published_at"])
        if ts.empty:
            return empty_fig("Aucune date de publication")
        ts = ts.copy()
        ts["hour"] = ts["published_at"].dt.hour
        counts = ts["hour"].value_counts().reindex(range(24), fill_value=0)

        fig = go.Figure(go.Scatter(
            x=list(range(24)), y=counts.values,
            mode="lines+markers", fill="tozeroy",
            line=dict(color=PALETTE["primary"], width=2.5),
            marker=dict(size=6, color=PALETTE["primary"]),
            fillcolor="rgba(27,73,101,.08)",
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=20, b=40, l=50, r=20), height=370,
            xaxis=dict(title="Heure (UTC)", dtick=2),
            yaxis=dict(title="Nombre d'offres"),
        )
        return fig

    # ── Cumulative ────────────────────────────────────────

    @app.callback(Output("chart-cumulative", "figure"), Input("filtered-data", "data"))
    def update_cumulative(data):
        df = _read_store(data)
        ts = df.dropna(subset=["published_at"]).copy()
        if ts.empty:
            return empty_fig("Aucune date de publication")
        ts["date"] = ts["published_at"].dt.date
        daily = ts.groupby("date").size().reset_index(name="count")
        daily["date"] = pd.to_datetime(daily["date"])
        daily = daily.sort_values("date")
        daily["cumul"] = daily["count"].cumsum()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["cumul"], mode="lines", fill="tozeroy",
            line=dict(color=PALETTE["primary"], width=2.5),
            fillcolor="rgba(27,73,101,.10)",
            hovertemplate="<b>%{x|%d %b}</b><br>Cumul: %{y}<extra></extra>",
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=40, l=60, r=20), height=370,
            xaxis=dict(title="Date"), yaxis=dict(title="Offres cumulées"),
        )
        return fig

    # ── Freshness ─────────────────────────────────────────

    @app.callback(Output("chart-freshness", "figure"), Input("filtered-data", "data"))
    def update_freshness(data):
        df = _read_store(data)
        ts = df.dropna(subset=["published_at"]).copy()
        if ts.empty:
            return empty_fig("Aucune date de publication")
        now = pd.Timestamp.now(tz="UTC")
        ts["age_days"] = (now - ts["published_at"]).dt.total_seconds() / 86400
        bins = [0, 1, 3, 7, 14, 30, 999]
        labels_b = ["< 1j", "1-3j", "3-7j", "7-14j", "14-30j", "> 30j"]
        ts["bucket"] = pd.cut(ts["age_days"], bins=bins, labels=labels_b, right=True)
        counts = ts["bucket"].value_counts().reindex(labels_b, fill_value=0)
        colors = [PALETTE["success"], PALETTE["success"], PALETTE["primary"],
                  PALETTE["primary_light"], PALETTE["warning"], PALETTE["danger"]]
        fig = go.Figure(go.Bar(
            x=counts.index.tolist(), y=counts.values,
            marker_color=colors, text=counts.values, textposition="outside",
            textfont=dict(size=12, family="Inter"),
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=20, b=40, l=50, r=20), height=370,
            yaxis=dict(title="Nombre d'offres"),
        )
        return fig
