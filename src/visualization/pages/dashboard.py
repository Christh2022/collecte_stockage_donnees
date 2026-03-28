"""
Page Dashboard — Vue d'ensemble (layout + callbacks).
"""

import time
from collections import Counter

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Input, Output, dash_table, dcc, html

from src.visualization.components import (
    build_bokeh_timeseries, chart_card, empty_fig, make_kpi_card,
    make_salary_card, make_skeleton_chart, make_skeleton_kpi_row,
    make_skeleton_map, make_skeleton_table, styled_fig,
)
from src.visualization.config import PALETTE, SKELETON_DELAY
from src.visualization.data import _read_store


def layout():
    return [

        # KPI Row
        dcc.Loading(
            id="loading-kpis",
            custom_spinner=make_skeleton_kpi_row(),
            children=html.Div(id="kpi-row", style={"minHeight": "130px"}),
            className="mb-4"
        ),

        # Charts Row 1: Histogram + Pie
        dbc.Row([
            dbc.Col(
                chart_card("Distribution des salaires",
                           dcc.Loading(
                               id="loading-hist",
                               custom_spinner=make_skeleton_chart("350px"),
                               children=dcc.Graph(id="chart-salary-hist",
                                                  config={"displayModeBar": False}),
                           )),
                lg=7, md=12, className="mb-4",
            ),
            dbc.Col(
                chart_card("Répartition des contrats",
                           dcc.Loading(
                               id="loading-pie",
                               custom_spinner=make_skeleton_chart("320px"),
                               children=dcc.Graph(id="chart-contract-pie",
                                                  config={"displayModeBar": False}),
                           )),
                lg=5, md=12, className="mb-4",
            ),
        ]),

        # Map
        dbc.Row([
            dbc.Col(
                chart_card("Carte des offres — France",
                           dcc.Loading(
                               id="loading-map",
                               custom_spinner=make_skeleton_map(),
                               children=dcc.Graph(id="chart-map",
                                                  config={"displayModeBar": False}),
                           )),
                width=12, className="mb-4",
            ),
        ]),

        # Charts Row 2: Skills + Bokeh
        dbc.Row([
            dbc.Col(
                chart_card("Top 15 Compétences",
                           dcc.Loading(
                               id="loading-skills",
                               custom_spinner=make_skeleton_chart("350px"),
                               children=dcc.Graph(id="chart-skills",
                                                  config={"displayModeBar": False}),
                           )),
                lg=6, md=12, className="mb-4",
            ),
            dbc.Col(
                chart_card("Évolution des publications",
                           dcc.Loading(
                               id="loading-bokeh",
                               custom_spinner=make_skeleton_chart("350px"),
                               children=html.Iframe(id="bokeh-chart", style={
                                   "width": "100%", "height": "380px",
                                   "border": "none", "borderRadius": "8px",
                               }),
                           )),
                lg=6, md=12, className="mb-4",
            ),
        ]),

        # Table
        dbc.Row([
            dbc.Col(
                chart_card("Offres détaillées",
                           dcc.Loading(
                               id="loading-table",
                               custom_spinner=make_skeleton_table(),
                               children=dash_table.DataTable(
                                   id="data-table",
                                   columns=[
                                       {"name": "Titre", "id": "title"},
                                       {"name": "Entreprise", "id": "company"},
                                       {"name": "Ville", "id": "city_clean"},
                                       {"name": "Contrat", "id": "contract_type"},
                                       {"name": "Salaire moy.", "id": "salary_avg",
                                        "type": "numeric"},
                                       {"name": "Tech Stack", "id": "tech_stack"},
                                   ],
                                   page_size=12, sort_action="native",
                                   filter_action="native",
                                   style_table={"overflowX": "auto"},
                                   style_header={
                                       "backgroundColor": PALETTE["primary"],
                                       "color": PALETTE["white"],
                                       "fontWeight": "600",
                                       "fontSize": "12px",
                                       "textTransform": "uppercase",
                                       "letterSpacing": "0.5px",
                                       "border": "none",
                                       "padding": "12px",
                                   },
                                   style_cell={
                                       "backgroundColor": PALETTE["white"],
                                       "color": PALETTE["dark"],
                                       "border": f"1px solid {PALETTE['light_bg']}",
                                       "padding": "10px 14px",
                                       "fontSize": "13px",
                                       "maxWidth": "260px",
                                       "overflow": "hidden",
                                       "textOverflow": "ellipsis",
                                       "fontFamily": "Inter, sans-serif",
                                       "textAlign": "left",
                                   },
                                   style_data_conditional=[
                                       {"if": {"row_index": "odd"},
                                        "backgroundColor": "#F1F5F9"},
                                   ],
                                   style_filter={
                                       "backgroundColor": "#F1F5F9",
                                       "fontSize": "12px",
                                   },
                               ),
                           )),
                width=12, className="mb-4",
            ),
        ]),

    ]


