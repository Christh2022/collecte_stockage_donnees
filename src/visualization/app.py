"""
Dashboard interactif — Marché de l'emploi Data Science.
Point d'entrée. Crée l'app Dash, enregistre les callbacks, lance le serveur.
"""

import os
import time

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, dcc, html

from src.visualization.config import PALETTE, SKELETON_DELAY
from src.visualization.data import filter_df
from src.visualization.sidebar import _nav_link, _sidebar_section_title, header, sidebar
from src.visualization.pages import (
    competences, dashboard, geographie, qualite, salaires, temporel,
)

# ── App Dash + Bootstrap LUX ──────────────────────────────
FA = "https://use.fontawesome.com/releases/v6.5.1/css/all.css"
GOOGLE_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Inter:wght@300;400;500;600;700&display=swap"
)

app = Dash(
    __name__,
    title="DPIA — Marché Data Science",
    external_stylesheets=[dbc.themes.LUX, FA, GOOGLE_FONTS],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    assets_folder=os.path.join(os.path.dirname(__file__), "assets"),
)
app.config.suppress_callback_exceptions = True
server = app.server


# ── Footer ────────────────────────────────────────────────
_footer = html.Div(
    html.P([
        html.I(className="fa-regular fa-copyright me-1"),
        " 2026 — DPIA · Collecte & Stockage de Données · Adzuna API",
    ], className="text-center mb-0",
       style={"color": PALETTE["muted"], "fontSize": "12px"}),
    style={"padding": "16px 0 24px"},
)


# ── Main Content ──────────────────────────────────────────
main_content = html.Div([
    dcc.Store(id="filtered-data"),
    header,
    html.Div(id="page-content"),
    _footer,
], style={
    "marginLeft": "260px",
    "padding": "28px 32px",
    "backgroundColor": PALETTE["light_bg"],
    "minHeight": "100vh",
    "fontFamily": "Inter, sans-serif",
})


# ── Layout ────────────────────────────────────────────────
app.layout = html.Div([dcc.Location(id="url", refresh=False), sidebar, main_content])


# ── Routing ───────────────────────────────────────────────

_NAV_PAGES = [
    ("fa-solid fa-gauge-high", "Vue d'ensemble", "/"),
    ("fa-solid fa-microchip", "Compétences", "/competences"),
    ("fa-solid fa-clock", "Temporel", "/temporel"),
    ("fa-solid fa-earth-europe", "Géographie", "/geographie"),
    ("fa-solid fa-coins", "Salaires", "/salaires"),
    ("fa-solid fa-heart-pulse", "Qualité", "/qualite"),
]

_PATH_TO_BUILDER = {
    "/": dashboard.layout,
    "/competences": competences.layout,
    "/temporel": temporel.layout,
    "/geographie": geographie.layout,
    "/salaires": salaires.layout,
    "/qualite": qualite.layout,
}


@app.callback(Output("sidebar-nav", "children"), Input("url", "pathname"))
def update_sidebar_nav(pathname):
    pathname = pathname or "/"
    return [_sidebar_section_title("NAVIGATION")] + [
        _nav_link(ico, label, href, is_active=(pathname == href))
        for ico, label, href in _NAV_PAGES
    ]


@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(pathname):
    builder = _PATH_TO_BUILDER.get(pathname or "/", dashboard.layout)
    return builder()


# ── Header subtitle (page-aware) ─────────────────────────

_PAGE_SUBTITLES = {
    "/": "Vue d'ensemble en temps réel des offres, salaires et compétences",
    "/competences": "Analyse des stacks techniques, IA générative et soft skills",
    "/temporel": "Dynamique de publication et fraîcheur des données",
    "/geographie": "Répartition géographique et tendances télétravail",
    "/salaires": "Distribution salariale et premium par compétence",
    "/qualite": "Complétude, doublons et santé globale du dataset",
}


@app.callback(Output("header-subtitle", "children"), Input("url", "pathname"))
def update_header_subtitle(pathname):
    return _PAGE_SUBTITLES.get(pathname or "/", _PAGE_SUBTITLES["/"])


# ── Global filter callback ────────────────────────────────
FILTER_INPUTS = [
    Input("filter-city", "value"),
    Input("filter-contract", "value"),
    Input("filter-salary", "value"),
]


@app.callback(Output("filtered-data", "data"), *FILTER_INPUTS)
def compute_filtered_data(city, contract, salary_range):
    if SKELETON_DELAY:
        time.sleep(SKELETON_DELAY * 0.3)
    df = filter_df(city, contract, salary_range)
    return df.to_json(date_format="iso", orient="split")


# ── Register page callbacks ──────────────────────────────
dashboard.register_callbacks(app)
competences.register_callbacks(app)
temporel.register_callbacks(app)
geographie.register_callbacks(app)
salaires.register_callbacks(app)
qualite.register_callbacks(app)


# Point d'entrée
if __name__ == "__main__":
    debug = os.getenv("ENV_MODE", "dev") == "dev"
    app.run(host="0.0.0.0", port=8050, debug=debug, use_reloader=False)
