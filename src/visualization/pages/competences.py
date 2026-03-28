"""
Page Compétences — Analyse Tech Stack (layout + callbacks).
"""

import re
from collections import Counter

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, dcc, html

from src.visualization.components import (
    chart_card, empty_fig, make_kpi_card, make_skeleton_chart,
    section_title, styled_fig,
)
from src.visualization.config import (
    CLOUD_KEYWORDS, GENAI_KEYWORDS, HARD_SKILLS, PALETTE,
    SOFT_SKILLS, TRADITIONAL_KEYWORDS,
)
from src.visualization.data import (
    _keyword_count, _keyword_pct, _read_store, _text_blob,
)


def layout():
    return [

        section_title("fa-solid fa-microchip", "Analyse Tech Stack — Clusters de compétences"),

        html.Div(id="kpi-row-competences", style={"minHeight": "100px"}),

        dbc.Row([
            dbc.Col(
                chart_card("Le « Power Trio » — Python + SQL + Cloud",
                           dcc.Loading(
                               custom_spinner=make_skeleton_chart("300px"),
                               children=dcc.Graph(id="chart-power-trio",
                                                  config={"displayModeBar": False}),
                           )),
                lg=4, md=12, className="mb-4",
            ),
            dbc.Col(
                chart_card("IA Générative vs Outils traditionnels",
                           dcc.Loading(
                               custom_spinner=make_skeleton_chart("300px"),
                               children=dcc.Graph(id="chart-genai-vs-trad",
                                                  config={"displayModeBar": False}),
                           )),
                lg=4, md=12, className="mb-4",
            ),
            dbc.Col(
                chart_card("Hard Skills vs Soft Skills",
                           dcc.Loading(
                               custom_spinner=make_skeleton_chart("300px"),
                               children=dcc.Graph(id="chart-hard-vs-soft",
                                                  config={"displayModeBar": False}),
                           )),
                lg=4, md=12, className="mb-4",
            ),
        ]),

        dbc.Row([
            dbc.Col(
                chart_card("Top compétences par type de contrat",
                           dcc.Loading(
                               custom_spinner=make_skeleton_chart("400px"),
                               children=dcc.Graph(id="chart-skills-by-contract",
                                                  config={"displayModeBar": False}),
                           )),
                lg=7, md=12, className="mb-4",
            ),
            dbc.Col(
                chart_card("Cloud Provider — Répartition",
                           dcc.Loading(
                               custom_spinner=make_skeleton_chart("400px"),
                               children=dcc.Graph(id="chart-cloud-providers",
                                                  config={"displayModeBar": False}),
                           )),
                lg=5, md=12, className="mb-4",
            ),
        ]),

    ]


