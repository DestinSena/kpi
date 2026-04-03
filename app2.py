import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import numpy as np

st.set_page_config(page_title="KPIs Réseau Hebdo", layout="wide")

# ─── CSS ─── (inchangé)
st.markdown("""
    <style>
        .stApp {
            background-color: #ffffff;
            color: #111111;
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
        }
        .header-container {
            background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%);
            border-radius: 16px;
            padding: 32px 28px;
            margin: 24px auto;
            max-width: 1400px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.06);
            text-align: center;
            border: 1px solid #e5e7eb;
        }
        .header-title {
            color: #1d4ed8;
            font-size: 2.8rem;
            font-weight: 900;
            margin-bottom: 10px;
        }
        .header-subtitle {
            color: #4b5563;
            font-size: 1.3rem;
        }
        .kpi-card {
            background: #ffffff;
            border-radius: 14px;
            padding: 24px 20px;
            border: 1px solid #e5e7eb;
            box-shadow: 0 6px 24px rgba(0,0,0,0.06);
            margin-bottom: 24px;
            transition: all 0.22s ease;
        }
        .kpi-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 12px 36px rgba(0,0,0,0.10);
        }
        [data-testid="stMetricLabel"] p {
            font-size: 1.65rem !important;
            font-weight: 700 !important;
            color: #1f2937 !important;
            margin-bottom: 4px !important;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        [data-testid="stMetricValue"] {
            font-size: 2.9rem !important;
            font-weight: 900 !important;
            color: #111827 !important;
            letter-spacing: -0.8px;
        }
        .delta-text {
            font-size: 1.12rem !important;
            font-weight: 700 !important;
            margin-top: 10px !important;
            padding: 5px 12px;
            border-radius: 8px;
            background: rgba(0,0,0,0.035);
            display: block;
        }
        div[data-testid="stFileUploaderDropzone"],
        div[data-testid="stFileUploader"] label,
        div[data-testid="stFileUploaderFileList"] {
            display: none !important;
        }
        .stPlotlyChart {
            background: #ffffff;
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid #e5e7eb;
            margin-top: 12px;
        }
    </style>
""", unsafe_allow_html=True)


# ─── Utilitaires ───
def fmt(v):
    if pd.isna(v):
        return "—"
    if v >= 1_000_000:
        val_m = v / 1_000_000
        if val_m == int(val_m):
            return f"{int(val_m)}M"
        return f"{val_m:.2f}M"
    if v >= 1_000:
        return f"{int(round(v)):,.0f}".replace(",", " ")
    if float(v).is_integer():
        return f"{int(v):,}".replace(",", " ")
    return f"{v:,.2f}".replace(",", " ")


def delta_str(g):
    if g is None:
        return "—"
    arrow = "↑" if g >= 0 else "↓"
    pct = f"{abs(g):.1f}%"
    color = "#16a34a" if g >= 0 else "#dc2626"
    bg = "rgba(22,163,74,0.10)" if g >= 0 else "rgba(220,38,38,0.10)"
    return f'<span style="color:{color}; background:{bg}; padding:4px 9px; border-radius:6px;">{arrow} {pct}</span>'


