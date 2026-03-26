"""
Page Qualité — Data Health (layout + callbacks).
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash_bootstrap_components as dbc
from dash import Input, Output, dcc, html

from src.visualization.components import (
    chart_card, empty_fig, make_kpi_card, make_skeleton_chart,
    section_title, styled_fig,
)
from src.visualization.config import PALETTE, PLOT_COLORS
from src.visualization.data import _read_store


def layout():
    return [

        section_title("fa-solid fa-heart-pulse", "Data Health — Qualité des données"),

        html.Div(id="kpi-row-qualite", style={"minHeight": "100px"}),

        dbc.Row([
            dbc.Col(
                chart_card("Taux de complétude par champ",
                           dcc.Loading(
                               custom_spinner=make_skeleton_chart("350px"),
                               children=dcc.Graph(id="chart-completeness",
                                                  config={"displayModeBar": False}),
                           )),
                lg=6, md=12, className="mb-4",
            ),
            dbc.Col(
                chart_card("Répartition par source & dédoublonnage",
                           dcc.Loading(
                               custom_spinner=make_skeleton_chart("350px"),
                               children=dcc.Graph(id="chart-source-dedup",
                                                  config={"displayModeBar": False}),
                           )),
                lg=6, md=12, className="mb-4",
            ),
        ]),

        dbc.Row([
            dbc.Col(
                chart_card("Valeurs manquantes — Heatmap",
                           dcc.Loading(
                               custom_spinner=make_skeleton_chart("350px"),
                               children=dcc.Graph(id="chart-missing-heatmap",
                                                  config={"displayModeBar": False}),
                           )),
                lg=6, md=12, className="mb-4",
            ),
            dbc.Col(
                chart_card("Volume par source & fraîcheur",
                           dcc.Loading(
                               custom_spinner=make_skeleton_chart("350px"),
                               children=dcc.Graph(id="chart-source-freshness",
                                                  config={"displayModeBar": False}),
                           )),
                lg=6, md=12, className="mb-4",
            ),
        ]),

    ]


def register_callbacks(app):

    # ── KPIs ──────────────────────────────────────────────

    @app.callback(Output("kpi-row-qualite", "children"), Input("filtered-data", "data"))
    def update_kpis_qualite(data):
        df = _read_store(data)
        n = len(df)
        if n == 0:
            return dbc.Row([
                make_kpi_card("fa-solid fa-database", "Total lignes", "0"),
                make_kpi_card("fa-solid fa-check-circle", "Complétude moy.", "0%"),
                make_kpi_card("fa-solid fa-clone", "Doublons", "0"),
                make_kpi_card("fa-solid fa-layer-group", "Sources", "0"),
            ], className="g-4 mb-4")
        fields = ["title", "company", "city", "contract_type", "salary_avg",
                  "description", "tech_stack", "published_at"]
        rates = []
        for col in fields:
            if col in df.columns:
                rates.append((df[col].notna() & (df[col].astype(str).str.strip() != "")).mean() * 100)
        avg_completeness = np.mean(rates) if rates else 0
        df_dedup = df.copy()
        df_dedup["_key"] = (
            df_dedup["company"].fillna("").str.lower().str.strip() + "|" +
            df_dedup["title"].fillna("").str.lower().str.strip().str[:40] + "|" +
            df_dedup["city_clean"].fillna("").str.lower().str.strip()
        )
        duplicates = n - df_dedup["_key"].nunique()
        n_sources = df["source"].nunique() if "source" in df.columns else 1
        return dbc.Row([
            make_kpi_card("fa-solid fa-database", "Total lignes", f"{n:,}"),
            make_kpi_card("fa-solid fa-check-circle", "Complétude moy.", f"{avg_completeness:.0f}%"),
            make_kpi_card("fa-solid fa-clone", "Doublons potentiels", f"{duplicates}"),
            make_kpi_card("fa-solid fa-layer-group", "Sources", f"{n_sources}"),
        ], className="g-4 mb-4")

    # ── Completeness ──────────────────────────────────────

    @app.callback(Output("chart-completeness", "figure"), Input("filtered-data", "data"))
    def update_completeness(data):
        df = _read_store(data)
        if df.empty:
            return empty_fig()
        fields = {
            "Titre": "title", "Entreprise": "company", "Ville": "city",
            "Type contrat": "contract_type", "Salaire": "salary_avg",
            "Description": "description", "Tech Stack": "tech_stack",
            "Date publication": "published_at", "URL": "url", "Source": "source",
        }
        rates = []
        for label, col in fields.items():
            if col in df.columns:
                filled = df[col].notna() & (df[col].astype(str).str.strip() != "")
                pct = filled.mean() * 100
            else:
                pct = 0.0
            rates.append({"Champ": label, "Complétude (%)": pct})

        rate_df = pd.DataFrame(rates).sort_values("Complétude (%)", ascending=True)
        colors = [PALETTE["success"] if v >= 80 else PALETTE["warning"] if v >= 50
                  else PALETTE["danger"] for v in rate_df["Complétude (%)"]]

        fig = go.Figure(go.Bar(
            x=rate_df["Complétude (%)"], y=rate_df["Champ"], orientation="h",
            marker_color=colors,
            text=[f"{v:.0f}%" for v in rate_df["Complétude (%)"]],
            textposition="auto",
            textfont=dict(family="Inter", size=12, color=PALETTE["white"]),
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=40, l=110, r=20), height=370,
            xaxis=dict(title="% de complétude", range=[0, 105]),
            yaxis=dict(showgrid=False),
        )
        fig.add_vline(x=80, line_dash="dash", line_color=PALETTE["muted"], line_width=1,
                      annotation_text="Seuil 80%", annotation_font=dict(size=10, color=PALETTE["muted"]))
        return fig

    # ── Source Dedup ──────────────────────────────────────

    @app.callback(Output("chart-source-dedup", "figure"), Input("filtered-data", "data"))
    def update_source_dedup(data):
        df = _read_store(data)
        if df.empty:
            return empty_fig()

        if "source" in df.columns:
            source_counts = df["source"].fillna("Inconnue").value_counts()
        else:
            source_counts = pd.Series({"Adzuna": len(df)})

        df_dedup = df.copy()
        df_dedup["_key"] = (
            df_dedup["company"].fillna("").str.lower().str.strip() + "|" +
            df_dedup["title"].fillna("").str.lower().str.strip().str[:40] + "|" +
            df_dedup["city_clean"].fillna("").str.lower().str.strip()
        )
        total = len(df_dedup)
        unique = df_dedup["_key"].nunique()
        duplicates = total - unique

        fig = make_subplots(
            rows=1, cols=2, specs=[[{"type": "pie"}, {"type": "bar"}]],
            subplot_titles=["Répartition par source", "Dédoublonnage"],
            horizontal_spacing=0.15,
        )
        fig.add_trace(go.Pie(
            labels=source_counts.index.tolist(), values=source_counts.values.tolist(),
            hole=0.45, marker=dict(colors=PLOT_COLORS),
            textinfo="percent+label", textfont=dict(size=11),
        ), row=1, col=1)

        fig.add_trace(go.Bar(
            x=["Uniques", "Doublons potentiels"],
            y=[unique, duplicates],
            marker_color=[PALETTE["success"], PALETTE["danger"]],
            text=[f"{unique}", f"{duplicates}"], textposition="outside",
            textfont=dict(size=13, family="Inter"),
        ), row=1, col=2)

        fig.update_layout(
            template="plotly_white",
            font=dict(family="Inter, sans-serif", color=PALETTE["dark"]),
            paper_bgcolor=PALETTE["white"], plot_bgcolor=PALETTE["white"],
            margin=dict(t=40, b=20, l=20, r=20), height=370,
            showlegend=False,
        )
        fig.update_annotations(font=dict(size=13, family="Inter", color=PALETTE["dark"]))
        return fig

    # ── Missing Heatmap ───────────────────────────────────

    @app.callback(Output("chart-missing-heatmap", "figure"), Input("filtered-data", "data"))
    def update_missing_heatmap(data):
        df = _read_store(data)
        if df.empty:
            return empty_fig()
        cols_check = ["title", "company", "city", "contract_type", "salary_avg",
                      "salary_min", "salary_max", "description", "tech_stack",
                      "published_at", "url", "source"]
        present = [c for c in cols_check if c in df.columns]
        if not present:
            return empty_fig()
        missing_pct = df[present].isna().mean() * 100
        filled_pct = 100 - missing_pct
        fig_df = pd.DataFrame({"Champ": present, "Rempli (%)": filled_pct.values, "Manquant (%)": missing_pct.values})
        fig_df = fig_df.sort_values("Rempli (%)", ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=fig_df["Champ"], x=fig_df["Rempli (%)"], orientation="h",
            name="Rempli", marker_color=PALETTE["success"],
            text=[f"{v:.0f}%" for v in fig_df["Rempli (%)"]], textposition="auto",
            textfont=dict(size=11, color=PALETTE["white"]),
        ))
        fig.add_trace(go.Bar(
            y=fig_df["Champ"], x=fig_df["Manquant (%)"], orientation="h",
            name="Manquant", marker_color=PALETTE["danger"],
            text=[f"{v:.0f}%" for v in fig_df["Manquant (%)"]], textposition="auto",
            textfont=dict(size=11, color=PALETTE["white"]),
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=40, l=110, r=20), height=370,
            barmode="stack", xaxis=dict(title="% du total", range=[0, 105]),
            yaxis=dict(showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
        )
        return fig

    # ── Source Freshness ──────────────────────────────────

    @app.callback(Output("chart-source-freshness", "figure"), Input("filtered-data", "data"))
    def update_source_freshness(data):
        df = _read_store(data)
        if df.empty:
            return empty_fig()
        src_col = "source" if "source" in df.columns else None
        if not src_col:
            return empty_fig("Colonne 'source' absente")
        ts = df.dropna(subset=["published_at"]).copy()
        if ts.empty:
            return empty_fig("Aucune date")
        now = pd.Timestamp.now(tz="UTC")
        ts["age_days"] = (now - ts["published_at"]).dt.total_seconds() / 86400
        grouped = ts.groupby(src_col).agg(
            count=("title", "size"),
            avg_age=("age_days", "mean"),
            min_age=("age_days", "min"),
        ).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=grouped[src_col], y=grouped["count"],
            name="Nb offres", marker_color=PALETTE["primary"],
            text=grouped["count"], textposition="outside",
            textfont=dict(size=12, family="Inter"),
            yaxis="y",
        ))
        fig.add_trace(go.Scatter(
            x=grouped[src_col], y=grouped["avg_age"],
            name="Âge moyen (jours)", mode="lines+markers+text",
            marker=dict(size=10, color=PALETTE["danger"]),
            line=dict(color=PALETTE["danger"], width=2.5),
            text=[f"{v:.0f}j" for v in grouped["avg_age"]],
            textposition="top center", textfont=dict(size=11, color=PALETTE["danger"]),
            yaxis="y2",
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=20, b=40, l=60, r=60), height=370,
            yaxis=dict(title="Nombre d'offres"),
            yaxis2=dict(title="Âge moyen (jours)", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
        )
        return fig
