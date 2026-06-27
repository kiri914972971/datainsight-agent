from __future__ import annotations

from html import escape

import streamlit as st


ICONS = {
    "database": """
        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
        <path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5"></path>
        <path d="M3 12c0 1.7 4 3 9 3s9-1.3 9-3"></path>
    """,
    "shield-check": """
        <path d="M20 13c0 5-3.5 7.5-7.7 8.7a1 1 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1z"></path>
        <path d="m9 12 2 2 4-4"></path>
    """,
    "sparkles": """
        <path d="m12 3-1.9 5.1L5 10l5.1 1.9L12 17l1.9-5.1L19 10l-5.1-1.9z"></path>
        <path d="M5 3v4"></path><path d="M3 5h4"></path>
        <path d="M19 17v4"></path><path d="M17 19h4"></path>
    """,
    "chart": """
        <path d="M3 3v18h18"></path>
        <path d="M18 17V9"></path><path d="M13 17V5"></path><path d="M8 17v-3"></path>
    """,
    "file-down": """
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <path d="M12 18v-6"></path><path d="m9 15 3 3 3-3"></path>
    """,
    "layout-dashboard": """
        <rect width="7" height="9" x="3" y="3" rx="1"></rect>
        <rect width="7" height="5" x="14" y="3" rx="1"></rect>
        <rect width="7" height="9" x="14" y="12" rx="1"></rect>
        <rect width="7" height="5" x="3" y="16" rx="1"></rect>
    """,
}


def icon(name: str, size: int = 20) -> str:
    paths = ICONS.get(name, ICONS["sparkles"])
    return (
        f'<svg class="lucide-icon" width="{size}" height="{size}" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{paths}</svg>'
    )


