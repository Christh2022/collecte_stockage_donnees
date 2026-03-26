"""
Page Salaires — Analyse salariale & premium compétences (layout + callbacks).
"""

import re

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, dcc, html

from src.visualization.components import (
    chart_card, empty_fig, make_kpi_card, make_skeleton_chart,
    section_title, styled_fig,
)
from src.visualization.config import PALETTE, PLOT_COLORS
from src.visualization.data import _read_store, _text_blob


def layout():
    return [

    section_title("fa-solid fa-coins", "Analyse Salaires — Premium compétences"),

    html.Div(id="kpi-row-salaires", style={"minHeight": "100px"}),

    dbc.Row([
        dbc.Col(
            chart_card("Premium salarial par compétence",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("380px"),
                           children=dcc.Graph(id="chart-skill-premium",
                                              config={"displayModeBar": False}),
                       )),
            lg=7, md=12, className="mb-4",
        ),
        dbc.Col(
            chart_card("Salaire moyen par source",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("380px"),
                           children=dcc.Graph(id="chart-salary-source",
                                              config={"displayModeBar": False}),
                       )),
            lg=5, md=12, className="mb-4",
        ),
    ]),

    dbc.Row([
        dbc.Col(
            chart_card("Salaire moyen par ville (Top 10)",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("380px"),
                           children=dcc.Graph(id="chart-salary-city",
                                              config={"displayModeBar": False}),
                       )),
            lg=6, md=12, className="mb-4",
        ),
        dbc.Col(
            chart_card("Distribution salariale par contrat",
                       dcc.Loading(
                           custom_spinner=make_skeleton_chart("380px"),
                           children=dcc.Graph(id="chart-salary-boxplot",
                                              config={"displayModeBar": False}),
                       )),
            lg=6, md=12, className="mb-4",
        ),
    ]),

    ]


