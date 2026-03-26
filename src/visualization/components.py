"""
Composants UI réutilisables — cartes KPI, graphiques, squelettes, helpers Plotly/Bokeh.
"""

import pandas as pd
import plotly.graph_objects as go
from bokeh.embed import file_html
from bokeh.models import ColumnDataSource, HoverTool
from bokeh.plotting import figure
from bokeh.resources import CDN
import dash_bootstrap_components as dbc
from dash import html

from src.visualization.config import PALETTE


# ══════════════════════════════════════════════════════════
# KPI CARDS
# ══════════════════════════════════════════════════════════

def make_kpi_card(icon_class, title, value, card_id=None):
    props = {"className": "kpi-card"}
    if card_id:
        props["id"] = card_id
        props["style"] = {"cursor": "pointer"}
    return dbc.Col(
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.P(title, style={
                        "color": PALETTE["muted"], "fontSize": "11px",
                        "fontWeight": "600", "textTransform": "uppercase",
                        "letterSpacing": "1.2px", "margin": 0,
                        "lineHeight": "1",
                    }),
                    html.Div([
                        html.I(className=icon_class,
                               style={"fontSize": "14px",
                                      "color": PALETTE["primary"]}),
                    ], style={
                        "width": "36px", "height": "36px",
                        "borderRadius": "10px",
                        "backgroundColor": "rgba(27,73,101,.08)",
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center", "flexShrink": "0",
                    }),
                ], style={
                    "display": "flex", "justifyContent": "space-between",
                    "alignItems": "center", "marginBottom": "16px",
                }),
                html.H2(value, style={
                    "fontWeight": "700", "fontSize": "32px",
                    "color": PALETTE["primary"],
                    "fontFamily": "Inter, sans-serif",
                    "margin": 0, "lineHeight": "1.1",
                }),
            ], style={"padding": "24px"}),
        ], **props),
        xs=12, sm=6, lg=True, className="mb-4",
    )


def make_salary_card(median_value, min_value, max_value):
    median_str = f"{median_value:,.0f} €" if pd.notna(median_value) else "N/A"
    parts = []
    if pd.notna(min_value):
        parts.append(f"Min : {min_value:,.0f} €")
    if pd.notna(max_value):
        parts.append(f"Max : {max_value:,.0f} €")
    sub_text = "  |  ".join(parts) if parts else ""

    return dbc.Col(
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.P("SALAIRE", style={
                        "color": PALETTE["muted"], "fontSize": "11px",
                        "fontWeight": "600", "textTransform": "uppercase",
                        "letterSpacing": "1.2px", "margin": 0,
                        "lineHeight": "1",
                    }),
                    html.Div([
                        html.I(className="fa-solid fa-coins",
                               style={"fontSize": "14px",
                                      "color": PALETTE["primary"]}),
                    ], style={
                        "width": "36px", "height": "36px",
                        "borderRadius": "10px",
                        "backgroundColor": "rgba(27,73,101,.08)",
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center", "flexShrink": "0",
                    }),
                ], style={
                    "display": "flex", "justifyContent": "space-between",
                    "alignItems": "center", "marginBottom": "16px",
                }),
                html.H2(median_str, style={
                    "fontWeight": "700", "fontSize": "32px",
                    "color": PALETTE["primary"],
                    "fontFamily": "Inter, sans-serif",
                    "margin": 0, "lineHeight": "1.1",
                }),
                html.P("Médian", style={
                    "color": PALETTE["muted"], "fontSize": "11px",
                    "fontWeight": "500", "margin": "4px 0 0 0",
                }),
                html.Hr(style={
                    "margin": "12px 0 10px", "borderColor": "#E8ECF1",
                    "opacity": "0.6",
                }),
                html.P(sub_text, style={
                    "color": PALETTE["muted"], "fontSize": "12px",
                    "fontWeight": "500", "margin": 0,
                    "letterSpacing": "0.3px",
                }),
            ], style={"padding": "24px"}),
        ], className="kpi-card"),
        xs=12, sm=6, lg=True, className="mb-0",
    )


def chart_card(title, children, height=None):
    style = {
        "borderRadius": "12px", "border": "none",
        "boxShadow": "0 2px 12px rgba(0,0,0,.06)",
    }
    if height:
        style["height"] = height
    return dbc.Card([
        dbc.CardHeader(
            html.H6(title, className="mb-0",
                    style={"fontWeight": "600", "color": PALETTE["dark"],
                           "fontFamily": "Inter, sans-serif"}),
            style={"backgroundColor": PALETTE["white"],
                   "borderBottom": f"2px solid {PALETTE['accent']}",
                   "padding": "14px 20px"},
        ),
        dbc.CardBody(children, style={"padding": "16px"}),
    ], style=style)


# ══════════════════════════════════════════════════════════
# SKELETON LOADERS
# ══════════════════════════════════════════════════════════

def _skel(width="100%", height="20px", radius="6px", mb="0"):
    return html.Div(className="skeleton", style={
        "width": width, "height": height, "borderRadius": radius,
        "marginBottom": mb,
    })


def make_skeleton_card():
    return dbc.Col(
        dbc.Card(
            dbc.CardBody([
                _skel("48px", "48px", "50%", "12px"),
                _skel("100px", "28px", "6px", "10px"),
                _skel("80px", "13px", "4px"),
            ], style={"textAlign": "center", "padding": "24px 16px",
                      "display": "flex", "flexDirection": "column",
                      "alignItems": "center"}),
            style={"borderRadius": "12px", "border": "none",
                   "boxShadow": "0 2px 12px rgba(0,0,0,.06)"},
        ),
        xs=12, sm=6, lg=True, className="mb-3",
    )


