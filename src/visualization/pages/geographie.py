"""
Page Géographie — Géographie & Télétravail (layout + callbacks).
"""

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, dcc, html

from src.visualization.components import (
    chart_card, empty_fig, make_kpi_card, make_skeleton_chart,
    make_skeleton_map, section_title, styled_fig,
)
from src.visualization.config import CITY_POPULATION, PALETTE
from src.visualization.data import _detect_remote, _read_store


def layout():
    return [

    section_title("fa-solid fa-earth-europe", "Géographie & Télétravail"),

    html.Div(id="kpi-row-geographie", style={"minHeight": "100px"}),

    dbc.Row([
        dbc.Col(
            chart_card("Coefficient Télétravail & impact salaire",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("350px"),
                           children=dcc.Graph(id="chart-remote-salary",
                                              config={"displayModeBar": False}),
                       )),
            lg=6, md=12, className="mb-4",
        ),
        dbc.Col(
            chart_card("Hubs dynamiques — Densité offres / ville",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("350px"),
                           children=dcc.Graph(id="chart-hub-density",
                                              config={"displayModeBar": False}),
                       )),
            lg=6, md=12, className="mb-4",
        ),
    ]),

    dbc.Row([
        dbc.Col(
            chart_card("Carte des offres — France",
                       dcc.Loading(
                           custom_spinner=make_skeleton_map(),
                           children=dcc.Graph(id="chart-map-geo",
                                              config={"displayModeBar": False}),
                       )),
            lg=7, md=12, className="mb-4",
        ),
        dbc.Col(
            chart_card("Top 10 villes — Nombre d'offres",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("400px"),
                           children=dcc.Graph(id="chart-top-cities",
                                              config={"displayModeBar": False}),
                       )),
            lg=5, md=12, className="mb-4",
        ),
    ]),

    ]