def register_callbacks(app):

    @app.callback(Output("kpi-row", "children"), Input("filtered-data", "data"))
    def update_kpis(data):
        if SKELETON_DELAY:
            time.sleep(SKELETON_DELAY * 0.3)
        df = _read_store(data)
        n = len(df)
        if n == 0:
            row1 = dbc.Row([
                make_kpi_card("fa-solid fa-briefcase", "Offres totales", "0"),
                make_kpi_card("fa-solid fa-euro-sign", "Salaire moyen", "N/A"),
                make_salary_card(None, None, None),
                make_kpi_card("fa-solid fa-file-contract", "CDI", "0 (0%)", card_id="kpi-card-cdi"),
                make_kpi_card("fa-solid fa-graduation-cap", "Stages", "0 (0%)", card_id="kpi-card-stage"),
                make_kpi_card("fa-solid fa-user-graduate", "Alternances", "0 (0%)", card_id="kpi-card-alternance"),
            ], className="g-4 mb-4")
            row2 = dbc.Row([
                make_kpi_card("fa-solid fa-building", "Entreprises", "0"),
                make_kpi_card("fa-solid fa-location-dot", "Villes", "0"),
                make_kpi_card("fa-solid fa-microchip", "Tech-stack", "0"),
            ], className="g-4")
            return [row1, row2]
        avg = df["salary_avg"].mean()
        median = df["salary_avg"].median()
        sal_min = df["salary_min"].min()
        sal_max = df["salary_max"].max()
        cdi_count = (df["contract_type"] == "CDI").sum()
        cdi_pct = (cdi_count / n * 100) if n > 0 else 0
        stage_count = (df["contract_type"] == "Stage").sum()
        stage_pct = (stage_count / n * 100) if n > 0 else 0
        alt_count = (df["contract_type"] == "Alternance").sum()
        alt_pct = (alt_count / n * 100) if n > 0 else 0

        row1 = dbc.Row([
            make_kpi_card("fa-solid fa-briefcase", "Offres totales",
                          f"{n:,}"),
            make_kpi_card("fa-solid fa-euro-sign", "Salaire moyen",
                          f"{avg:,.0f} €" if pd.notna(avg) else "N/A"),
            make_salary_card(median, sal_min, sal_max),
            make_kpi_card("fa-solid fa-file-contract", "CDI",
                          f"{cdi_count} ({cdi_pct:.0f}%)",
                          card_id="kpi-card-cdi"),
            make_kpi_card("fa-solid fa-graduation-cap", "Stages",
                          f"{stage_count} ({stage_pct:.0f}%)",
                          card_id="kpi-card-stage"),
            make_kpi_card("fa-solid fa-user-graduate", "Alternances",
                          f"{alt_count} ({alt_pct:.0f}%)",
                          card_id="kpi-card-alternance"),
        ], className="g-4 mb-4")

        row2 = dbc.Row([
            make_kpi_card("fa-solid fa-building", "Entreprises",
                          f"{df['company'].nunique():,}"),
            make_kpi_card("fa-solid fa-location-dot", "Villes",
                          f"{df['city_clean'].nunique()}"),
            make_kpi_card("fa-solid fa-microchip", "Tech-stack",
                          f"{(df['tech_stack'].fillna('') != '').sum()}"),
        ], className="g-4")

        return [row1, row2]

    @app.callback(
        Output("filter-contract", "value"),
        [Input("kpi-card-cdi", "n_clicks"),
         Input("kpi-card-stage", "n_clicks"),
         Input("kpi-card-alternance", "n_clicks")],
        prevent_initial_call=True,
    )
    def filter_by_contract_click(cdi_clicks, stage_clicks, alt_clicks):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update
        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
        mapping = {
            "kpi-card-cdi": "CDI",
            "kpi-card-stage": "Stage",
            "kpi-card-alternance": "Alternance",
        }
        return mapping.get(trigger_id, "ALL")

    @app.callback(Output("chart-salary-hist", "figure"), Input("filtered-data", "data"))
    def update_histogram(data):
        if SKELETON_DELAY:
            time.sleep(SKELETON_DELAY * 0.6)
        df = _read_store(data)
        df_sal = df.dropna(subset=["salary_avg"])
        if df_sal.empty:
            return empty_fig("Aucune donnée salariale")
        avg = df_sal["salary_avg"].mean()
        fig = px.histogram(
            df_sal, x="salary_avg", nbins=25,
            labels={"salary_avg": "Salaire moyen (€)", "count": "Nombre d'offres"},
            color_discrete_sequence=[PALETTE["primary"]],
        )
        fig = styled_fig(fig)
        fig.update_layout(bargap=0.06)
        fig.add_vline(x=avg, line_dash="dash", line_color=PALETTE["danger"],
                      annotation_text=f"Moy: {avg:,.0f} €",
                      annotation_font=dict(color=PALETTE["danger"], size=12,
                                           family="Inter"))
        return fig

    @app.callback(Output("chart-contract-pie", "figure"), Input("filtered-data", "data"))
    def update_pie(data):
        if SKELETON_DELAY:
            time.sleep(SKELETON_DELAY * 0.5)
        df = _read_store(data)
        if df.empty or "contract_type" not in df.columns:
            return empty_fig("Aucune donnée")

        # ── Normaliser les types de contrat ───────────────
        raw = df["contract_type"].fillna("Non précisé").str.strip().str.lower()
        mapping = {
            "cdi": "CDI", "contrat à durée indéterminée": "CDI",
            "cdd": "CDD", "contrat à durée déterminée": "CDD",
            "stage": "Stage", "internship": "Stage",
            "alternance": "Alternance", "apprentissage": "Alternance",
            "freelance": "Freelance", "indépendant": "Freelance",
            "interim": "Intérim", "intérim": "Intérim",
            "non précisé": "Non précisé", "": "Non précisé",
        }

        def _norm(val):
            if val in mapping:
                return mapping[val]
            for key, label in mapping.items():
                if key in val:
                    return label
            return "Autre"

        clean = raw.map(_norm)
        counts = clean.value_counts()

        # ── Regrouper les catégories < 2% dans "Autre" ───
        total = counts.sum()
        main = counts[counts / total >= 0.02]
        other = counts[counts / total < 0.02].sum()
        if other > 0:
            main["Autre"] = main.get("Autre", 0) + other

        # ── Couleurs fixes par catégorie ──────────────────
        color_map = {
            "CDI": PALETTE["primary"],
            "CDD": PALETTE["warning"],
            "Stage": PALETTE["secondary"],
            "Alternance": PALETTE["success"],
            "Freelance": "#E9C46A",
            "Intérim": "#264653",
            "Non précisé": PALETTE["muted"],
            "Autre": "#BEE9E8",
        }

        fig = px.pie(
            names=main.index, values=main.values,
            color=main.index,
            color_discrete_map=color_map,
            hole=0.45,
        )
        fig.update_layout(
            template="plotly_white",
            font=dict(family="Inter, sans-serif", color=PALETTE["dark"]),
            paper_bgcolor=PALETTE["white"],
            margin=dict(t=10, b=30, l=10, r=10),
            legend=dict(
                font=dict(size=12),
                orientation="h",
                yanchor="bottom", y=-0.15,
                xanchor="center", x=0.5,
            ),
        )
        fig.update_traces(
            textinfo="percent+label",
            textfont_size=12,
            textposition="inside",
            insidetextorientation="radial",
            marker=dict(line=dict(color=PALETTE["white"], width=2)),
            pull=[0.03 if v == main.values.max() else 0 for v in main.values],
        )
        return fig

    @app.callback(Output("chart-map", "figure"), Input("filtered-data", "data"))
    def update_map(data):
        if SKELETON_DELAY:
            time.sleep(SKELETON_DELAY * 0.8)
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
            margin=dict(t=10, b=10, l=10, r=10), height=500,
        )
        return fig

    @app.callback(Output("chart-skills", "figure"), Input("filtered-data", "data"))
    def update_skills(data):
        if SKELETON_DELAY:
            time.sleep(SKELETON_DELAY * 0.7)
        df = _read_store(data)
        if df.empty or "tech_stack" not in df.columns:
            return empty_fig("Aucune compétence extraite")
        all_skills = []
        for stack in df["tech_stack"].dropna():
            if stack.strip():
                all_skills.extend([s.strip() for s in stack.split(",") if s.strip()])
        skill_counts = Counter(all_skills).most_common(15)
        if not skill_counts:
            return empty_fig("Aucune compétence extraite")
        sk_df = pd.DataFrame(skill_counts, columns=["skill", "count"])
        fig = px.bar(
            sk_df, x="count", y="skill", orientation="h",
            labels={"count": "Mentions", "skill": ""},
            color="count", color_continuous_scale="Teal",
        )
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=30, l=120, r=20),
            yaxis=dict(autorange="reversed", showgrid=False),
            showlegend=False, coloraxis_showscale=False,
        )
        return fig

    @app.callback(Output("bokeh-chart", "srcDoc"), Input("filtered-data", "data"))
    def update_bokeh(data):
        if SKELETON_DELAY:
            time.sleep(SKELETON_DELAY * 0.9)
        df = _read_store(data)
        return build_bokeh_timeseries(df)

    @app.callback(Output("data-table", "data"), Input("filtered-data", "data"))
    def update_table(data):
        if SKELETON_DELAY:
            time.sleep(SKELETON_DELAY * 1.0)
        df = _read_store(data)
        cols = ["title", "company", "city_clean", "contract_type", "salary_avg", "tech_stack"]
        return df[[c for c in cols if c in df.columns]].to_dict("records")
