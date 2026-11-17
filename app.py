import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Panel de Accidentes de Tránsito", layout="wide")
# Configura la página en modo ancho.

COLORS = ["#1F4E79", "#00C6D2", "#F5821F", "#7FB3D5", "#F9C784", "#A9CCE3"]
# Paleta de colores que usan todos los gráficos.

SEVERITY_ORDER = ["Baja", "Moderada", "Alta", "Grave"]
# Orden lógico de la severidad.

SEVERITY_COLORS = {"Baja": "#7FB3D5", "Moderada": "#1F4E79", "Alta": "#F5821F", "Grave": "#C0392B"}
# Color fijo para cada nivel de severidad.

SHIFT_ORDER = ["Madrugada", "Mañana", "Tarde", "Noche"]
# Orden de los turnos del día.

WEEKDAY_MAP = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
               "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado",
               "Sunday": "Domingo"}
# Traduce los días de la semana al español.

WEEKDAY_ORDER = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


@st.cache_data
def load_data():
    df = pd.read_csv('accidentes_limpios.csv', parse_dates=['start_time'])
    df['weekday'] = df['start_time'].dt.day_name().map(WEEKDAY_MAP)
    # Día de la semana en español.
    df['hour'] = df['start_time'].dt.hour
    # Hora del accidente.
    df['month'] = df['start_time'].dt.to_period('M').dt.to_timestamp()
    # Mes del accidente, para la serie de tiempo.
    return df