def register_callbacks(app):

    # ── KPIs ──────────────────────────────────────────────

    @app.callback(Output("kpi-row-competences", "children"), Input("filtered-data", "data"))
    def update_kpis_competences(data):
        df = _read_store(data)
        n = len(df)
        if n == 0:
            return dbc.Row([
                make_kpi_card("fa-solid fa-code", "Skills uniques", "0"),
                make_kpi_card("fa-solid fa-python", "Python", "0%"),
                make_kpi_card("fa-solid fa-database", "SQL", "0%"),
                make_kpi_card("fa-solid fa-cloud", "Cloud", "0%"),
                make_kpi_card("fa-solid fa-robot", "IA Générative", "0%"),
            ], className="g-4 mb-4")
        blob = _text_blob(df)
        all_skills = []
        for stack in df["tech_stack"].dropna():
            if stack.strip():
                all_skills.extend([s.strip() for s in stack.split(",") if s.strip()])
        unique_skills = len(set(all_skills))
        py_pct = blob.str.contains(r"\bpython\b", case=False, na=False).mean() * 100
        sql_pct = blob.str.contains(r"\bsql\b", case=False, na=False).mean() * 100
        cloud_pct = _keyword_pct(blob, CLOUD_KEYWORDS)
        genai_pct = _keyword_pct(blob, GENAI_KEYWORDS)
        return dbc.Row([
            make_kpi_card("fa-solid fa-code", "Skills uniques", f"{unique_skills}"),
            make_kpi_card("fa-brands fa-python", "Python", f"{py_pct:.0f}%"),
            make_kpi_card("fa-solid fa-database", "SQL", f"{sql_pct:.0f}%"),
            make_kpi_card("fa-solid fa-cloud", "Cloud", f"{cloud_pct:.0f}%"),
            make_kpi_card("fa-solid fa-robot", "IA Générative", f"{genai_pct:.0f}%"),
        ], className="g-4 mb-4")

    # ── Power Trio ────────────────────────────────────────

    @app.callback(Output("chart-power-trio", "figure"), Input("filtered-data", "data"))
    def update_power_trio(data):
        df = _read_store(data)
        if df.empty:
            return empty_fig()
        blob = _text_blob(df)
        has_python = blob.str.contains(r"\bpython\b", case=False, na=False)
        has_sql = blob.str.contains(r"\bsql\b", case=False, na=False)
        has_cloud = blob.str.contains("|".join(re.escape(k) for k in CLOUD_KEYWORDS), case=False, na=False)
        trio = (has_python & has_sql & has_cloud).mean() * 100
        py_sql = (has_python & has_sql).mean() * 100
        py_cloud = (has_python & has_cloud).mean() * 100
        sql_cloud = (has_sql & has_cloud).mean() * 100

        labels = ["Python + SQL + Cloud", "Python + SQL", "Python + Cloud", "SQL + Cloud"]
        values = [trio, py_sql, py_cloud, sql_cloud]
        colors = [PALETTE["primary"], PALETTE["primary_light"], PALETTE["secondary"], PALETTE["accent"]]

        fig = go.Figure(go.Bar(
            x=values, y=labels, orientation="h",
            marker_color=colors,
            text=[f"{v:.1f}%" for v in values], textposition="auto",
            textfont=dict(family="Inter", size=13, color=PALETTE["white"]),
        ))
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=20, l=140, r=20), height=300,
            yaxis=dict(showgrid=False), xaxis=dict(title="% des offres"),
        )
        return fig

    # ── GenAI vs Traditional ──────────────────────────────

    @app.callback(Output("chart-genai-vs-trad", "figure"), Input("filtered-data", "data"))
    def update_genai_vs_trad(data):
        df = _read_store(data)
        if df.empty:
            return empty_fig()
        blob = _text_blob(df)

        genai_counts = {k: _keyword_count(blob, [k]) for k in GENAI_KEYWORDS}
        trad_counts = {k: _keyword_count(blob, [k]) for k in TRADITIONAL_KEYWORDS}

        genai_counts = {k: v for k, v in genai_counts.items() if v > 0}
        trad_counts = {k: v for k, v in trad_counts.items() if v > 0}

        all_labels = list(genai_counts.keys()) + list(trad_counts.keys())
        all_values = list(genai_counts.values()) + list(trad_counts.values())
        all_cats = ["IA Générative"] * len(genai_counts) + ["Traditionnel"] * len(trad_counts)

        if not all_labels:
            return empty_fig("Aucun mot-clé détecté")

        fig_df = pd.DataFrame({"Outil": all_labels, "Mentions": all_values, "Catégorie": all_cats})
        fig_df = fig_df.sort_values("Mentions", ascending=True)
        fig = px.bar(
            fig_df, x="Mentions", y="Outil", orientation="h", color="Catégorie",
            color_discrete_map={"IA Générative": PALETTE["danger"], "Traditionnel": PALETTE["primary"]},
        )
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=20, l=120, r=20), height=300,
            yaxis=dict(showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
        )
        return fig

    # ── Hard vs Soft Skills ───────────────────────────────

    @app.callback(Output("chart-hard-vs-soft", "figure"), Input("filtered-data", "data"))
    def update_hard_vs_soft(data):
        df = _read_store(data)
        if df.empty:
            return empty_fig()
        blob = _text_blob(df)

        hard_detail = sorted(
            [(s, _keyword_count(blob, [s])) for s in HARD_SKILLS],
            key=lambda x: x[1], reverse=True,
        )[:8]
        soft_detail = sorted(
            [(s, _keyword_count(blob, [s])) for s in SOFT_SKILLS],
            key=lambda x: x[1], reverse=True,
        )[:8]

        labels = [h[0] for h in hard_detail] + [s[0] for s in soft_detail]
        values = [h[1] for h in hard_detail] + [s[1] for s in soft_detail]
        cats = ["Hard Skill"] * len(hard_detail) + ["Soft Skill"] * len(soft_detail)

        if not any(v > 0 for v in values):
            return empty_fig("Aucun skill détecté")

        fig_df = pd.DataFrame({"Compétence": labels, "Mentions": values, "Type": cats})
        fig_df = fig_df[fig_df["Mentions"] > 0].sort_values("Mentions", ascending=True)
        fig = px.bar(
            fig_df, x="Mentions", y="Compétence", orientation="h", color="Type",
            color_discrete_map={"Hard Skill": PALETTE["primary"], "Soft Skill": PALETTE["warning"]},
        )
        fig = styled_fig(fig)
        fig.update_layout(
            margin=dict(t=10, b=20, l=120, r=20), height=300,
            yaxis=dict(showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
        )
        return fig

    # ── Skills by Contract (heatmap) ──────────────────────

    @app.callback(Output("chart-skills-by-contract", "figure"), Input("filtered-data", "data"))
    def update_skills_by_contract(data):
        df = _read_store(data)
        if df.empty or "tech_stack" not in df.columns or "contract_type" not in df.columns:
            return empty_fig("Aucune donnée")

        # Normaliser les types de contrat
        def _norm_contract(val):
            if not isinstance(val, str):
                return "Autre"
            v = val.lower().strip()
            if "cdi" in v:
                return "CDI"
            if "cdd" in v:
                return "CDD"
            if "freelance" in v or "indépendant" in v:
                return "Freelance"
            if "stage" in v:
                return "Stage"
            if "alternance" in v or "apprentissage" in v:
                return "Alternance"
            if "intérim" in v or "interim" in v:
                return "Intérim"
            return "Autre"

        df = df.copy()
        df["contract_type"] = df["contract_type"].apply(_norm_contract)

        top_skills = []
        for stack in df["tech_stack"].dropna():
            if stack.strip():
                top_skills.extend([s.strip() for s in stack.split(",") if s.strip()])
        top_10 = [s for s, _ in Counter(top_skills).most_common(10)]
        if not top_10:
            return empty_fig("Aucune compétence extraite")
        rows = []
        for ct in df["contract_type"].dropna().unique():
            sub = df[df["contract_type"] == ct]
            blob = _text_blob(sub)
            for skill in top_10:
                cnt = blob.str.contains(re.escape(skill.lower()), case=False, na=False).sum()
                rows.append({"Contrat": ct, "Skill": skill, "Mentions": cnt})
        hm_df = pd.DataFrame(rows)
        pivot = hm_df.pivot_table(index="Skill", columns="Contrat", values="Mentions", fill_value=0)
        pivot = pivot.loc[top_10]
        fig = px.imshow(
            pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
            color_continuous_scale="Teal", aspect="auto",
            labels={"color": "Mentions"},
        )
        fig.update_layout(
            template="plotly_white", font=dict(family="Inter", color=PALETTE["dark"]),
            paper_bgcolor=PALETTE["white"], margin=dict(t=10, b=40, l=100, r=20), height=400,
        )
        return fig

    # ── Cloud Providers ───────────────────────────────────

    @app.callback(Output("chart-cloud-providers", "figure"), Input("filtered-data", "data"))
    def update_cloud_providers(data):
        df = _read_store(data)
        if df.empty:
            return empty_fig()
        blob = _text_blob(df)
        providers = {"AWS": ["aws", "amazon web services", "s3", "lambda", "ec2"],
                     "Azure": ["azure", "microsoft azure"],
                     "GCP": ["gcp", "google cloud", "bigquery"]}
        counts = {}
        for name, kws in providers.items():
            mask = blob.str.contains("|".join(re.escape(k) for k in kws), case=False, na=False)
            counts[name] = int(mask.sum())
        if all(v == 0 for v in counts.values()):
            return empty_fig("Aucun cloud provider détecté")
        fig = go.Figure(go.Pie(
            labels=list(counts.keys()), values=list(counts.values()),
            hole=0.5, marker=dict(colors=[PALETTE["warning"], PALETTE["primary"], PALETTE["danger"]]),
            textinfo="percent+label+value", textfont=dict(size=12),
        ))
        fig.update_layout(
            template="plotly_white", font=dict(family="Inter", color=PALETTE["dark"]),
            paper_bgcolor=PALETTE["white"], margin=dict(t=10, b=10, l=10, r=10), height=400,
            showlegend=False,
        )
        return fig