def register_callbacks(app):

    # ── KPIs ──────────────────────────────────────────────

    @app.callback(Output("kpi-row-salaires", "children"), Input("filtered-data", "data"))
    def update_kpis_salaires(data):
        df = _read_store(data)
        df_sal = df.dropna(subset=["salary_avg"])
        if df_sal.empty:
            return dbc.Row([
                make_kpi_card("fa-solid fa-euro-sign", "Salaire moyen", "N/A"),
                make_kpi_card("fa-solid fa-arrow-down", "Salaire min", "N/A"),
                make_kpi_card("fa-solid fa-arrow-up", "Salaire max", "N/A"),
                make_kpi_card("fa-solid fa-chart-simple", "Médiane", "N/A"),
                make_kpi_card("fa-solid fa-percent", "% avec salaire", "0%"),
            ], className="g-4 mb-4")
        avg = df_sal["salary_avg"].mean()
        mn = df_sal["salary_min"].min()
        mx = df_sal["salary_max"].max()
        med = df_sal["salary_avg"].median()
        pct_sal = len(df_sal) / len(df) * 100 if len(df) > 0 else 0
        return dbc.Row([
            make_kpi_card("fa-solid fa-euro-sign", "Salaire moyen", f"{avg:,.0f} €"),
            make_kpi_card("fa-solid fa-arrow-down", "Salaire min", f"{mn:,.0f} €" if pd.notna(mn) else "N/A"),
            make_kpi_card("fa-solid fa-arrow-up", "Salaire max", f"{mx:,.0f} €" if pd.notna(mx) else "N/A"),
            make_kpi_card("fa-solid fa-chart-simple", "Médiane", f"{med:,.0f} €"),
            make_kpi_card("fa-solid fa-percent", "% avec salaire", f"{pct_sal:.0f}%"),
        ], className="g-4 mb-4")

    # ── Skill Premium ─────────────────────────────────────

    @app.callback(Output("chart-skill-premium", "figure"), Input("filtered-data", "data"))
    def update_skill_premium(data):
        df = _read_store(data)
        df_sal = df.dropna(subset=["salary_avg"])
        if df_sal.empty or len(df_sal) < 3:
            return empty_fig("Pas assez de données salariales")
        global_avg = df_sal["salary_avg"].mean()

        # Parse tech_stack (comma-separated) for each salary row
        def _has_skill(tech_stack, skill):
            if not isinstance(tech_stack, str):
                return False
            return skill in [s.strip().lower() for s in tech_stack.split(",")]

        # Discover top skills from ALL filtered rows (not just salary ones)
        from collections import Counter
        all_skills = []
        ts_col = df["tech_stack"].dropna()
        for v in ts_col:
            if isinstance(v, str):
                all_skills.extend([s.strip().lower() for s in v.split(",") if s.strip()])
        top_skills = [s for s, _ in Counter(all_skills).most_common(20)]

        premiums = []
        for skill in top_skills:
            mask = df_sal["tech_stack"].apply(lambda ts: _has_skill(ts, skill))
            n_match = mask.sum()
            if n_match >= 2:
                avg_skill = df_sal.loc[mask, "salary_avg"].mean()
                premium = ((avg_skill - global_avg) / global_avg) * 100
                premiums.append({"skill": skill.title(), "premium": premium,
                                 "count": int(n_match), "avg_salary": avg_skill})

        if not premiums:
            # Fallback: try description + tech_stack blob with threshold = 1
            blob = _text_blob(df_sal)
            fallback_skills = ["Python", "R", "SQL", "Machine Learning", "Docker",
                               "AWS", "Java", "Kubernetes", "CI/CD", "Power BI"]
            for skill in fallback_skills:
                mask = blob.str.contains(re.escape(skill.lower()), case=False, na=False)
                n_match = mask.sum()
                if n_match >= 1:
                    avg_skill = df_sal.loc[mask, "salary_avg"].mean()
                    premium = ((avg_skill - global_avg) / global_avg) * 100
                    premiums.append({"skill": skill, "premium": premium,
                                     "count": int(n_match), "avg_salary": avg_skill})

        if not premiums:
            return empty_fig("Pas assez de données par compétence")

        prem_df = pd.DataFrame(premiums).sort_values("premium", ascending=True).tail(15)
        colors = [PALETTE["success"] if p >= 0 else PALETTE["danger"] for p in prem_df["premium"]]

        fig = go.Figure(go.Bar(
            x=prem_df["premium"], y=prem_df["skill"], orientation="h",
            marker_color=colors,
            text=[f"{p:+.1f}%" for p in prem_df["premium"]], textposition="outside",
            textfont=dict(family="Inter", size=12),
            customdata=np.stack([prem_df["count"], prem_df["avg_salary"]], axis=-1),
            hovertemplate="<b>%{y}</b><br>Premium: %{x:.1f}%<br>"
                          "Offres: %{customdata[0]}<br>"
                          "Salaire moy: %{customdata[1]:,.0f}€<extra></extra>",
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=40, l=100, r=60),
            height=max(300, len(prem_df) * 35 + 80),
            xaxis=dict(title="Premium vs moyenne globale (%)", zeroline=True,
                       zerolinecolor=PALETTE["muted"], zerolinewidth=1.5),
            yaxis=dict(showgrid=False),
        )
        fig.add_vline(x=0, line_dash="dot", line_color=PALETTE["muted"], line_width=1)
        return fig

    # ── Salary Source ─────────────────────────────────────

    @app.callback(Output("chart-salary-source", "figure"), Input("filtered-data", "data"))
    def update_salary_source(data):
        df = _read_store(data)
        if "source" not in df.columns:
            return empty_fig("Colonne 'source' absente")
        df_sal = df.dropna(subset=["salary_avg"])
        if df_sal.empty:
            return empty_fig("Aucune donnée salariale")
        grouped = df_sal.groupby("source").agg(
            salary_avg=("salary_avg", "mean"),
            salary_med=("salary_avg", "median"),
            count=("title", "size"),
        ).reset_index()
        grouped = grouped.sort_values("salary_avg", ascending=True)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=grouped["source"], x=grouped["salary_avg"], orientation="h",
            name="Moyenne", marker_color=PALETTE["primary"],
            text=[f"{v:,.0f}€" for v in grouped["salary_avg"]], textposition="auto",
            textfont=dict(size=12, family="Inter", color=PALETTE["white"]),
        ))
        fig.add_trace(go.Bar(
            y=grouped["source"], x=grouped["salary_med"], orientation="h",
            name="Médiane", marker_color=PALETTE["secondary"],
            text=[f"{v:,.0f}€" for v in grouped["salary_med"]], textposition="auto",
            textfont=dict(size=12, family="Inter", color=PALETTE["white"]),
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=40, l=100, r=20), height=400,
            xaxis=dict(title="Salaire (€)"), yaxis=dict(showgrid=False),
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=11)),
        )
        return fig

    # ── Salary City ───────────────────────────────────────

    @app.callback(Output("chart-salary-city", "figure"), Input("filtered-data", "data"))
    def update_salary_city(data):
        df = _read_store(data)
        df_sal = df.dropna(subset=["salary_avg"])
        if df_sal.empty or "city_clean" not in df_sal.columns:
            return empty_fig("Pas assez de données salariales")
        city_sal = df_sal.groupby("city_clean").agg(
            avg=("salary_avg", "mean"), count=("title", "size"),
        ).reset_index()
        city_sal = city_sal[city_sal["count"] >= 3].sort_values("avg", ascending=True).tail(10)
        if city_sal.empty:
            return empty_fig("Pas assez d'offres par ville")
        fig = go.Figure(go.Bar(
            x=city_sal["avg"], y=city_sal["city_clean"], orientation="h",
            marker_color=PALETTE["primary"],
            text=[f"{v:,.0f}€" for v in city_sal["avg"]], textposition="auto",
            textfont=dict(size=12, family="Inter", color=PALETTE["white"]),
            customdata=city_sal["count"],
            hovertemplate="<b>%{y}</b><br>Salaire moy: %{x:,.0f}€<br>Offres: %{customdata}<extra></extra>",
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=40, l=130, r=20), height=400,
            xaxis=dict(title="Salaire moyen (€)"), yaxis=dict(showgrid=False),
        )
        return fig

    # ── Salary Boxplot ────────────────────────────────────

    @app.callback(Output("chart-salary-boxplot", "figure"), Input("filtered-data", "data"))
    def update_salary_boxplot(data):
        df = _read_store(data)
        df_sal = df.dropna(subset=["salary_avg"])
        if df_sal.empty or "contract_type" not in df_sal.columns:
            return empty_fig("Pas assez de données salariales")
        fig = px.box(
            df_sal, x="contract_type", y="salary_avg",
            color="contract_type", color_discrete_sequence=PLOT_COLORS,
            labels={"salary_avg": "Salaire moyen (€)", "contract_type": "Contrat"},
        )
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=40, l=60, r=20), height=400,
            showlegend=False,
        )
        return fig
