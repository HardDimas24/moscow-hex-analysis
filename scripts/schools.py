import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point

def load_schools(csv_path="data/schools.csv"):
    """Загружает школы из CSV с колонками lat, lon → GeoDataFrame."""
    df = pd.read_csv(csv_path)
    df = df[df["lat"].notnull() & df["lon"].notnull()]
    schools_gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326"
    )
    print(f"Загружено школ: {len(schools_gdf)}")
    return schools_gdf


def count_schools_per_hex(hex_gdf, schools_gdf, max_good=4, alpha=1.0):
    """
    Считает количество школ внутри каждой соты и добавляет school_score.

    max_good — при каком количестве школ достигается score = 1.0 (например, 4)
    alpha — крутизна кривой роста (0.7–1.2 обычно)
    """
    # --- Переводим в метрическую систему ---
    hex_m = hex_gdf.to_crs(epsg=3857).copy()
    schools_m = schools_gdf.to_crs(epsg=3857)

    # --- Обеспечим наличие hex_id как столбца ---
    if "hex_id" not in hex_m.columns:
        hex_m = hex_m.reset_index()

    # --- Пространственное соединение ---
    joined = gpd.sjoin(schools_m, hex_m, predicate="within")

    # --- Подсчёт количества школ по hex_id ---
    counts = joined.groupby("hex_id").size()

    # --- Добавляем столбец school_amount ---
    hex_m["school_amount"] = hex_m["hex_id"].map(counts).fillna(0).astype(int)

    # --- Расчёт school_score (экспоненциальное насыщение, 4+ школ = 1.0) ---
    c = hex_m["school_amount"].astype(float)
    num = 1 - np.exp(-alpha * c)
    den = 1 - np.exp(-alpha * max_good)
    hex_m["school_score"] = np.clip(num / den, 0, 1)

    # --- Возвращаем в исходную проекцию ---
    return hex_m.to_crs(epsg=4326)