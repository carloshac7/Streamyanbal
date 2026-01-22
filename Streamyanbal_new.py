import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO
from datetime import datetime

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="Gantt MAM vs MAC", layout="wide")
st.title("Ejecuciones de Modelos Semánticos — (MAM vs MAC)")
st.markdown("Visualiza todos los modelos ejecutados en un día específico, agrupados por Workspace (MAM y MAC).")

# === FUNCIÓN PARA LEER DESDE SHAREPOINT ===
@st.cache_data(ttl=600)
def cargar_desde_sharepoint(url):
    """Intenta cargar archivo Excel desde SharePoint"""
    try:
        if '?e=' in url:
            url_descarga = url.split('?e=')[0] + '?download=1'
        else:
            url_descarga = url + '?download=1'
        
        response = requests.get(url_descarga, timeout=30)
        response.raise_for_status()
        return pd.read_excel(BytesIO(response.content))
    except Exception as e:
        st.error(f"❌ Error al cargar desde SharePoint: {str(e)}")
        return None

# === LECTURA DEL ARCHIVO ===
url_sharepoint = "https://uniqueyanbal-my.sharepoint.com/:x:/g/personal/sistemas446_per_yanbal_com/IQDJ1u6WlTzhQpTWU3AIqmB3AT0XDJ3n2-hOultvQgKNdaQ?e=15bT3R"

with st.spinner("📥 Cargando datos desde SharePoint..."):
    df = cargar_desde_sharepoint(url_sharepoint)

if df is None:
    st.warning("⚠️ No se pudo cargar desde SharePoint. Sube el archivo manualmente:")
    archivo_subido = st.file_uploader("📁 Sube el archivo Excel", type=['xlsx', 'xls'])
    
    if archivo_subido is not None:
        df = pd.read_excel(archivo_subido)
    else:
        st.info("👆 Por favor sube el archivo para continuar")
        st.stop()

# === PREPARAR DATOS ===
df = df.rename(columns={'Base de datos': 'Nombre Modelo Semántico'})
df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce').dt.date
df['fecha_str'] = df['fecha'].astype(str)
df['Inicio'] = pd.to_datetime(df['fecha_str'] + ' ' + df['Hora inicio'].astype(str), errors='coerce')
df['Fin'] = pd.to_datetime(df['fecha_str'] + ' ' + df['Hora fin'].astype(str), errors='coerce')
df['Periodo'] = df['Inicio'].dt.hour.apply(lambda x: 'AM' if x < 12 else 'PM')
df = df.dropna(subset=['Inicio', 'Fin'])

if df.empty:
    st.error("❌ No hay datos válidos.")
    st.stop()

df = df.sort_values(by=['fecha', 'Workspace', 'Inicio'])

# === INDICADORES DEL DATASET (en área principal, debajo del subtítulo) ===
col_info1, col_info2, col_info3, col_info4 = st.columns(4)

with col_info1:
    st.metric("📊 Total de registros", len(df))

with col_info2:
    st.metric("📅 Total de días", df['fecha'].nunique())

# Distribución por Workspace
workspaces = sorted(df['Workspace'].unique())
for i, ws in enumerate(workspaces[:2]):  # Máximo 2 workspaces en las columnas restantes
    count = len(df[df['Workspace'] == ws])
    porcentaje = (count / len(df)) * 100
    emoji = "🔵" if ws == "MAM" else "🟠" if ws == "MAC" else "🟢"
    
    if i == 0:
        with col_info3:
            st.metric(f"{emoji} {ws}", f"{count} ({porcentaje:.1f}%)")
    elif i == 1:
        with col_info4:
            st.metric(f"{emoji} {ws}", f"{count} ({porcentaje:.1f}%)")

st.markdown("---")

# === FILTROS EN BARRA LATERAL ===
st.sidebar.header("🔍 Filtros")

# Filtro por día
dias_disponibles = sorted(df['fecha'].unique(), reverse=True)
dias_opciones = [str(d) for d in dias_disponibles]
dia_sel_str = st.sidebar.selectbox("📅 Selecciona un día:", dias_opciones)
dia_sel = datetime.strptime(dia_sel_str, '%Y-%m-%d').date()

# Filtrar por día
df_dia = df[df['fecha'] == dia_sel].copy()

if df_dia.empty:
    st.warning("⚠️ No hay ejecuciones para el día seleccionado.")
    st.stop()

# Filtro AM/PM
periodo_opciones = ['Todos', 'AM (00:00 - 11:59)', 'PM (12:00 - 23:59)']
periodo_sel = st.sidebar.radio("🕐 Periodo del día:", periodo_opciones)

