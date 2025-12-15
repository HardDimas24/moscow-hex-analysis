import math
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

def load_transport(metro_path="data/metro.csv", mcd_path="data/mcd.csv"):
    metro = pd.read_csv(metro_path, sep=None, engine='python', skiprows=1)
    mcd = pd.read_csv(mcd_path, sep=None, engine='python', skiprows=1)

    metro = metro.loc[:, ~metro.columns.str.contains("^Unnamed")]
    mcd = mcd.loc[:, ~mcd.columns.str.contains("^Unnamed")]

    mcd = mcd.rename(columns={
        'Наименование прохода станции МЦД': 'Наименование',
        'Долгота прохода в WGS-84': 'Долгота в WGS-84',
        'Широта прохода в WGS-84': 'Широта в WGS-84'
    })

    transport = pd.concat([metro, mcd], ignore_index=True)

    transport = transport.dropna(subset=['Долгота в WGS-84', 'Широта в WGS-84'])

    geometry = [
        Point(lon, lat)
        for lon, lat in zip(transport['Долгота в WGS-84'], transport['Широта в WGS-84'])
    ]

    transport_gdf = gpd.GeoDataFrame(transport, geometry=geometry, crs="EPSG:4326")

    print(f"Точек транспорта загружено: {len(transport_gdf)}")

    return transport_gdf

def calc_metro_score(hex_poly, transport_gdf):
    """
    hex_poly — сота в EPSG:3857 (метры)
    transport_gdf — точки метро в EPSG:3857
    """

    # ---- 1. Если станция внутри соты → score = 1 ----
    if transport_gdf.within(hex_poly).any():
        return 1.0

    # ---- 2. Иначе считаем расстояния ----
    dist_series = transport_gdf.distance(hex_poly)

    # расстояние до ближайшей станции
    min_d = dist_series.min()

    # количество станций в радиусах
    n300 = (dist_series <= 300).sum()
    n500 = (dist_series <= 500).sum()
    n800 = (dist_series <= 800).sum()

    # A. Экспонента расстояния
    D = math.exp(-min_d / 500)

    # B. Взвешенное количество станций
    S = (1.0*n300 + 0.6*n500 + 0.3*n800) / 5
    S = min(S, 1)  # нормировка

    # Итоговая метрика
    A = 0.7 * D + 0.3 * S

    return A