def make_skeleton_kpi_row():
    return dbc.Row([make_skeleton_card() for _ in range(10)], className="g-3")


def make_skeleton_chart(height="320px"):
    bars = [
        _skel(f"{w}%", "18px", "4px", "10px")
        for w in [75, 90, 55, 85, 45, 70, 60, 80]
    ]
    return html.Div([
        _skel("35%", "14px", "4px", "20px"),
        html.Div(bars, style={"height": height, "overflow": "hidden"}),
    ], style={"padding": "16px", "width": "100%"})


def make_skeleton_map():
    return html.Div([
        _skel("30%", "14px", "4px", "16px"),
        _skel("100%", "440px", "8px"),
    ], style={"padding": "16px", "width": "100%"})


def make_skeleton_table():
    header = html.Div(
        [html.Div(_skel("80%", "12px", "4px"),
                  style={"flex": "1"}) for _ in range(6)],
        style={"display": "flex", "gap": "16px", "padding": "14px 10px",
               "backgroundColor": "#EDF2F7", "borderRadius": "6px",
               "marginBottom": "12px"},
    )
    rows = [
        html.Div(
            [html.Div(_skel(f"{w}%", "13px", "4px"),
                      style={"flex": "1"}) for w in [85, 70, 55, 60, 45, 75]],
            style={"display": "flex", "gap": "16px",
                   "padding": "10px", "marginBottom": "4px"},
        )
        for _ in range(8)
    ]
    return html.Div([header, *rows], style={"padding": "12px", "width": "100%"})


# ══════════════════════════════════════════════════════════
# SECTION DIVIDER
# ══════════════════════════════════════════════════════════

def section_title(icon_class, label):
    return html.Div([
        html.Div([
            html.Div([
                html.I(className=icon_class,
                       style={"fontSize": "14px", "color": PALETTE["primary"]}),
            ], style={
                "width": "32px", "height": "32px", "borderRadius": "8px",
                "backgroundColor": "rgba(27,73,101,.08)",
                "display": "flex", "alignItems": "center",
                "justifyContent": "center", "flexShrink": "0",
                "marginRight": "12px",
            }),
            html.H5(label, style={
                "margin": 0, "fontWeight": "700", "fontSize": "16px",
                "color": PALETTE["dark"], "fontFamily": "Inter, sans-serif",
            }),
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div(style={
            "flex": "1", "height": "2px", "marginLeft": "20px",
            "background": f"linear-gradient(90deg, {PALETTE['accent']}, transparent)",
            "borderRadius": "1px",
        }),
    ], style={
        "display": "flex", "alignItems": "center",
        "margin": "32px 0 20px",
    })


# ══════════════════════════════════════════════════════════
# PLOTLY HELPERS
# ══════════════════════════════════════════════════════════

def empty_fig(msg="Aucune donnée"):
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        annotations=[{"text": msg, "showarrow": False,
                      "font": {"size": 15, "color": PALETTE["muted"]}}],
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig


def styled_fig(fig):
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Inter, sans-serif", color=PALETTE["dark"]),
        paper_bgcolor=PALETTE["white"],
        plot_bgcolor=PALETTE["white"],
        margin=dict(t=10, b=40, l=50, r=20),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#EDF2F7", zeroline=False),
    )
    return fig


def build_bokeh_timeseries(df):
    ts = df.dropna(subset=["published_at"]).copy()
    if ts.empty:
        p = figure(title="Aucune donnée", width=500, height=350)
        return file_html(p, resources=CDN, title="Vide")

    ts["date"] = ts["published_at"].dt.date
    daily = ts.groupby("date").size().reset_index(name="count")
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date")
    daily["ma3"] = daily["count"].rolling(3, min_periods=1).mean()
    source = ColumnDataSource(daily)

    p = figure(
        x_axis_type="datetime", title="Publications par jour",
        height=350, sizing_mode="stretch_width",
        background_fill_color="#FFFFFF", border_fill_color="#FFFFFF",
        outline_line_color=None,
    )
    p.title.text_color = PALETTE["dark"]
    p.title.text_font = "Inter"
    p.title.text_font_size = "14px"
    p.title.text_font_style = "bold"
    p.xaxis.axis_label = "Date"
    p.yaxis.axis_label = "Nombre d'offres"
    for ax in [p.xaxis, p.yaxis]:
        ax.axis_label_text_color = PALETTE["muted"]
        ax.axis_label_text_font = "Inter"
        ax.major_label_text_color = PALETTE["muted"]
        ax.major_label_text_font = "Inter"
        ax.minor_tick_line_color = None
        ax.axis_line_color = "#E2E8F0"
    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = "#EDF2F7"
    p.ygrid.grid_line_dash = "dotted"

    p.vbar(x="date", top="count", width=60_000_000, source=source,
           fill_color=PALETTE["primary"], fill_alpha=0.7, line_color=None,
           legend_label="Offres/jour")
    p.line(x="date", y="ma3", source=source, line_width=2.5,
           line_color=PALETTE["danger"], legend_label="Moy. mobile 3j")
    p.add_tools(HoverTool(tooltips=[
        ("Date", "@date{%F}"), ("Offres", "@count"), ("Moy. 3j", "@ma3{0.0}"),
    ], formatters={"@date": "datetime"}, mode="vline"))
    p.legend.location = "top_left"
    p.legend.label_text_font = "Inter"
    p.legend.label_text_color = PALETTE["dark"]
    p.legend.background_fill_color = PALETTE["white"]
    p.legend.background_fill_alpha = 0.9
    p.legend.border_line_color = "#E2E8F0"
    return file_html(p, resources=CDN, title="Timeseries")
