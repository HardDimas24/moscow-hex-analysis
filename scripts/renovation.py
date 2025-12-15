import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
from shapely.ops import transform
from shapely import wkt
import pyproj

def add_housing_renovation_scores(
    hex_gdf,
    houses_csv_path="data/houses.csv",
    year_from=1953,
    year_to=1972,
    x0=0.04,
    k=73.2
):
    """
    Добавляет в hex_gdf:
    - renovation_score  : нормализованный (логистика) скор ∈ [0,1]

    hex_gdf:
        GeoDataFrame в EPSG:4326
        ОБЯЗАТЕЛЬНО должен содержать столбец area_m2

    houses.csv:
        geometry — WKT (MULTIPOLYGON)
        r_year   — год постройки
        CRS домов — EPSG:3857
    """

    # -----------------------------
    # 1. Загружаем дома
    # -----------------------------
    houses = pd.read_csv(houses_csv_path, sep=None, engine="python")
    houses = houses.dropna(subset=["geometry"])

    houses["geometry"] = houses["geometry"].apply(wkt.loads)
    houses_gdf = gpd.GeoDataFrame(houses, geometry="geometry", crs="EPSG:3857")

    # Убираем Z-координату
    def drop_z(geom):
        if geom.has_z:
            return transform(lambda x, y, z=None: (x, y), geom)
        return geom

    houses_gdf["geometry"] = houses_gdf["geometry"].apply(drop_z)

    # -----------------------------
    # 2. Фильтруем дома под реновацию
    # -----------------------------
    renov_houses = houses_gdf[
        (houses_gdf["r_year"] >= year_from) &
        (houses_gdf["r_year"] <= year_to)
    ].copy()

    if renov_houses.empty:
        hex_gdf["renovation_score_raw"] = 0.0
        hex_gdf["renovation_score_02"] = 0.0
        return hex_gdf

    renov_sindex = renov_houses.sindex

    # -----------------------------
    # 3. Подготовка трансформации
    # -----------------------------
    to_3857 = pyproj.Transformer.from_crs(
        "EPSG:4326", "EPSG:3857", always_xy=True
    ).transform

    # -----------------------------
    # 4. Функция расчёта raw-скора
    # -----------------------------
    def renovation_score_for_hex(hex_poly_wgs84, hex_area_m2):
        if hex_area_m2 <= 0:
            return 0.0

        hex_poly_m = transform(to_3857, hex_poly_wgs84)

        cand_idx = list(renov_sindex.intersection(hex_poly_m.bounds))
        if not cand_idx:
            return 0.0

        total_area = 0.0
        for house_poly in renov_houses.iloc[cand_idx].geometry:
            inter = house_poly.intersection(hex_poly_m)
            if not inter.is_empty:
                total_area += inter.area

        return float(min(total_area / hex_area_m2, 1.0))

    # -----------------------------
    # 5. Считаем renovation_score_raw
    # -----------------------------
    raw_scores = []
    for _, row in hex_gdf.iterrows():
        raw_scores.append(
            renovation_score_for_hex(
                row.geometry,
                row["area_m2"]
            )
        )
    raw_scores_arr = np.array(raw_scores, dtype=float)
    hex_gdf = hex_gdf.copy()

    # -----------------------------
    # 6. Логистическая нормализация
    # -----------------------------
    hex_gdf["renovation_score"] = (
        1 / (1 + np.exp(-k * (raw_scores_arr - x0)))
    )

    return hex_gdf

def swap_latlon(geom):
    # geom уже shapely geometry
    return transform(lambda x, y: (y, x), geom)

def add_promzone_renovation_scores(
    hex_gdf,
    promzone_json_path="data/promzone.json",
    x0=0.02,
    k=120
):
    """
    Добавляет:
    - promzone_score_raw
    - promzone_score
    """

    # -----------------------------
    # 1. Загружаем промзоны
    # -----------------------------
    df = pd.read_json(promzone_json_path)

    # статус
    df = df[df[1] == "Планируемый"]

    if df.empty:
        hex_gdf = hex_gdf.copy()
        hex_gdf["promzone_score_raw"] = 0.0
        hex_gdf["promzone_score"] = 0.0
        return hex_gdf

    df["geometry"] = df[14].apply(shape).apply(swap_latlon)

    prom_gdf = gpd.GeoDataFrame(
        df,
        geometry="geometry",
        crs="EPSG:4326"
    ).to_crs(epsg=3857)

    prom_sindex = prom_gdf.sindex

    # -----------------------------
    # 2. Трансформация сот
    # -----------------------------
    to_3857 = pyproj.Transformer.from_crs(
        "EPSG:4326", "EPSG:3857", always_xy=True
    ).transform

    # -----------------------------
    # 3. raw-метрика
    # -----------------------------
    def promzone_score_for_hex(hex_poly_wgs84, hex_area_m2):
        if hex_area_m2 <= 0:
            return 0.0

        hex_poly_m = transform(to_3857, hex_poly_wgs84)

        cand_idx = list(prom_sindex.intersection(hex_poly_m.bounds))
        if not cand_idx:
            return 0.0

        total_area = 0.0
        for prom_poly in prom_gdf.iloc[cand_idx].geometry:
            inter = prom_poly.intersection(hex_poly_m)
            if not inter.is_empty:
                total_area += inter.area

        return min(total_area / hex_area_m2, 1.0)

    # -----------------------------
    # 4. Считаем raw
    # -----------------------------
    raw_scores = np.array([
        promzone_score_for_hex(row.geometry, row["area_m2"])
        for _, row in hex_gdf.iterrows()
    ])

    hex_gdf = hex_gdf.copy()
    hex_gdf["promzone_score_raw"] = raw_scores

    # -----------------------------
    # 5. Сигмоида
    # -----------------------------
    hex_gdf["promzone_score"] = 1 / (
        1 + np.exp(-k * (raw_scores - x0))
    )

    return hex_gdf