def apply_product_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --di-bg: #f6f7fb;
            --di-surface: rgba(255, 255, 255, 0.86);
            --di-surface-solid: #ffffff;
            --di-surface-soft: #f3f5f9;
            --di-border: rgba(15, 23, 42, 0.09);
            --di-border-strong: rgba(15, 23, 42, 0.15);
            --di-text: #111827;
            --di-muted: #64748b;
            --di-primary: #635bff;
            --di-primary-strong: #4f46e5;
            --di-primary-soft: #eeedff;
            --di-success: #0f9f6e;
            --di-warning: #c47b12;
            --di-danger: #dc4c64;
            --di-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 10px 30px rgba(15, 23, 42, 0.06);
            --di-shadow-hover: 0 2px 4px rgba(15, 23, 42, 0.05), 0 16px 40px rgba(15, 23, 42, 0.10);
            --di-radius: 12px;
            --di-radius-lg: 18px;
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --di-bg: #0b0d12;
                --di-surface: rgba(20, 23, 31, 0.88);
                --di-surface-solid: #14171f;
                --di-surface-soft: #191d27;
                --di-border: rgba(255, 255, 255, 0.08);
                --di-border-strong: rgba(255, 255, 255, 0.15);
                --di-text: #f4f6fb;
                --di-muted: #9ca6b7;
                --di-primary: #8b83ff;
                --di-primary-strong: #a8a2ff;
                --di-primary-soft: rgba(99, 91, 255, 0.15);
                --di-shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 14px 34px rgba(0, 0, 0, 0.2);
                --di-shadow-hover: 0 2px 4px rgba(0, 0, 0, 0.35), 0 18px 48px rgba(0, 0, 0, 0.28);
            }
        }

        html, body, [class*="css"] {
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        html, body { font-size: 16px; }
        .stApp {
            color: var(--di-text);
            background:
                radial-gradient(circle at 16% -10%, rgba(99, 91, 255, 0.10), transparent 28rem),
                radial-gradient(circle at 100% 12%, rgba(14, 165, 233, 0.06), transparent 24rem),
                var(--di-bg);
        }
        [data-testid="stHeader"] {
            background: color-mix(in srgb, var(--di-bg) 82%, transparent);
            backdrop-filter: blur(18px);
            border-bottom: 1px solid var(--di-border);
        }
        [data-testid="stMainBlockContainer"] {
            width: 100%;
            max-width: 1560px;
            padding: 2rem 2.6rem 5rem;
            margin: 0 auto !important;
        }
        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 324px;
            max-width: 324px;
            background: color-mix(in srgb, var(--di-surface-solid) 92%, transparent);
            border-right: 1px solid var(--di-border);
        }
        [data-testid="stSidebar"][aria-expanded="false"] {
            min-width: 0 !important;
            max-width: 0 !important;
            width: 0 !important;
        }
        [data-testid="stSidebarContent"] { padding: 1.2rem 1rem 2rem; }
        [data-testid="stSidebar"] h2 {
            font-size: 20px !important;
            letter-spacing: -0.025em;
            margin-top: 0.4rem;
        }
        [data-testid="stSidebar"] hr {
            border-color: var(--di-border);
            margin: 1.25rem 0;
        }

        .di-hero {
            position: relative;
            overflow: hidden;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            gap: 2rem;
            margin-bottom: 1.5rem;
            padding: 1.8rem 2rem;
            border: 1px solid var(--di-border);
            border-radius: var(--di-radius-lg);
            background:
                linear-gradient(135deg, color-mix(in srgb, var(--di-surface-solid) 92%, transparent), color-mix(in srgb, var(--di-primary-soft) 55%, var(--di-surface-solid))),
                var(--di-surface-solid);
            box-shadow: var(--di-shadow);
        }
        .di-hero::after {
            content: "";
            position: absolute;
            width: 18rem;
            height: 18rem;
            right: -7rem;
            top: -11rem;
            border-radius: 999px;
            background: rgba(99, 91, 255, 0.14);
            filter: blur(4px);
        }
        .di-brand { display: flex; align-items: center; gap: 0.65rem; margin-bottom: 0.75rem; color: var(--di-primary); font-weight: 700; }
        .di-brand-mark {
            width: 2rem;
            height: 2rem;
            display: grid;
            place-items: center;
            border-radius: 10px;
            color: white;
            background: linear-gradient(135deg, var(--di-primary), #8b5cf6);
            box-shadow: 0 8px 20px rgba(99, 91, 255, 0.28);
        }
        .di-hero h1 {
            margin: 0;
            color: var(--di-text);
            font-size: clamp(2rem, 4vw, 3.25rem);
            line-height: 1.06;
            letter-spacing: -0.055em;
        }
        .di-hero p {
            max-width: 48rem;
            margin: 0.8rem 0 0;
            color: var(--di-muted);
            font-size: 1rem;
            line-height: 1.75;
        }
        .di-chips { position: relative; z-index: 1; display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 0.5rem; }
        .di-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.5rem 0.7rem;
            border: 1px solid var(--di-border);
            border-radius: 999px;
            color: var(--di-muted);
            background: color-mix(in srgb, var(--di-surface-solid) 82%, transparent);
            font-size: 0.78rem;
            font-weight: 650;
            white-space: nowrap;
        }

        .di-module-intro {
            display: flex;
            align-items: flex-start;
            gap: 0.9rem;
            padding: 1rem 1.1rem;
            margin: 0.35rem 0 1.25rem;
            border: 1px solid var(--di-border);
            border-radius: var(--di-radius);
            background: var(--di-surface);
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        }
        .di-module-icon {
            flex: 0 0 auto;
            display: grid;
            place-items: center;
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 11px;
            color: var(--di-primary);
            background: var(--di-primary-soft);
        }
        .di-eyebrow {
            color: var(--di-primary);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .di-module-intro h3 { margin: 0.14rem 0 0; color: var(--di-text); font-size: 1rem; letter-spacing: -0.015em; }
        .di-module-intro p { margin: 0.22rem 0 0; color: var(--di-muted); font-size: 0.86rem; line-height: 1.55; }

        .di-bento {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.5rem 0 1.35rem;
        }
        .di-bento-card {
            min-height: 8rem;
            padding: 1rem;
            border: 1px solid var(--di-border);
            border-radius: var(--di-radius);
            background: var(--di-surface);
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
            transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
        }
        .di-bento-card:hover {
            transform: translateY(-2px);
            border-color: color-mix(in srgb, var(--di-primary) 34%, var(--di-border));
            box-shadow: var(--di-shadow-hover);
        }
        .di-bento-card .di-module-icon { width: 2rem; height: 2rem; margin-bottom: 0.75rem; }
        .di-bento-card strong { display: block; color: var(--di-text); margin-bottom: 0.25rem; }
        .di-bento-card span { display: block; color: var(--di-muted); font-size: 0.78rem; line-height: 1.5; }

        .stApp p, .stApp label, .stApp li, .stApp button, .stApp input, .stApp textarea { font-size: 16px !important; }
        h2, h3 { color: var(--di-text) !important; letter-spacing: -0.03em !important; }
        h2 {
            margin-top: 2.1rem !important;
            padding-top: 0.4rem !important;
            font-size: 1.55rem !important;
        }
        h3 { font-size: 1.06rem !important; }
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--di-muted) !important; }

        [data-testid="stMetric"] {
            min-height: 118px;
            padding: 1rem 1.05rem;
            border: 1px solid var(--di-border);
            border-radius: var(--di-radius);
            background: var(--di-surface);
            box-shadow: var(--di-shadow);
            transition: transform 160ms ease, box-shadow 160ms ease;
        }
        [data-testid="stMetric"]:hover { transform: translateY(-2px); box-shadow: var(--di-shadow-hover); }
        [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {
            color: var(--di-muted) !important;
            font-size: 0.82rem !important;
            font-weight: 650 !important;
        }
        [data-testid="stMetricValue"], [data-testid="stMetricValue"] div {
            color: var(--di-text) !important;
            font-size: 30px !important;
            font-weight: 740 !important;
            letter-spacing: -0.045em !important;
        }
        [data-testid="stMetricDelta"] { font-weight: 700; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--di-border) !important;
            border-radius: var(--di-radius) !important;
            background: var(--di-surface);
            box-shadow: var(--di-shadow);
        }
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMetric"] {
            min-height: auto;
            padding: 0.2rem;
            border: 0;
            box-shadow: none;
            background: transparent;
        }

        .stTabs [data-baseweb="tab-list"] {
            width: fit-content;
            max-width: 100%;
            gap: 0.25rem;
            padding: 0.3rem;
            overflow-x: auto;
            border: 1px solid var(--di-border);
            border-radius: 13px;
            background: var(--di-surface-soft);
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        }
        .stTabs [data-baseweb="tab-border"] { display: none; }
        .stTabs button[data-baseweb="tab"] {
            height: 2.7rem;
            padding: 0 1rem;
            border-radius: 9px;
            color: var(--di-muted);
            transition: all 150ms ease;
        }
        .stTabs button[data-baseweb="tab"]:hover { color: var(--di-text); background: var(--di-surface); }
        .stTabs button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--di-text);
            background: var(--di-surface-solid);
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08), 0 4px 12px rgba(15, 23, 42, 0.05);
        }
        .stTabs button[data-baseweb="tab"] p { font-size: 0.9rem !important; font-weight: 680; }
        .stTabs [data-baseweb="tab-panel"] { padding-top: 1.25rem; }

        .stButton > button, .stDownloadButton > button {
            min-height: 2.75rem;
            border: 1px solid var(--di-border-strong);
            border-radius: 10px;
            color: var(--di-text);
            background: var(--di-surface-solid);
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
            font-weight: 680;
            transition: transform 150ms ease, box-shadow 150ms ease, border-color 150ms ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            transform: translateY(-1px);
            border-color: color-mix(in srgb, var(--di-primary) 45%, var(--di-border));
            box-shadow: var(--di-shadow-hover);
        }
        .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
            border-color: transparent;
            color: #fff;
            background: linear-gradient(135deg, var(--di-primary), var(--di-primary-strong));
            box-shadow: 0 8px 20px rgba(99, 91, 255, 0.22);
        }
        .stButton > button:disabled, .stDownloadButton > button:disabled { opacity: 0.45; transform: none; box-shadow: none; }

        [data-baseweb="input"] > div, [data-baseweb="select"] > div,
        [data-testid="stTextArea"] textarea, [data-testid="stNumberInput"] input {
            border-color: var(--di-border-strong) !important;
            border-radius: 10px !important;
            background: var(--di-surface-solid) !important;
            box-shadow: none !important;
        }
        [data-baseweb="input"] > div:focus-within, [data-baseweb="select"] > div:focus-within,
        [data-testid="stTextArea"] textarea:focus {
            border-color: var(--di-primary) !important;
            box-shadow: 0 0 0 3px var(--di-primary-soft) !important;
        }
        [data-testid="stFileUploaderDropzone"] {
            padding: 1rem;
            border: 1px dashed color-mix(in srgb, var(--di-primary) 45%, var(--di-border));
            border-radius: var(--di-radius);
            background: var(--di-primary-soft);
        }

        [data-testid="stDataFrame"], [data-testid="stTable"] {
            overflow: hidden;
            border: 1px solid var(--di-border);
            border-radius: var(--di-radius);
            background: var(--di-surface-solid);
            box-shadow: var(--di-shadow);
        }
        [data-testid="stPlotlyChart"] {
            overflow: hidden;
            padding: 0.35rem;
            border: 1px solid var(--di-border);
            border-radius: var(--di-radius);
            background: var(--di-surface-solid);
            box-shadow: var(--di-shadow);
        }
        [data-testid="stAlert"] {
            border-radius: var(--di-radius);
            border-color: var(--di-border);
        }
        [data-testid="stExpander"] {
            overflow: hidden;
            border: 1px solid var(--di-border);
            border-radius: var(--di-radius);
            background: var(--di-surface);
        }
        .lucide-icon { display: block; }

        @media (max-width: 1100px) {
            [data-testid="stMainBlockContainer"] { padding: 1.5rem 1.25rem 4rem; }
            .di-bento { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .di-hero { align-items: flex-start; flex-direction: column; }
            .di-chips { justify-content: flex-start; }
        }
        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] { padding: 1.1rem 0.8rem 3rem; }
            .di-hero { padding: 1.3rem; border-radius: 14px; }
            .di-hero h1 { font-size: 2rem; }
            .di-bento { grid-template-columns: 1fr; }
            .stTabs [data-baseweb="tab-list"] { width: 100%; border-radius: 10px; }
            [data-testid="stMetric"] { min-height: 100px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header() -> None:
    st.markdown(
        f"""
        <section class="di-hero">
            <div>
                <div class="di-brand">
                    <span class="di-brand-mark">{icon("chart", 18)}</span>
                    <span>DataInsight Agent</span>
                </div>
                <h1>从数据到决策，清晰一步到位。</h1>
                <p>上传业务数据，完成质量诊断、探索分析、经营洞察与专业报告导出。</p>
            </div>
            <div class="di-chips">
                <span class="di-chip">{icon("shield-check", 14)} 质量诊断</span>
                <span class="di-chip">{icon("sparkles", 14)} AI 洞察</span>
                <span class="di-chip">{icon("file-down", 14)} 多格式导出</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_module_intro(icon_name: str, eyebrow: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <section class="di-module-intro">
            <div class="di-module-icon">{icon(icon_name, 20)}</div>
            <div>
                <div class="di-eyebrow">{escape(eyebrow)}</div>
                <h3>{escape(title)}</h3>
                <p>{escape(description)}</p>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

