import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="Gantt MAM vs MAC", layout="wide")
st.title("Ejecuciones de Modelos Semánticos — (MAM vs MAC)")

# === FUNCIÓN PARA LEER DESDE SHAREPOINT ===
@st.cache_data(ttl=600)  # Cache por 10 minutos
def cargar_desde_sharepoint(url):
    """
    Intenta cargar archivo Excel desde SharePoint
    """
    try:
        # Intenta convertir a enlace de descarga directa
        if '?e=' in url:
            url_descarga = url.split('?e=')[0] + '?download=1'
        else:
            url_descarga = url + '?download=1'
        
        # Descarga el archivo
        response = requests.get(url_descarga, timeout=30)
        response.raise_for_status()
        
        # Lee el Excel desde bytes
        return pd.read_excel(BytesIO(response.content))
    
    except Exception as e:
        st.error(f"❌ Error al cargar desde SharePoint: {str(e)}")
        return None

# === LECTURA DEL ARCHIVO ===
# OPCIÓN A: Desde SharePoint (si funciona el enlace directo)
url_sharepoint = "https://uniqueyanbal-my.sharepoint.com/:x:/g/personal/sistemas446_per_yanbal_com/IQDJ1u6WlTzhQpTWU3AIqmB3AaGRHqf-yIHuteqFGaoXCE8?e=xl0VLG"

with st.spinner("📥 Cargando datos desde SharePoint..."):
    df = cargar_desde_sharepoint(url_sharepoint)

# OPCIÓN B: Subir archivo manualmente (fallback)
if df is None:
    st.warning("⚠️ No se pudo cargar desde SharePoint. Sube el archivo manualmente:")
    archivo_subido = st.file_uploader("📁 Sube el archivo Excel", type=['xlsx', 'xls'])
    
    if archivo_subido is not None:
        df = pd.read_excel(archivo_subido)
    else:
        st.info("👆 Por favor sube el archivo para continuar")
        st.stop()

# === RENOMBRAR COLUMNAS ===
df = df.rename(columns={'Base de datos': 'Nombre Modelo Semántico'})

# === PREPARAR COLUMNAS ===
# Convertir fecha a solo fecha (sin hora)
df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce').dt.date
df['fecha_str'] = df['fecha'].astype(str)

# Convertir horas a datetime completo
df['Inicio'] = pd.to_datetime(df['fecha_str'] + ' ' + df['Hora inicio'].astype(str), errors='coerce')
df['Fin'] = pd.to_datetime(df['fecha_str'] + ' ' + df['Hora fin'].astype(str), errors='coerce')

# Agregar columna de periodo (AM/PM)
df['Periodo'] = df['Inicio'].dt.hour.apply(lambda x: 'AM' if x < 12 else 'PM')

# Eliminar filas inválidas
df = df.dropna(subset=['Inicio', 'Fin'])

if df.empty:
    st.error("❌ No hay datos válidos.")
    st.stop()

# Ordenar
df = df.sort_values(by=['fecha', 'Workspace', 'Inicio'])

# === PANEL LATERAL - INFORMACIÓN ===
st.sidebar.header("📊 Dataset")
st.sidebar.metric("Total de registros", len(df))
st.sidebar.metric("Total de días", df['fecha'].nunique())

# Estadísticas por Workspace
st.sidebar.markdown("---")
st.sidebar.subheader("Distribución por Workspace")
for ws in sorted(df['Workspace'].unique()):
    count = len(df[df['Workspace'] == ws])
    porcentaje = (count / len(df)) * 100
    emoji = "🔵" if ws == "MAM" else "🟠" if ws == "MAC" else "🟢"
    st.sidebar.markdown(f"**{emoji} {ws}:** {count} ({porcentaje:.1f}%)")

# === FILTROS HORIZONTALES ===
st.markdown("---")
st.subheader("🔍 Filtros")

col_filtro1, col_filtro2, col_filtro3 = st.columns([2, 2, 1])

with col_filtro1:
    # Filtro por día
    dias_disponibles = sorted(df['fecha'].unique(), reverse=True)
    dias_opciones = [str(d) for d in dias_disponibles]
    dia_sel_str = st.selectbox("📅 Selecciona un día:", dias_opciones)

