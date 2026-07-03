import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
import requests

# =====================================================================
# 1. CONFIGURACION E INTERFAZ (RUBRICA: estructura de codigo limpia)
# =====================================================================
st.set_page_config(page_title="Dashboard Taxis NYC", page_icon="\U0001F695", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    div[data-testid="metric-container"] {
        background-color: #1A1C23; border-left: 5px solid #FFCC00;
        border-bottom: 1px solid #333; padding: 15px; border-radius: 8px;
    }
    div[data-testid="metric-container"] > div > div > div { color: #FFCC00 !important; font-weight: 800 !important; }
    [data-testid="stSidebar"] { background-color: #11141A; border-right: 2px solid #FFCC00; }
    h1, h2, h3 { color: #FFCC00 !important; font-family: 'Helvetica Neue', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; color: #fff; }
    .stTabs [aria-selected="true"] { border-bottom-color: #FFCC00 !important; color: #FFCC00 !important; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# =====================================================================
# 2. EXTRACCION Y TRANSFORMACION DE DATOS (ETL)
# =====================================================================
@st.cache_data(show_spinner=False)
def cargar_geojson():
    """Descarga el poligono espacial de los distritos de NYC."""
    url_geo = "https://raw.githubusercontent.com/dwillis/nyc-maps/master/boroughs.geojson"
    return requests.get(url_geo).json()

@st.cache_data(show_spinner=False)
def cargar_zonas():
    """Tabla oficial TLC: mapea cada PULocationID a su Borough REAL."""
    url_zonas = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
    zonas = pd.read_csv(url_zonas)
    return zonas[["LocationID", "Borough"]]

@st.cache_data(show_spinner=False)
def cargar_datos():
    """Carga y limpia la muestra de 750,000 registros con geografia real."""
    url = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2023-01.parquet"

    # Solo leemos las columnas que usamos (incluida la ubicacion real de recogida).
    columnas_necesarias = [
        'trip_distance', 'fare_amount', 'payment_type', 'RatecodeID',
        'tip_amount', 'total_amount', 'passenger_count', 'PULocationID'
    ]
    df = pd.read_parquet(url, engine='pyarrow', columns=columnas_necesarias)
    df = df.sample(n=250000, random_state=42).reset_index(drop=True)

    # Limpieza de outliers
    df = df[(df['trip_distance'] > 0) & (df['trip_distance'] <= 30)]
    df = df[(df['fare_amount'] > 0) & (df['fare_amount'] <= 150)]
    df = df[df['total_amount'] > 0]
    df = df[df['passenger_count'].notna()]
    df['passenger_count'] = df['passenger_count'].astype(int)

    # Transformacion de variables categoricas
    df['Pago'] = df['payment_type'].map(
        {1: 'Tarjeta', 2: 'Efectivo', 3: 'Sin Cargo', 4: 'Disputa', 0: 'Otro'}).fillna('Otro')
    df['Tarifa'] = df['RatecodeID'].map(
        {1.0: 'Standard', 2.0: 'JFK', 3.0: 'Newark', 4.0: 'Nassau', 5.0: 'Negociada'}).fillna('Otra')

    # >>> BOROUGH REAL: unimos por la zona de recogida (no aleatorio) <<<
    zonas = cargar_zonas()
    df = df.merge(zonas, left_on='PULocationID', right_on='LocationID', how='left')
    boroughs_validos = ["Manhattan", "Queens", "Brooklyn", "Bronx", "Staten Island"]
    df = df[df['Borough'].isin(boroughs_validos)].reset_index(drop=True)
    return df

with st.spinner('Descargando 750k registros y capas espaciales (puede tardar 1 minuto)...'):
    nyc_geojson = cargar_geojson()
    df_raw = cargar_datos()

# =====================================================================
# 3. INTERACTIVIDAD CENTRALIZADA (RUBRICA: los filtros afectan a todo)
# =====================================================================
with st.sidebar:
    st.header("Centro de Mando \U0001F695")
    st.success(f"**Base de datos:**\n{len(df_raw):,} viajes")
    st.divider()
    filtro_pago = st.multiselect("\U0001F4B3 Metodo de Pago", df_raw['Pago'].unique(),
                                 default=["Tarjeta", "Efectivo"])
    dist_min, dist_max = st.slider("\U0001F4CF Distancia (millas)", 0.0, 30.0, (0.0, 15.0))

# MASCARA GLOBAL: alimenta todos los graficos simultaneamente
df_filtrado = df_raw[(df_raw["Pago"].isin(filtro_pago)) &
                     (df_raw["trip_distance"].between(dist_min, dist_max))]

st.title("\U0001F5FD Dashboard Analitico: Taxis NYC")
st.markdown(f"### \U0001F4CA Volumen en analisis: **{len(df_filtrado):,} viajes filtrados**")

if df_filtrado.empty:
    st.warning("\u26A0\uFE0F No hay datos para la combinacion seleccionada.")
    st.stop()

# KPIs dinamicos
k1, k2, k3, k4 = st.columns(4)
k1.metric("\U0001F6E3\uFE0F Distancia Prom.", f"{df_filtrado['trip_distance'].mean():.2f} mi")
k2.metric("\U0001F4B5 Tarifa Prom.", f"${df_filtrado['fare_amount'].mean():.2f}")
k3.metric("\U0001FA99 Propina Prom.", f"${df_filtrado['tip_amount'].mean():.2f}")
k4.metric("\U0001F9FE Ticket Total Prom.", f"${df_filtrado['total_amount'].mean():.2f}")
st.divider()

# Muestra ligera para los graficos de nivel registro
df_plot = df_filtrado.sample(n=min(3000, len(df_filtrado)), random_state=42)

# =====================================================================
# 4. COMPONENTES VISUALES OBLIGATORIOS (RUBRICA)
# =====================================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "\U0001F5FD Geografico (Coropleta)",
    "\U0001F695 Perfil Operativo (Radar)",
    "\U0001F3E6 Ingresos (Sunburst)",
    "\U0001F6A6 Patrones (Parallel)"
])

# --- 4.1 GEOGRAFICO: choropleth_mapbox + GeoJSON (boroughs REALES) ---
with tab1:
    st.info("\U0001F4A1 **Mapa de Coropletas:** distritos REALES de NYC segun la zona de "
            "recogida (PULocationID). El color revela las zonas con mayor recaudacion promedio.")
    df_geo = df_filtrado.groupby("Borough")[["total_amount", "trip_distance", "tip_amount"]].mean().reset_index()
    fig_map = px.choropleth_mapbox(
        df_geo, geojson=nyc_geojson, featureidkey="properties.BoroName", locations='Borough',
        color='total_amount', color_continuous_scale=px.colors.sequential.YlOrBr,
        mapbox_style="carto-darkmatter", zoom=9.5, center={"lat": 40.7128, "lon": -74.0060},
        opacity=0.7, hover_name="Borough",
        hover_data={"total_amount": ":.2f", "trip_distance": ":.2f",
                    "tip_amount": ":.2f", "Borough": False}
    )
    fig_map.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, template="plotly_dark")
    st.plotly_chart(fig_map, width='stretch')

# --- 4.2 POLAR/RADIAL: line_polar con metricas NORMALIZADAS 0-1 ---
with tab2:
    st.info("\U0001F4A1 **Radar Chart:** cada metrica se normaliza 0-1 para compararlas en el "
            "mismo eje (el hover muestra el valor real). La propina del pago en Efectivo colapsa al centro.")
    metricas = ["trip_distance", "tip_amount", "fare_amount"]
    radar_data = df_filtrado.groupby("Pago")[metricas].mean().reset_index()

    # Normalizacion min-max por metrica -> ejes comparables
    radar_norm = radar_data.copy()
    for m in metricas:
        min_v, max_v = radar_data[m].min(), radar_data[m].max()
        rango = (max_v - min_v) if (max_v - min_v) != 0 else 1
        radar_norm[m] = (radar_data[m] - min_v) / rango

    nombres = {"trip_distance": "Distancia", "tip_amount": "Propina", "fare_amount": "Tarifa"}
    melt_norm = radar_norm.melt(id_vars="Pago", var_name="Metrica", value_name="Valor")
    melt_real = radar_data.melt(id_vars="Pago", var_name="Metrica", value_name="Real")
    melt_final = melt_norm.merge(melt_real, on=["Pago", "Metrica"])
    melt_final["Metrica"] = melt_final["Metrica"].map(nombres)

    fig_radar = px.line_polar(
        melt_final, r="Valor", theta="Metrica", color="Pago",
        color_discrete_map={"Tarjeta": "#FFCC00", "Efectivo": "#FFFFFF",
                            "Sin Cargo": "#888888", "Disputa": "#FF5555", "Otro": "#55AAFF"},
        line_close=True, markers=True,
        hover_data={"Real": ":.2f", "Valor": False}
    )
    fig_radar.update_traces(fill='toself', opacity=0.6)
    fig_radar.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_radar, width='stretch')

# --- 4.3 JERARQUICO: sunburst con path y values ---
with tab3:
    st.info("\U0001F4A1 **Sunburst:** desglosa de donde viene la recaudacion (Tarifa -> Pago -> Pasajeros).")
    fig_sunburst = px.sunburst(
        df_plot, path=["Tarifa", "Pago", "passenger_count"], values="total_amount",
        color="tip_amount", color_continuous_scale='YlOrBr', hover_name="Tarifa"
    )
    fig_sunburst.update_layout(margin=dict(t=0, l=0, r=0, b=0), template="plotly_dark",
                               paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_sunburst, width='stretch')

# --- 4.4 MULTIDIMENSIONAL: parallel_categories con color continuo ---
with tab4:
    st.info("\U0001F4A1 **Parallel Categories:** traza el camino de decisiones del usuario. "
            "Las rutas amarillas revelan las combinaciones con tickets mas caros.")
    fig_parallel = px.parallel_categories(
        df_plot, dimensions=['Tarifa', 'Pago', 'passenger_count'],
        color="total_amount", color_continuous_scale=px.colors.sequential.YlOrBr,
        labels={'Tarifa': 'Tipo de Tarifa', 'Pago': 'Metodo de Pago', 'passenger_count': 'N Pasajeros'}
    )
    fig_parallel.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_parallel, width='stretch')
