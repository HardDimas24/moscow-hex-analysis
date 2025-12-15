import math
import geopandas as gpd
from shapely.geometry import Polygon, Point
import osmnx as ox
from shapely.ops import unary_union

def make_hexagon(center_x, center_y, radius):
    angles_deg = [0, 60, 120, 180, 240, 300]
    pts = [(center_x + radius * math.cos(math.radians(a)), center_y + radius * math.sin(math.radians(a))) for a in angles_deg]
    return Polygon(pts)

def generate_hex_grid(_city_gdf, hex_diameter_km=2.0):
    city = gpd.GeoSeries([_city_gdf.geometry.iloc[0]], crs="EPSG:4326").to_crs(epsg=3857)
    poly = city.iloc[0]

    minx, miny, maxx, maxy = poly.bounds
    radius_m = (hex_diameter_km * 1000.0) / 2.0
    h_step = 1.5 * radius_m
    v_step = math.sqrt(3) * radius_m
    pad = max(radius_m*2, 1000)
    start_x = minx - pad
    end_x = maxx + pad
    start_y = miny - pad
    end_y = maxy + pad

    hexes, centers = [], []
    col = 0
    x = start_x
    while x <= end_x:
        y_offset = v_step / 2.0 if col % 2 == 1 else 0.0
        y = start_y + y_offset
        while y <= end_y:
            hex_poly = make_hexagon(x, y, radius_m)
            inter = hex_poly.intersection(poly)
            if not inter.is_empty:
                hexes.append(inter)
                centers.append((x, y))
            y += v_step
        x += h_step
        col += 1

    hex_gdf = gpd.GeoDataFrame({
        "geometry": hexes,
        "center_x": [c[0] for c in centers],
        "center_y": [c[1] for c in centers],
    }, crs="EPSG:3857")
    hex_gdf["hex_id"] = [f"hex_{i}" for i in range(len(hex_gdf))]
    hex_gdf = hex_gdf.set_index("hex_id").to_crs(epsg=4326)
    centers_gs = gpd.GeoSeries([Point(xy) for xy in zip(hex_gdf["center_x"], hex_gdf["center_y"])], crs="EPSG:3857")
    centers_wgs = centers_gs.to_crs(epsg=4326)
    hex_gdf["center_lon"] = centers_wgs.x.values
    hex_gdf["center_lat"] = centers_wgs.y.values
    hex_gdf_m = hex_gdf.to_crs(epsg=3857)
    hex_gdf["area_m2"] = hex_gdf_m.geometry.area.values
    return hex_gdf

def add_administrative_info(hex_gdf, districts_gdf):
    """
    Добавляет в hex_gdf:
    - AO     : административный округ
    - district : район

    Логика:
    1) spatial join (within) по центру соты
    2) fallback: ближайший район / AO по расстоянию
    """

    # --- Определяем названия колонок ---
    ao_col = next((c for c in ["AO", "АО"] if c in districts_gdf.columns), None)
    district_col = next(
        (c for c in ["Район", "район", "District", "district"] if c in districts_gdf.columns),
        None
    )

    if ao_col is None:
        raise ValueError("В districts_gdf не найдена колонка AO / АО")
    if district_col is None:
        raise ValueError("В districts_gdf не найдена колонка района")

    # --- Центры сот ---
    centers_gdf = gpd.GeoDataFrame(
        hex_gdf[["center_lon", "center_lat"]],
        geometry=gpd.points_from_xy(
            hex_gdf["center_lon"],
            hex_gdf["center_lat"]
        ),
        crs="EPSG:4326"
    )

    # --- 1. Основной spatial join (within) ---
    joined = gpd.sjoin(
        centers_gdf,
        districts_gdf[[ao_col, district_col, "geometry"]],
        how="left",
        predicate="within"
    )

    ao_series = joined[ao_col].copy()
    district_series = joined[district_col].copy()

    # --- 2. Fallback: nearest ---
    missing_idx = ao_series[ao_series.isna()].index

    if len(missing_idx) > 0:
        centers_m = centers_gdf.to_crs(epsg=3857)
        districts_m = districts_gdf[[ao_col, district_col, "geometry"]].to_crs(epsg=3857)

        for idx in missing_idx:
            point = centers_m.loc[idx].geometry
            distances = districts_m.geometry.distance(point)
            nearest_idx = distances.idxmin()

            ao_series.loc[idx] = districts_m.loc[nearest_idx, ao_col]
            district_series.loc[idx] = districts_m.loc[nearest_idx, district_col]

    # --- Записываем в hex_gdf ---
    hex_gdf = hex_gdf.copy()
    hex_gdf["AO"] = ao_series.values
    hex_gdf["district"] = district_series.values

    return hex_gdf

# -----------------------------
# Загружаем границу Москвы (OSM) без Новой Москвы
# -----------------------------
def get_moscow_polygon():
    gdf = ox.geocode_to_gdf("Moscow, Russia").to_crs(epsg=4326)
    geom0 = gdf.geometry.iloc[0]
    if geom0.geom_type == "MultiPolygon":
        largest_poly = max(geom0.geoms, key=lambda p: p.area)
    else:
        largest_poly = geom0
    moscow_gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[largest_poly])

    # Троицкий и Новомосковский АО
    troitsky = ox.geocode_to_gdf("Troitsky, Moscow, Russia").to_crs(epsg=4326)
    novomoskovsky = ox.geocode_to_gdf("Novomoskovsky, Moscow, Russia").to_crs(epsg=4326)
    new_moscow_poly = unary_union(list(troitsky.geometry) + list(novomoskovsky.geometry))

    def remove_new_moscow(geom):
        if geom.is_empty:
            return None
        diff = geom.difference(new_moscow_poly)
        if diff.is_empty:
            return None
        return diff

    moscow_gdf["geometry"] = moscow_gdf["geometry"].apply(remove_new_moscow)
    moscow_gdf = moscow_gdf[moscow_gdf["geometry"].notnull()]
    return moscow_gdf