with col_filtro2:
    # Filtro AM/PM
    periodo_opciones = ['Todos', 'AM (00:00 - 11:59)', 'PM (12:00 - 23:59)']
    periodo_sel = st.selectbox("🕐 Periodo del día:", periodo_opciones)

with col_filtro3:
    st.markdown("##")  # Espaciado
    if st.button("🔄 Actualizar", use_container_width=True):
        st.rerun()

from datetime import datetime
dia_sel = datetime.strptime(dia_sel_str, '%Y-%m-%d').date()

# Filtrar por día
df_dia = df[df['fecha'] == dia_sel].copy()

if df_dia.empty:
    st.warning("⚠️ No hay ejecuciones para el día seleccionado.")
    st.stop()

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

# === CREAR IDENTIFICADOR ÚNICO PARA EJECUCIONES MÚLTIPLES ===
df_filtrado['num_ejecucion'] = df_filtrado.groupby('Nombre Modelo Semántico').cumcount() + 1

def crear_identificador(row):
    count = df_filtrado[df_filtrado['Nombre Modelo Semántico'] == row['Nombre Modelo Semántico']].shape[0]
    if count > 1:
        return f"{row['Workspace']} - {row['Nombre Modelo Semántico']} (Ej. {row['num_ejecucion']})"
    else:
        return f"{row['Workspace']} - {row['Nombre Modelo Semántico']}"

df_filtrado['Identificador'] = df_filtrado.apply(crear_identificador, axis=1)

# === CREAR CATEGORÍA DE COLOR ===
def asignar_categoria_color(row):
    workspace = row['Workspace']
    num_ejecucion = row['num_ejecucion']
    
    if workspace == 'MAM':
        if num_ejecucion == 1:
            return 'MAM - 1ra ejecución'
        elif num_ejecucion == 2:
            return 'MAM - 2da ejecución'
        else:
            return 'MAM - 3ra+ ejecución'
    elif workspace == 'MAC':
        if num_ejecucion == 1:
            return 'MAC - 1ra ejecución'
        elif num_ejecucion == 2:
            return 'MAC - 2da ejecución'
        else:
            return 'MAC - 3ra+ ejecución'
    else:
        return workspace

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

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("📊 Total", len(df_filtrado))

with col2:
    mam_count = len(df_filtrado[df_filtrado['Workspace'] == 'MAM'])
    st.metric("🔵 MAM", mam_count)

with col3:
    mac_count = len(df_filtrado[df_filtrado['Workspace'] == 'MAC'])
    st.metric("🟠 MAC", mac_count)

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
    labels={
        "Identificador": "Modelo Semántico",
        "num_ejecucion": "N° Ejecución"
    },
    color_discrete_map=color_map
)

fig.update_yaxes(autorange="reversed", title="Modelos Semánticos")

# Configurar el eje X con ticks cada 30 minutos
fig.update_xaxes(
    title="Hora del día", 
    tickformat="%H:%M", 
    dtick=1800000,  # Ticks cada 30 minutos
    showgrid=True,
    gridcolor="LightGray",
    minor=dict(
        ticklen=6,
        tickcolor="LightGray",
        showgrid=True
    )
)

altura = max(400, min(1200, len(df_filtrado) * 30))

# Obtener rango de tiempo para las líneas verticales
tiempo_inicio = df_filtrado['Inicio'].min()
tiempo_fin = df_filtrado['Fin'].max()

# Crear lista de horas completas y medias horas
import pandas as pd
from datetime import datetime, timedelta

# Redondear al inicio de hora
inicio_hora = tiempo_inicio.replace(minute=0, second=0, microsecond=0)
if tiempo_inicio.minute > 0:
    inicio_hora += timedelta(hours=1)

# Lista para almacenar las líneas
shapes = []

# Generar líneas cada 30 minutos
hora_actual = inicio_hora
while hora_actual <= tiempo_fin:
    # Línea sólida para horas completas (00 minutos)
    if hora_actual.minute == 0:
        shapes.append(dict(
            type="line",
            x0=hora_actual,
            x1=hora_actual,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="gray", width=1, dash="solid")
        ))
    # Línea punteada para medias horas (30 minutos)
    else:
        shapes.append(dict(
            type="line",
            x0=hora_actual,
            x1=hora_actual,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="lightgray", width=1, dash="dot")
        ))
    
    hora_actual += timedelta(minutes=30)

