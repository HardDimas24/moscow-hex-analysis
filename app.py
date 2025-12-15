import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import shape
from scripts.map_grid import get_moscow_polygon
from scripts.districts import load_districts

# =========================================================
# КОНФИГУРАЦИЯ СТРАНИЦЫ
# =========================================================
st.set_page_config(layout="wide", page_title="Гексагональная сетка Москвы")
st.title("Реновационный потенциал и качество среды Москвы (~2 км)")

METRICS = {
    "combined_score": "🏙️ Итоговый индекс (строительство)",
    "buildability_score": "🏗️ Возможность застройки (жильё + промзоны)",
    "urban_quality_score": "🌆 Качество городской среды",

    "renovation_score": "🏚️ Реновация жилфонда",
    "promzone_score": "🏭 Потенциал промзон",

    "metro_score": "🚇 Метро",
    "school_score": "🏫 Школы",
    "park_score": "🌳 Парки",
}

# =========================================================
# САЙДБАР
# =========================================================
with st.sidebar:
    st.header("Параметры отображения")

    metric = st.selectbox(
        "Выберите показатель:",
        options=list(METRICS.keys()),
        format_func=lambda x: METRICS[x],
    )

    show_border = st.checkbox("Показать границу Москвы", value=True)
    show_districts = st.checkbox("Показать районы", value=False)

# =========================================================
# ЗАГРУЗКА СОТ
# =========================================================
hex_gdf = gpd.read_file("hex_grid_with_score.gpkg", layer="hexes")

required = [
    "park_score",
    "school_score",
    "metro_score",
    "renovation_score",     
    "promzone_score",
]
missing = [c for c in required if c not in hex_gdf.columns]
if missing:
    st.error(f"Отсутствуют колонки: {missing}")
    st.stop()

# =========================================================
# RENOVATION FINAL = max(жильё, промзоны)
# =========================================================
hex_gdf["buildability_score"] = np.maximum(
    hex_gdf["renovation_score"].fillna(0),
    hex_gdf["promzone_score"].fillna(0),
)

# =========================================================
# QUALITY SCORE (БЕЗ РЕНОВАЦИИ)
# =========================================================
hex_gdf["urban_quality_score"] = (
    0.40 * hex_gdf["metro_score"].fillna(0)
    + 0.30 * hex_gdf["school_score"].fillna(0)
    + 0.30 * hex_gdf["park_score"].fillna(0)
)

# =========================================================
# FINAL SCORE (GATE)
# =========================================================
hex_gdf["combined_score"] = (
    hex_gdf["buildability_score"] * hex_gdf["urban_quality_score"]
)

st.write(f"Соты загружено: {len(hex_gdf):,}")

# =========================================================
# ЗАГРУЗКА ГРАНИЦ МОСКВЫ И РАЙОНОВ
# =========================================================
moscow_gdf = get_moscow_polygon()
districts_gdf = load_districts()

# =========================================================
# ОПРЕДЕЛЕНИЕ ЦАО
# =========================================================
ao_col = next((c for c in ["AO", "АО"] if c in districts_gdf.columns), None)
hex_gdf["is_cao"] = False

if ao_col:
    cao = districts_gdf[districts_gdf[ao_col] == "ЦАО"]
    if not cao.empty:
        centers = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy(
                hex_gdf["center_lon"], hex_gdf["center_lat"]
            ),
            crs="EPSG:4326",
        )
        joined = gpd.sjoin(
            centers, cao[["geometry"]], how="left", predicate="within"
        )
        hex_gdf["is_cao"] = joined.index_right.notna()

# =========================================================
# СТИЛИЗАЦИЯ СОТ
# =========================================================
def style_function_hex(feature):
    props = feature["properties"]

    if props.get("is_cao", False):
        return {
            "fillColor": "#777777",
            "color": "#555555",
            "weight": 1,
            "fillOpacity": 0.85,
        }

    score = max(0.0, min(1.0, props.get(metric, 0)))
    r = int(255 * (1 - score))
    g = int(120 + 135 * score)

    return {
        "fillColor": f"rgb({r},{g},0)",
        "color": "#444",
        "weight": 1,
        "fillOpacity": 0.65,
    }

