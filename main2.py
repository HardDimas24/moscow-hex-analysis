import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
from map_grid import get_moscow_polygon
from districts import load_districts

st.set_page_config(layout="wide", page_title="Гексагональная сетка Москвы")

st.title("Гексагональная сетка Москвы (~2 km) — Folium + Streamlit")

# -----------------------------
# Параметры UI
# -----------------------------
with st.sidebar:
    st.header("Параметры отображения")

    metric = st.selectbox(
        "Выберите показатель для отображения:",
        options=["combined_score", "park_score", "school_score", "metro_score"],
        format_func=lambda x: {
            "combined_score": "🏙️ Общий индекс (парки + школы + метро)",
            "park_score": "🌳 Парки",
            "school_score": "🏫 Школы",
            "metro_score": "🚇 Метро"
        }[x]
    )

    show_border = st.checkbox("Показать границу Москвы", value=True)
    show_districts = st.checkbox("Показать районы", value=False)
    st.markdown("---")

# -----------------------------
# Загружаем hex-сетку
# -----------------------------
hex_file = "hex_grid_with_score.gpkg"
hex_gdf = gpd.read_file(hex_file, layer="hexes")

# ℹ️ Проверяем наличие metro_score
if "metro_score" not in hex_gdf.columns:
    st.error("В hex_grid_with_score.gpkg отсутствует колонка metro_score. Сначала рассчитайте её.")
    st.stop()

# Если нет combined_score — создаём
if "combined_score" not in hex_gdf.columns:
    hex_gdf["combined_score"] = (
        0.34 * hex_gdf.get("park_score", 0).fillna(0) +
        0.33 * hex_gdf.get("school_score", 0).fillna(0) +
        0.33 * hex_gdf.get("metro_score", 0).fillna(0)
    )

st.write(f"Соты загружено: {len(hex_gdf):,}")

moscow_gdf = get_moscow_polygon()
districts_gdf = load_districts()

# -----------------------------
# Функция окрашивания
# -----------------------------
def style_function_hex(feature):
    score = feature["properties"].get(metric, 0)
    r = int(255 * (1 - score))
    g = int(120 + 135 * score)
    b = 0
    return {"fillColor": f"rgb({r},{g},{b})", "color": "#444", "weight": 1, "fillOpacity": 0.6}

# -----------------------------
# Создаём карту
# -----------------------------
center = hex_gdf.geometry.union_all().centroid
m = folium.Map(location=[center.y, center.x], zoom_start=10, tiles="CartoDB positron")

# Подготовка данных для GeoJSON
features = []
for hex_id, row in hex_gdf.iterrows():
    features.append({
        "type": "Feature",
        "geometry": row.geometry.__geo_interface__,
        "properties": {
            "hex_id": hex_id,
            "center_lat": float(row.get("center_lat", 0)),
            "center_lon": float(row.get("center_lon", 0)),
            "area_m2": float(row.get("area_m2", 0)),
            "park_score": round(float(row.get("park_score", 0)), 2),
            "school_score": round(float(row.get("school_score", 0)), 2),
            "metro_score": round(float(row.get("metro_score", 0)), 2),
            "combined_score": round(float(row.get("combined_score", 0)), 2)
        }
    })

folium.GeoJson(
    {"type": "FeatureCollection", "features": features},
    name="Гексагональная сетка",
    style_function=style_function_hex,
    highlight_function=lambda x: {"weight": 3, "color": "red"},
    tooltip=folium.GeoJsonTooltip(
        fields=["hex_id", "center_lat", "center_lon", "area_m2", metric],
        aliases=["ID", "центр lat", "центр lon", "площадь (м²)", metric],
        localize=True
    )
).add_to(m)

# -----------------------------
# Граница и районы
# -----------------------------
if show_border:
    folium.GeoJson(
        moscow_gdf,
        name="Граница Москвы",
        tooltip="Москва",
        style_function=lambda f: {"color": "blue", "weight": 2.5, "fill": False, "opacity": 0.7}
    ).add_to(m)

if show_districts and not districts_gdf.empty:
    folium.GeoJson(
        districts_gdf,
        name="Районы",
        style_function=lambda f: {"fillColor": "#3388ff", "color": "#b40404", "weight": 1, "fillOpacity": 0.05},
        tooltip=folium.GeoJsonTooltip(
            fields=[col for col in ["Район", "AO", "АО"] if col in districts_gdf.columns][:2],
            aliases=["Район", "АО"],
            localize=True
        )
    ).add_to(m)

folium.LayerControl().add_to(m)

# -----------------------------
# Карта
# -----------------------------
st.subheader(f"Карта: {metric}")
st_folium(m, width=1100, height=700)

# -----------------------------
# Таблица
# -----------------------------
with st.expander("Показать первые соты (таблица)"):
    st.write(hex_gdf.head(30)[[
        "center_lat", "center_lon",
        "park_score", "school_score", "metro_score",
        "combined_score"
    ]])