fig.update_layout(
    height=altura,
    xaxis=dict(showgrid=False),  # Desactivar grid default para usar shapes
    shapes=shapes,  # Agregar las líneas personalizadas
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

# === TABLA DE DETALLES ===
st.subheader("📋 Detalle de ejecuciones")

df_tabla = df_filtrado[['Workspace', 'Nombre Modelo Semántico', 'Hora inicio', 'Hora fin', 'num_ejecucion']].copy()
df_tabla = df_tabla.rename(columns={'num_ejecucion': 'N° Ejecución'})
df_tabla['Duración'] = (df_filtrado['Fin'] - df_filtrado['Inicio']).dt.total_seconds() / 60
df_tabla['Duración'] = df_tabla['Duración'].apply(lambda x: f"{int(x)} min")
df_tabla = df_tabla.sort_values(by='Hora inicio')

tab1, tab2, tab3 = st.tabs(["📊 Todas", "🔵 MAM", "🟠 MAC"])

with tab1:
    st.dataframe(df_tabla, use_container_width=True, hide_index=True)
    st.caption(f"Total: {len(df_tabla)} ejecuciones")

with tab2:
    df_mam = df_tabla[df_filtrado['Workspace'] == 'MAM']
    if not df_mam.empty:
        st.dataframe(df_mam, use_container_width=True, hide_index=True)
        duraciones_mam = (df_filtrado[df_filtrado['Workspace'] == 'MAM']['Fin'] - 
                         df_filtrado[df_filtrado['Workspace'] == 'MAM']['Inicio']).dt.total_seconds() / 60
        col1, col2, col3 = st.columns(3)
        col1.metric("Total", len(df_mam))
        col2.metric("Promedio", f"{duraciones_mam.mean():.1f} min")
        col3.metric("Total tiempo", f"{duraciones_mam.sum():.1f} min")
    else:
        st.info("No hay ejecuciones MAM en este periodo")

with tab3:
    df_mac = df_tabla[df_filtrado['Workspace'] == 'MAC']
    if not df_mac.empty:
        st.dataframe(df_mac, use_container_width=True, hide_index=True)
        duraciones_mac = (df_filtrado[df_filtrado['Workspace'] == 'MAC']['Fin'] - 
                         df_filtrado[df_filtrado['Workspace'] == 'MAC']['Inicio']).dt.total_seconds() / 60
        col1, col2, col3 = st.columns(3)
        col1.metric("Total", len(df_mac))
        col2.metric("Promedio", f"{duraciones_mac.mean():.1f} min")
        col3.metric("Total tiempo", f"{duraciones_mac.sum():.1f} min")
    else:
        st.info("No hay ejecuciones MAC en este periodo")

# === ANÁLISIS DE TRASLAPES ===
with st.expander("🔍 Análisis de traslapes"):
    traslapes = []
    df_sorted = df_filtrado.sort_values('Inicio')
    
    for i in range(len(df_sorted) - 1):
        fila_actual = df_sorted.iloc[i]
        fila_siguiente = df_sorted.iloc[i + 1]
        
        if fila_actual['Fin'] > fila_siguiente['Inicio']:
            traslapes.append({
                'Modelo 1': fila_actual['Nombre Modelo Semántico'],
                'WS 1': fila_actual['Workspace'],
                'Modelo 2': fila_siguiente['Nombre Modelo Semántico'],
                'WS 2': fila_siguiente['Workspace'],
                'Inicio': fila_siguiente['Inicio'].strftime('%H:%M:%S'),
                'Fin': min(fila_actual['Fin'], fila_siguiente['Fin']).strftime('%H:%M:%S')
            })
    
    if traslapes:
        st.warning(f"⚠️ {len(traslapes)} traslapes detectados")
        st.dataframe(pd.DataFrame(traslapes), use_container_width=True, hide_index=True)
    else:
        st.success("✅ Sin traslapes en este periodo")

# === DESCARGA ===
st.markdown("---")
csv_data = df_filtrado.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Descargar CSV del periodo",
    data=csv_data,
    file_name=f"ejecuciones_{dia_sel_str}_{periodo_texto.replace(' ', '_')}.csv",
    mime="text/csv"
)

st.markdown("---")
st.caption("Desarrollado por Kevin HG. — Visualización Gantt de Ejecuciones en Databricks")