def create_sparkline(df_plot, y_col, x_col='Semaine', height=150):
    if df_plot.empty or y_col not in df_plot.columns or len(df_plot) < 2:
        return None

    fig = px.line(df_plot, x=x_col, y=y_col)   # ← markers=True supprimé

    # === AMÉLIORATION ÉCHELLE Y (rendre les petites variations visibles) ===
    y_values = df_plot[y_col].dropna()
    if len(y_values) >= 2:
        y_min = y_values.min()
        y_max = y_values.max()
        y_range = y_max - y_min

        if y_range == 0:  # toutes les valeurs identiques
            padding = abs(y_min) * 0.05 if y_min != 0 else 1
            y_min -= padding
            y_max += padding
        else:
            padding = y_range * 0.08
            y_min -= padding
            y_max += padding

        fig.update_yaxes(range=[y_min, y_max], autorange=False)

    # === AMÉLIORATION AXE X : seulement extrémités + milieu ===
    n = len(df_plot)
    if n >= 3:
        tick_positions = [df_plot.iloc[0][x_col],
                          df_plot.iloc[n // 2][x_col],
                          df_plot.iloc[-1][x_col]]
        tick_texts = [df_plot.iloc[0][x_col],
                      df_plot.iloc[n // 2][x_col],
                      df_plot.iloc[-1][x_col]]
    else:
        tick_positions = df_plot[x_col].tolist()
        tick_texts = df_plot[x_col].tolist()

    fig.update_traces(
        line=dict(color='#3b82f6', width=2.4),
        # marker supprimé complètement
        fill='tozeroy',
        fillcolor='rgba(59,130,246,0.07)'
    )

    fig.update_layout(
        height=height,
        margin=dict(l=40, r=16, t=8, b=50),
        showlegend=False,
        xaxis=dict(
            title=None,
            tickmode='array',
            tickvals=tick_positions,
            ticktext=tick_texts,
            tickangle=-40,
            tickfont=dict(size=11, color='#4b5563'),
            showgrid=True,
            gridcolor='rgba(229,231,235,0.6)',
        ),
        yaxis=dict(
            title=None,
            tickfont=dict(size=11.5, color='#4b5563'),
            gridcolor='rgba(229,231,235,0.6)',
        ),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        hovermode="x unified",
        hoverlabel=dict(bgcolor="white", font_size=12)
    )
    return fig


# ─── Chargement ─── (inchangé)
@st.cache_data
def load_kpi_file(file_bytes):
    kpis_data = {}
    with pd.ExcelFile(BytesIO(file_bytes)) as xls:
        for sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name, header=0)
                if len(df.columns) < 2:
                    continue
                week_col = df.columns[0]
                val_col = df.columns[1]
                df = df[[week_col, val_col]].copy()
                df.rename(columns={week_col: 'Semaine', val_col: 'Valeur'}, inplace=True)
                df['Valeur'] = pd.to_numeric(df['Valeur'], errors='coerce')
                df = df.dropna(subset=['Valeur', 'Semaine']).reset_index(drop=True)
                if not df.empty:
                    kpis_data[sheet_name] = {
                        'df': df,
                        'value_header': val_col.strip()
                    }
            except:
                pass
    return kpis_data


# ─── Interface ───
st.markdown("""
    <div class="header-container">
        <h1 class="header-title">KPIs Réseau Hebdo</h1>
        <p class="header-subtitle">Suivi hebdomadaire – Focus semaine actuelle + WoW / YoY</p>
    </div>
""", unsafe_allow_html=True)

uploaded = st.file_uploader("Importer fichier KPIs hebdo (.xlsx)", type="xlsx")

if uploaded:
    with st.spinner("Traitement du fichier..."):
        kpis_data = load_kpi_file(uploaded.getvalue())

    if not kpis_data:
        st.error("Aucun indicateur valide détecté dans le fichier.")
        st.stop()

    st.success(f"{len(kpis_data)} indicateurs chargés")

    st.markdown("### 📊 Indicateurs clés")

    cols = st.columns(5)

    for idx, (title, info) in enumerate(kpis_data.items()):
        df = info['df']
        if len(df) < 3:
            continue

        n = len(df)

        current_row = df.iloc[n - 2]
        prev_row = df.iloc[n - 3]
        last_year_row = df.iloc[n - 1]

        current_val = current_row['Valeur']
        current_week = current_row['Semaine']

        prev_val = prev_row['Valeur']
        prev_week = prev_row['Semaine']

        yoy_ref_val = last_year_row['Valeur']
        yoy_ref_week = last_year_row['Semaine']

        wow_pct = ((current_val - prev_val) / prev_val * 100) if prev_val != 0 and pd.notna(prev_val) else None
        yoy_pct = ((current_val - yoy_ref_val) / yoy_ref_val * 100) if yoy_ref_val != 0 and pd.notna(
            yoy_ref_val) else None

        df_plot = df.iloc[:-1].copy()

        col = cols[idx % 5]

        with col:
            st.markdown('<div class="kpi-card">', unsafe_allow_html=True)

            st.metric(
                label=title,
                value=fmt(current_val),
            )

            if wow_pct is not None:
                delta_wow = delta_str(wow_pct)
                txt_wow = f"vs {fmt(prev_val)} {prev_week}"
                st.markdown(
                    f'<div class="delta-text">{txt_wow} {delta_wow}</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown('<div class="delta-text">WoW — données incomplètes</div>', unsafe_allow_html=True)

            if yoy_pct is not None:
                delta_yoy = delta_str(yoy_pct)
                txt_yoy = f"vs {fmt(yoy_ref_val)} {yoy_ref_week}"
                st.markdown(
                    f'<div class="delta-text">{txt_yoy} {delta_yoy}</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown('<div class="delta-text">YoY — données incomplètes</div>', unsafe_allow_html=True)

            fig = create_sparkline(df_plot, 'Valeur', height=150)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    if kpis_data:
        first_df = list(kpis_data.values())[0]['df']
        last_real_week = first_df.iloc[-2]['Semaine'] if len(first_df) >= 2 else "—"
    else:
        last_real_week = "—"

    st.caption(f"Semaine actuelle : **{last_real_week}**  •  Données brutes du fichier")

else:
    st.info(
        "Importez votre fichier Excel hebdomadaire.\n\n"
        "Format attendu pour chaque feuille :\n"
        "• …\n"
        "• Semaine précédente     (ex: S10-2026)\n"
        "• Semaine actuelle       (ex: S11-2026)\n"
        "• Même semaine A-1       (ex: S11-2025)\n"
    )