def register_callbacks(app):

    # ── KPIs ──────────────────────────────────────────────

    @app.callback(Output("kpi-row-geographie", "children"), Input("filtered-data", "data"))
    def update_kpis_geographie(data):
        df = _read_store(data)
        n = len(df)
        if n == 0:
            return dbc.Row([
                make_kpi_card("fa-solid fa-location-dot", "Villes", "0"),
                make_kpi_card("fa-solid fa-city", "Top ville", "N/A"),
                make_kpi_card("fa-solid fa-house-laptop", "Remote", "0%"),
                make_kpi_card("fa-solid fa-building", "Hybride", "0%"),
                make_kpi_card("fa-solid fa-map-pin", "Paris", "0%"),
            ], className="g-4 mb-4")
        n_cities = df["city_clean"].nunique() if "city_clean" in df.columns else 0
        top_city = df["city_clean"].value_counts().idxmax() if "city_clean" in df.columns and not df["city_clean"].isna().all() else "N/A"
        df_tmp = df.copy()
        df_tmp["_wm"] = df_tmp.apply(_detect_remote, axis=1)
        remote_pct = (df_tmp["_wm"] == "Full Remote").mean() * 100
        hybrid_pct = (df_tmp["_wm"] == "Hybride").mean() * 100
        paris_pct = ((df["city_clean"] == "Paris").sum() / n * 100) if "city_clean" in df.columns else 0
        return dbc.Row([
            make_kpi_card("fa-solid fa-location-dot", "Villes", f"{n_cities}"),
            make_kpi_card("fa-solid fa-city", "Top ville", top_city),
            make_kpi_card("fa-solid fa-house-laptop", "Full Remote", f"{remote_pct:.0f}%"),
            make_kpi_card("fa-solid fa-building", "Hybride", f"{hybrid_pct:.0f}%"),
            make_kpi_card("fa-solid fa-map-pin", "Paris", f"{paris_pct:.0f}%"),
        ], className="g-4 mb-4")

    # ── Remote Salary ─────────────────────────────────────

    @app.callback(Output("chart-remote-salary", "figure"), Input("filtered-data", "data"))
    def update_remote_salary(data):
        df = _read_store(data)
        if df.empty:
            return empty_fig()
        df = df.copy()
        df["work_mode"] = df.apply(_detect_remote, axis=1)
        grouped = df.groupby("work_mode").agg(
            count=("title", "size"),
            salary=("salary_avg", "mean"),
        ).reset_index()
        grouped = grouped.sort_values("count", ascending=False)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=grouped["work_mode"], y=grouped["count"],
            name="Nb offres", marker_color=PALETTE["primary"],
            yaxis="y", text=grouped["count"], textposition="outside",
            textfont=dict(size=11, family="Inter"),
        ))
        fig.add_trace(go.Scatter(
            x=grouped["work_mode"],
            y=grouped["salary"].fillna(0),
            name="Salaire moy. (€)",
            mode="lines+markers+text",
            marker=dict(size=10, color=PALETTE["danger"]),
            line=dict(color=PALETTE["danger"], width=2.5),
            text=[f"{v:,.0f}€" if pd.notna(v) else "N/A" for v in grouped["salary"]],
            textposition="top center", textfont=dict(size=11, color=PALETTE["danger"]),
            yaxis="y2",
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=20, b=40, l=60, r=60), height=370,
            yaxis=dict(title="Nombre d'offres", showgrid=True, gridcolor="#EDF2F7"),
            yaxis2=dict(title="Salaire moy. (€)", overlaying="y", side="right",
                        showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=11)),
            barmode="group",
        )
        return fig

    # ── Hub Density ───────────────────────────────────────

    @app.callback(Output("chart-hub-density", "figure"), Input("filtered-data", "data"))
    def update_hub_density(data):
        df = _read_store(data)
        if df.empty:
            return empty_fig()
        city_counts = df["city_clean"].value_counts().head(15)
        hub_data = []
        for city, count in city_counts.items():
            pop = CITY_POPULATION.get(city)
            if pop:
                ratio = count / pop * 100_000
                hub_data.append({"city": city, "offres": count, "population": pop, "ratio": ratio})
        if not hub_data:
            return empty_fig("Pas de données de population")
        hub_df = pd.DataFrame(hub_data).sort_values("ratio", ascending=True)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=hub_df["ratio"], y=hub_df["city"], orientation="h",
            marker_color=[PALETTE["danger"] if c != "Paris" and r == hub_df["ratio"].max()
                          else PALETTE["primary_light"] if c == "Paris"
                          else PALETTE["secondary"]
                          for c, r in zip(hub_df["city"], hub_df["ratio"])],
            text=[f"{r:.1f}" for r in hub_df["ratio"]], textposition="auto",
            textfont=dict(size=11, family="Inter", color=PALETTE["white"]),
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=40, l=130, r=20), height=370,
            xaxis=dict(title="Offres pour 100k habitants"),
            yaxis=dict(showgrid=False),
        )
        return fig

    # ── Map Geo ───────────────────────────────────────────

    @app.callback(Output("chart-map-geo", "figure"), Input("filtered-data", "data"))
    def update_map_geo(data):
        df = _read_store(data)
        if df.empty or "lat" not in df.columns or "lon" not in df.columns:
            return empty_fig("Aucune coordonnée disponible")
        df_geo = df.dropna(subset=["lat", "lon"])
        if df_geo.empty:
            return empty_fig("Aucune coordonnée disponible")
        geo_agg = df_geo.groupby("city_clean").agg(
            lat=("lat", "first"), lon=("lon", "first"),
            count=("title", "size"), salary=("salary_avg", "mean"),
        ).reset_index()
        fig = px.scatter_map(
            geo_agg, lat="lat", lon="lon", size="count",
            color="salary", hover_name="city_clean",
            hover_data={"count": True, "salary": ":.0f", "lat": False, "lon": False},
            color_continuous_scale="Tealgrn", size_max=40, zoom=5,
            labels={"count": "Offres", "salary": "Salaire moy. (€)"},
        )
        fig.update_traces(marker_sizemin=8)
        fig.update_layout(
            map_style="carto-positron", map_center={"lat": 46.6, "lon": 2.3},
            paper_bgcolor=PALETTE["white"],
            font=dict(family="Inter, sans-serif", color=PALETTE["dark"]),
            margin=dict(t=10, b=10, l=10, r=10), height=460,
        )
        return fig

    # ── Top Cities ────────────────────────────────────────

    @app.callback(Output("chart-top-cities", "figure"), Input("filtered-data", "data"))
    def update_top_cities(data):
        df = _read_store(data)
        if df.empty or "city_clean" not in df.columns:
            return empty_fig()
        top = df["city_clean"].value_counts().head(10)
        fig = go.Figure(go.Bar(
            x=top.values, y=top.index, orientation="h",
            marker_color=PALETTE["primary"],
            text=top.values, textposition="auto",
            textfont=dict(size=12, family="Inter", color=PALETTE["white"]),
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=40, l=120, r=20), height=460,
            yaxis=dict(autorange="reversed", showgrid=False),
            xaxis=dict(title="Nombre d'offres"),
        )
        return fig