# =========================================================
# КАРТА
# =========================================================
center = hex_gdf.geometry.union_all().centroid
m = folium.Map(
    location=[center.y, center.x],
    zoom_start=10,
    tiles="CartoDB positron",
)

# =========================================================
# GEOJSON
# =========================================================
features = []
for idx, row in hex_gdf.iterrows():
    features.append(
        {
            "type": "Feature",
            "geometry": row.geometry.__geo_interface__,
            "properties": {
                "hex_id": str(idx),
                "is_cao": bool(row["is_cao"]),
                "area_m2": float(row.get("area_m2", 0)),
                "park_score": round(row["park_score"], 2),
                "school_score": round(row["school_score"], 2),
                "metro_score": round(row["metro_score"], 2),
                "renovation_score": round(row["renovation_score"], 2),
                "promzone_score": round(row["promzone_score"], 2),
                "buildability_score": round(
                    row["buildability_score"], 2
                ),
                "urban_quality_score": round(row["urban_quality_score"], 2),
                "combined_score": round(row["combined_score"], 2),
            },
        }
    )

features_normal = [f for f in features if not f["properties"]["is_cao"]]
features_cao = [f for f in features if f["properties"]["is_cao"]]

# =========================================================
# СЛОИ НА КАРТЕ
# =========================================================
folium.GeoJson(
    {"type": "FeatureCollection", "features": features_normal},
    style_function=style_function_hex,
    highlight_function=lambda x: {"weight": 3, "color": "red"},
    tooltip=folium.GeoJsonTooltip(
        fields=["hex_id", "area_m2", metric],
        aliases=["ID", "Площадь (м²)", metric],
    ),
).add_to(m)

folium.GeoJson(
    {"type": "FeatureCollection", "features": features_cao},
    style_function=style_function_hex,
).add_to(m)

if show_border:
    folium.GeoJson(
        moscow_gdf,
        style_function=lambda f: {
            "color": "blue",
            "weight": 2.5,
            "fill": False,
        },
    ).add_to(m)

if show_districts:
    folium.GeoJson(
        districts_gdf,
        name="Районы",
        style_function=lambda f: {
            "fillColor": "#3388ff",
            "color": "#b40404",
            "weight": 1,
            "fillOpacity": 0.05,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["Район"],
            aliases=["Район"],
        ),
    ).add_to(m)

folium.LayerControl().add_to(m)

# =========================================================
# ДИСПЛЕЙ КАРТЫ
# =========================================================
st.subheader(f"Карта: {metric}")
st_folium(m, width=1100, height=700)

# =========================================================
# ТАБЛИЦА
# =========================================================
with st.expander("Первые соты"):
    st.write(
        hex_gdf.head(30)[
            [
                "renovation_score",
                "promzone_score",
                "buildability_score",
                "urban_quality_score",
                "combined_score",
            ]
        ]
    )

# =========================================================
# ЛУЧШИЕ РАЙОНЫ
# =========================================================
st.markdown("## 🏆 Топ-5 районов по привлекательности для строительства")

TOP_N_HEX = 10

district_scores = (
    hex_gdf.loc[~hex_gdf["is_cao"]]
    .dropna(subset=["district"])
    .sort_values("combined_score", ascending=False)
    .groupby("district")
    .head(TOP_N_HEX)
    .groupby("district")
    .agg(
        mean_top_score=("combined_score", "mean"),
        max_score=("combined_score", "max"),
        hex_count=("combined_score", "count"),
    )
    .sort_values("mean_top_score", ascending=False)
    .head(5)
    .reset_index()
)

district_scores.index = range(1, len(district_scores) + 1)

st.dataframe(
    district_scores.rename(
        columns={
            "district": "Район",
            "mean_top_score": "Средний score (TOP-10 сот)",
            "max_score": "Максимальный score",
            "hex_count": "Число учтённых сот",
        }
    ),
    use_container_width=True,
)