"""
Sidebar + Header layout.
"""

import pandas as pd
from dash import dcc, html

from src.visualization.config import PALETTE, SB
from src.visualization.data import DF


def _sidebar_section_title(label):
    return html.Div(
        label,
        style={
            "fontSize": "10px", "fontWeight": "600",
            "letterSpacing": "0.05em", "color": SB["text_dim"],
            "textTransform": "uppercase",
            "padding": "0 0 8px 0", "margin": "0",
        },
    )


def _nav_link(ico, label, href, is_active=False):
    active_bar = html.Div(style={
        "position": "absolute", "left": "0", "top": "6px", "bottom": "6px",
        "width": "3px", "borderRadius": "0 3px 3px 0",
        "backgroundColor": SB["accent"] if is_active else "transparent",
    })
    return dcc.Link([
        active_bar,
        html.I(className=f"{ico}",
               style={"width": "18px", "textAlign": "center",
                      "color": SB["white"] if is_active else SB["text_dim"],
                      "fontSize": "14px", "flexShrink": "0"}),
        html.Span(label, style={
            "fontSize": "14px",
            "color": SB["white"] if is_active else SB["text"],
            "fontWeight": "500" if is_active else "400",
            "marginLeft": "12px",
        }),
    ], href=href, style={
        "display": "flex", "alignItems": "center", "position": "relative",
        "padding": "10px 20px", "textDecoration": "none",
        "borderRadius": "0", "marginBottom": "2px",
        "backgroundColor": SB["surface"] if is_active else "transparent",
        "transition": "background .15s ease",
    }, className="sidebar-nav-link")