# Aplicar filtro de periodo
if periodo_sel == 'AM (00:00 - 11:59)':
    df_filtrado = df_dia[df_dia['Periodo'] == 'AM'].copy()
    periodo_texto = "AM"
elif periodo_sel == 'PM (12:00 - 23:59)':
    df_filtrado = df_dia[df_dia['Periodo'] == 'PM'].copy()
    periodo_texto = "PM"
else:
    df_filtrado = df_dia.copy()
    periodo_texto = "Día completo"

if df_filtrado.empty:
    st.warning(f"⚠️ No hay ejecuciones en el periodo seleccionado ({periodo_texto}).")
    st.stop()

# === CREAR IDENTIFICADOR ÚNICO ===
df_filtrado['num_ejecucion'] = df_filtrado.groupby('Nombre Modelo Semántico').cumcount() + 1

def crear_identificador(row):
    count = df_filtrado[df_filtrado['Nombre Modelo Semántico'] == row['Nombre Modelo Semántico']].shape[0]
    if count > 1:
        return f"{row['Workspace']} - {row['Nombre Modelo Semántico']} (Ej. {row['num_ejecucion']})"
    return f"{row['Workspace']} - {row['Nombre Modelo Semántico']}"

df_filtrado['Identificador'] = df_filtrado.apply(crear_identificador, axis=1)

# === CREAR CATEGORÍA DE COLOR ===
def asignar_categoria_color(row):
    ws, num = row['Workspace'], row['num_ejecucion']
    sufijos = {1: '1ra ejecución', 2: '2da ejecución'}
    sufijo = sufijos.get(num, '3ra+ ejecución')
    return f'{ws} - {sufijo}' if ws in ['MAM', 'MAC'] else ws

df_filtrado['Categoria_Color'] = df_filtrado.apply(asignar_categoria_color, axis=1)

color_map = {
    'MAM - 1ra ejecución': '#1f77b4',
    'MAM - 2da ejecución': '#6baed6',
    'MAM - 3ra+ ejecución': '#c6dbef',
    'MAC - 1ra ejecución': '#ff7f0e',
    'MAC - 2da ejecución': '#ffbb78',
    'MAC - 3ra+ ejecución': '#ffd699'
}

# === MÉTRICAS DEL PERIODO ===
st.subheader(f"📅 Ejecuciones del {dia_sel_str} - {periodo_texto}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("📊 Total", len(df_filtrado))
col2.metric("🔵 MAM", len(df_filtrado[df_filtrado['Workspace'] == 'MAM']))
col3.metric("🟠 MAC", len(df_filtrado[df_filtrado['Workspace'] == 'MAC']))
duracion_promedio = (df_filtrado['Fin'] - df_filtrado['Inicio']).dt.total_seconds().mean() / 60
col4.metric("⏱️ Duración Avg", f"{duracion_promedio:.1f} min")

# Mostrar bases con ejecuciones múltiples
ejecuciones_multiples = df_filtrado[df_filtrado['num_ejecucion'] > 1]['Nombre Modelo Semántico'].unique()
if len(ejecuciones_multiples) > 0:
    with st.expander(f"⚠️ {len(ejecuciones_multiples)} Base(s) de datos con múltiples ejecuciones"):
        for bd in ejecuciones_multiples:
            count = len(df_filtrado[df_filtrado['Nombre Modelo Semántico'] == bd])
            st.write(f"• **{bd}**: {count} ejecuciones")

# === GRÁFICO GANTT ===
fig = px.timeline(
    df_filtrado,
    x_start="Inicio",
    x_end="Fin",
    y="Identificador",
    color="Categoria_Color",
    hover_data={
        "Workspace": True,
        "Nombre Modelo Semántico": True,
        "Inicio": "|%H:%M:%S",
        "Fin": "|%H:%M:%S",
        "Identificador": False,
        "Categoria_Color": False,
        "num_ejecucion": True
    },
    labels={"Identificador": "Modelo Semántico", "num_ejecucion": "N° Ejecución"},
    color_discrete_map=color_map
)

fig.update_yaxes(autorange="reversed", title="Modelos Semánticos")
fig.update_xaxes(title="Hora del día", tickformat="%H:%M", dtick=3600000)

fig.update_layout(
    height=max(400, min(1200, len(df_filtrado) * 30)),
    xaxis=dict(showgrid=True, gridcolor="LightGray"),
    legend=dict(
        title="Tipo de Ejecución",
        orientation="v",
        yanchor="top",
        y=1,
        xanchor="left",
        x=1.02
    ),
    bargap=0.1,
    template="plotly_white",
    hovermode='closest'
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("Desarrollado por Kevin HG. — Visualización Gantt de Ejecuciones en Databricks")