def create_filters(df):
    # Dibuja los filtros en la barra lateral y devuelve la selección.
    st.sidebar.header("Filtros")

    min_date = df["start_time"].min().date()
    # Fecha mínima disponible en los datos.

    max_date = df["start_time"].max().date()
    # Fecha máxima disponible en los datos.

    date_range = st.sidebar.date_input(
        "Rango de fechas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    # Selector de rango de fechas.

    severities = st.sidebar.multiselect(
        "Severidad",
        SEVERITY_ORDER,
        default=SEVERITY_ORDER,
    )
    # Selector de niveles de severidad.

    shifts = st.sidebar.multiselect(
        "Turno del día",
        SHIFT_ORDER,
        default=SHIFT_ORDER,
    )
    # Selector de turnos.

    states = st.sidebar.multiselect(
        "Estados (vacío = todos)",
        sorted(df["state"].unique()),
        default=[],
    )
    # Selector de estados.

    max_duration = st.sidebar.slider(
        "Duración máxima (minutos)", 0, 1440, 1440, step=30
    )
    # Control deslizante de duración máxima.

    return {
        "date_range": date_range,
        "severities": severities,
        "shifts": shifts,
        "states": states,
        "max_duration": max_duration,
    }
    # Devuelve todo lo que eligió el usuario.


def apply_filters(df, options):
    # Aplica la selección del usuario al DataFrame.
    date_range = options["date_range"]
    if len(date_range) == 2:
        start, end = date_range
    else:
        start = end = date_range[0]
    # Si solo se eligió una fecha, se usa ese mismo día.

    mask = (
        (df["start_time"].dt.date >= start) & (df["start_time"].dt.date <= end)
        & df["severity_label"].isin(options["severities"])
        & df["shift"].isin(options["shifts"])
        & (df["duration_min"] <= options["max_duration"])
    )
    if options["states"]:
        mask &= df["state"].isin(options["states"])
    # Reúne todas las condiciones en una sola máscara.

    return df[mask]


def show_kpis(df):
    # Muestra los indicadores principales.
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Accidentes", f"{len(df):,}")
    col2.metric("Severidad media", f"{df['severity'].mean():.2f}")
    col3.metric("Duración mediana", f"{df['duration_min'].median():.0f} min")
    col4.metric("% graves", f"{(df['severity_label'] == 'Grave').mean() * 100:.1f}%")


def show_charts(df):
    # Dibuja los gráficos del panel.
    col1, col2 = st.columns(2)

    top = (df.groupby('state')
             .agg(Accidentes=('severity', 'size'), Severidad_media=('severity', 'mean'),
                  Duracion_mediana=('duration_min', 'median'))
             .sort_values('Accidentes', ascending=False).head(15).reset_index())
    top['Severidad_media'] = top['Severidad_media'].round(2)
    top['Duracion_mediana'] = top['Duracion_mediana'].round(1)
    # Resumen de los 15 estados con más accidentes.

    fig_bar = px.bar(top, x='Accidentes', y='state', orientation='h',
                     hover_data=['Severidad_media', 'Duracion_mediana'],
                     color_discrete_sequence=[COLORS[0]],
                     title='Top 15 estados por número de accidentes',
                     labels={'Accidentes': 'Número de accidentes', 'state': 'Estado'})
    fig_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
    col1.plotly_chart(fig_bar, width='stretch')

    sev = df['severity_label'].value_counts().reindex(SEVERITY_ORDER, fill_value=0).reset_index()
    sev.columns = ['Severidad', 'Accidentes']
    # Número de accidentes por severidad.

    fig_sev = px.bar(sev, x='Severidad', y='Accidentes', color='Severidad',
                     color_discrete_map=SEVERITY_COLORS,
                     title='Accidentes por nivel de severidad')
    fig_sev.update_layout(showlegend=False)
    col2.plotly_chart(fig_sev, width='stretch')

    monthly = df.groupby('month').size().reset_index(name='Accidentes')
    # Número de accidentes por mes.

    fig_line = px.line(monthly, x='month', y='Accidentes',
                       color_discrete_sequence=[COLORS[2]],
                       title='Accidentes por mes',
                       labels={'month': 'Mes', 'Accidentes': 'Número de accidentes'})
    st.plotly_chart(fig_line, width='stretch')

    col3, col4 = st.columns(2)

    heat = (df.groupby(['weekday', 'hour']).size().unstack(fill_value=0)
              .reindex(index=WEEKDAY_ORDER, columns=range(24), fill_value=0))
    # Tabla de accidentes por día de la semana y hora.

    fig_heat = px.imshow(heat, color_continuous_scale='Blues', aspect='auto',
                         title='Accidentes por día de la semana y hora',
                         labels={'x': 'Hora', 'y': 'Día', 'color': 'Accidentes'})
    col3.plotly_chart(fig_heat, width='stretch')

    weather = df['weather'].value_counts().head(10).reset_index()
    weather.columns = ['Clima', 'Accidentes']
    # Las 10 condiciones de clima más frecuentes.

    fig_weather = px.bar(weather, x='Accidentes', y='Clima', orientation='h',
                         color_discrete_sequence=[COLORS[1]],
                         title='Top 10 condiciones de clima')
    fig_weather.update_layout(yaxis={'categoryorder': 'total ascending'})
    col4.plotly_chart(fig_weather, width='stretch')

    muestra = df.sample(min(5000, len(df)), random_state=42)
    # Muestra de puntos para que el mapa cargue rápido.

    fig_map = px.scatter(muestra, x='lng', y='lat', color='severity_label', opacity=0.6,
                         category_orders={'severity_label': SEVERITY_ORDER},
                         color_discrete_map=SEVERITY_COLORS,
                         hover_data=['city', 'state', 'start_time', 'weather', 'duration_min'],
                         title=f'Ubicación de los accidentes (muestra de {len(muestra):,})',
                         labels={'lng': 'Longitud', 'lat': 'Latitud', 'severity_label': 'Severidad'})
    st.plotly_chart(fig_map, width='stretch')


def main():
    st.title("Panel de Accidentes de Tránsito - Estados Unidos (2016-2023)")
    st.caption('Proyecto Integrador - Big Data')

    df = load_data()
    options = create_filters(df)
    filtered = apply_filters(df, options)

    if filtered.empty:
        st.warning("No hay accidentes con los filtros seleccionados.")
        return
    # Si los filtros no dejan datos, se avisa y no se dibuja nada.

    show_kpis(filtered)
    show_charts(filtered)

    with st.expander("Ver datos filtrados"):
        st.dataframe(filtered.head(1000))


if __name__ == "__main__":
    main()