sidebar = html.Div([

    # ── Brand ─────────────────────────────────────────────
    html.Div([
        html.Div([
            html.I(className="fa-solid fa-chart-line",
                   style={"fontSize": "16px", "color": SB["accent"]}),
        ], style={
            "width": "36px", "height": "36px", "borderRadius": "10px",
            "backgroundColor": "rgba(59,130,246,.12)",
            "display": "flex", "alignItems": "center",
            "justifyContent": "center", "flexShrink": "0",
        }),
        html.Div([
            html.Span("DPIA", style={
                "fontWeight": "700", "fontSize": "16px",
                "color": SB["white"], "letterSpacing": "0.02em",
            }),
            html.Span(" Analytics", style={
                "fontWeight": "400", "fontSize": "16px",
                "color": SB["text"],
            }),
        ], style={"marginLeft": "12px"}),
    ], style={
        "display": "flex", "alignItems": "center",
        "padding": "24px 20px 20px",
    }),

    # ── Navigation ────────────────────────────────────────
    html.Div(id="sidebar-nav", style={"padding": "8px 0 4px"}),

    # ── Separator ─────────────────────────────────────────
    html.Div(style={
        "height": "1px", "backgroundColor": SB["border"],
        "margin": "8px 20px", "opacity": "0.5",
    }),

    # ── Filtres ───────────────────────────────────────────
    html.Div([
        _sidebar_section_title("FILTRES"),

        html.Div([
            html.Label("Ville", style={
                "fontSize": "12px", "fontWeight": "500",
                "color": SB["text"], "marginBottom": "6px",
                "display": "block",
            }),
            dcc.Dropdown(
                id="filter-city",
                options=[{"label": "Toutes les villes", "value": "ALL"}] +
                        ([{"label": c, "value": c}
                         for c in sorted(DF["city_clean"].dropna().unique())]
                         if "city_clean" in DF.columns else []),
                value="ALL", clearable=False,
                className="sidebar-dropdown",
            ),
        ], style={"marginBottom": "16px"}),

        html.Div([
            html.Label("Contrat", style={
                "fontSize": "12px", "fontWeight": "500",
                "color": SB["text"], "marginBottom": "6px",
                "display": "block",
            }),
            dcc.Dropdown(
                id="filter-contract",
                options=[{"label": "Tous les contrats", "value": "ALL"}] +
                        ([{"label": c, "value": c}
                         for c in sorted(DF["contract_type"].dropna().unique())]
                         if "contract_type" in DF.columns else []),
                value="ALL", clearable=False,
                className="sidebar-dropdown",
            ),
        ], style={"marginBottom": "16px"}),

        html.Div([
            html.Label("Salaire (k€)", style={
                "fontSize": "12px", "fontWeight": "500",
                "color": SB["text"], "marginBottom": "10px",
                "display": "block",
            }),
            dcc.RangeSlider(
                id="filter-salary", min=0, max=150, step=5, value=[0, 150],
                marks={
                    i: {"label": f"{i}k",
                        "style": {"color": SB["text_dim"], "fontSize": "10px"}}
                    for i in range(0, 151, 50)
                },
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ]),
    ], style={"padding": "12px 20px 20px"}),

    # ── Spacer ────────────────────────────────────────────
    html.Div(style={"flex": "1"}),

    # ── Footer ────────────────────────────────────────────
    html.Div([
        html.Div(style={
            "height": "1px", "backgroundColor": SB["border"],
            "margin": "0 0 16px", "opacity": "0.4",
        }),
        html.Div([
            html.I(className="fa-solid fa-satellite-dish",
                   style={"fontSize": "10px", "color": SB["text_dim"],
                          "marginRight": "6px"}),
            html.Span("Source : Adzuna API", style={
                "fontSize": "11px", "color": SB["text_dim"]}),
        ], style={"textAlign": "center", "marginBottom": "8px",
                  "display": "flex", "alignItems": "center",
                  "justifyContent": "center"}),
        html.Div([
            html.Span("© 2026 — DPIA Project", style={
                "fontSize": "11px", "color": SB["text_dim"]}),
        ], style={"textAlign": "center"}),
    ], style={"padding": "0 20px 20px"}),

], style={
    "position": "fixed", "top": 0, "left": 0, "bottom": 0,
    "width": "260px",
    "backgroundColor": SB["bg"],
    "borderRight": f"1px solid {SB['border']}",
    "overflowY": "auto", "zIndex": 1000,
    "fontFamily": "Inter, sans-serif",
    "display": "flex", "flexDirection": "column",
})


# ── Header helpers ─────────────────────────────────────────

def _header_stat(icon, label, value, color=PALETTE["primary"]):
    """Mini stat badge for the header bar."""
    return html.Div([
        html.Div([
            html.I(className=icon,
                   style={"fontSize": "11px", "color": color}),
        ], style={
            "width": "28px", "height": "28px", "borderRadius": "8px",
            "backgroundColor": f"{color}12",
            "display": "flex", "alignItems": "center",
            "justifyContent": "center", "flexShrink": "0",
        }),
        html.Div([
            html.Span(value, style={
                "fontWeight": "700", "fontSize": "14px",
                "color": PALETTE["dark"], "lineHeight": "1",
            }),
            html.Span(label, style={
                "fontSize": "10px", "color": PALETTE["muted"],
                "textTransform": "uppercase", "letterSpacing": "0.04em",
                "fontWeight": "600", "lineHeight": "1",
            }),
        ], style={
            "display": "flex", "flexDirection": "column", "gap": "2px",
            "marginLeft": "8px",
        }),
    ], style={
        "display": "flex", "alignItems": "center",
        "padding": "6px 14px 6px 8px",
        "backgroundColor": PALETTE["white"],
        "borderRadius": "10px",
        "border": "1px solid #E8ECF1",
    })


# Compute header stats from DF
_n_offers = f"{len(DF):,}".replace(",", "\u202f")
_n_companies = (
    f"{DF['company'].nunique():,}".replace(",", "\u202f")
    if "company" in DF.columns and not DF.empty else "—"
)
_n_cities = str(DF["city_clean"].nunique()) if "city_clean" in DF.columns and not DF.empty else "—"
_avg_salary = (
    f"{DF['salary_avg'].dropna().mean() / 1000:.0f}k€"
    if "salary_avg" in DF.columns and DF["salary_avg"].notna().any() else "—"
)


# ── Header ────────────────────────────────────────────────
header = html.Div([

    # ── Top row: title + badges ───────────────────────────
    html.Div([
        # Left: icon + title + subtitle
        html.Div([
            html.Div([
                html.I(className="fa-solid fa-chart-pie",
                       style={"fontSize": "20px", "color": PALETTE["white"]}),
            ], style={
                "width": "46px", "height": "46px", "borderRadius": "14px",
                "background": f"linear-gradient(135deg, {PALETTE['primary']}, {PALETTE['secondary']})",
                "display": "flex", "alignItems": "center",
                "justifyContent": "center", "flexShrink": "0",
                "boxShadow": "0 4px 14px rgba(27,73,101,.25)",
            }),
            html.Div([
                html.H4("Marché de l'emploi Data Science", style={
                    "margin": 0, "fontWeight": "700", "fontSize": "20px",
                    "color": PALETTE["dark"], "fontFamily": "Inter, sans-serif",
                    "lineHeight": "1.2",
                }),
                html.P(id="header-subtitle", style={
                    "margin": "3px 0 0", "fontSize": "13px",
                    "color": PALETTE["muted"], "fontWeight": "400",
                    "fontFamily": "Inter, sans-serif",
                }),
            ], style={"marginLeft": "14px"}),
        ], style={"display": "flex", "alignItems": "center"}),

        # Right: status badges
        html.Div([
            html.Div([
                html.Div(style={
                    "width": "8px", "height": "8px", "borderRadius": "50%",
                    "backgroundColor": PALETTE["success"],
                    "boxShadow": f"0 0 6px {PALETTE['success']}",
                    "marginRight": "6px", "flexShrink": "0",
                    "animation": "pulse 2s ease-in-out infinite",
                }),
                html.Span("Pipeline actif", style={
                    "fontSize": "12px", "fontWeight": "500",
                    "color": PALETTE["success"],
                }),
            ], style={
                "display": "flex", "alignItems": "center",
                "backgroundColor": "rgba(45,147,108,.07)",
                "padding": "6px 14px", "borderRadius": "20px",
            }),
            html.Div([
                html.I(className="fa-regular fa-clock",
                       style={"fontSize": "11px", "color": PALETTE["muted"],
                              "marginRight": "6px"}),
                html.Span(
                    pd.Timestamp.now().strftime("%d %b %Y · %H:%M"),
                    style={"fontSize": "12px", "fontWeight": "500",
                           "color": PALETTE["dark"]},
                ),
            ], style={
                "display": "flex", "alignItems": "center",
                "backgroundColor": PALETTE["white"],
                "padding": "6px 14px", "borderRadius": "20px",
                "border": "1px solid #E8ECF1",
            }),
        ], style={"display": "flex", "alignItems": "center", "gap": "10px"}),
    ], style={
        "display": "flex", "justifyContent": "space-between",
        "alignItems": "center", "flexWrap": "wrap", "gap": "12px",
    }),

    # ── Separator ─────────────────────────────────────────
    html.Div(style={
        "height": "1px",
        "background": "linear-gradient(90deg, transparent, #E8ECF1 20%, #E8ECF1 80%, transparent)",
        "margin": "16px 0 14px",
    }),

    # ── Bottom row: quick stats ───────────────────────────
    html.Div([
        _header_stat("fa-solid fa-database", "Offres", _n_offers, PALETTE["primary"]),
        _header_stat("fa-solid fa-building", "Entreprises", _n_companies, PALETTE["secondary"]),
        _header_stat("fa-solid fa-location-dot", "Villes", _n_cities, PALETTE["warning"]),
        _header_stat("fa-solid fa-coins", "Salaire moy.", _avg_salary, PALETTE["success"]),
    ], style={
        "display": "flex", "alignItems": "center",
        "gap": "12px", "flexWrap": "wrap",
    }),

], style={
    "padding": "22px 28px 20px",
    "backgroundColor": PALETTE["white"],
    "borderRadius": "16px",
    "boxShadow": "0 2px 12px rgba(0,0,0,.06)",
    "marginBottom": "24px",
    "borderLeft": f"4px solid {PALETTE['primary']}",
})
