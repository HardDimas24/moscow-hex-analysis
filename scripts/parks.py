import ast
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon

def load_parks(json_path="data/parks.json"):
    df = pd.read_json(json_path, encoding="utf-8")
    park_polygons = []

    for i, geom_str in enumerate(df['geoData']):
        if pd.isna(geom_str):
            continue
        try:
            geom_dict = ast.literal_eval(geom_str)
        except:
            continue
        coords = geom_dict.get('coordinates', None)
        if not coords:
            continue
        try:
            if isinstance(coords[0][0][0], (float, int)):
                park_polygons.append(Polygon(coords[0]))
            else:
                for poly_coords in coords:
                    park_polygons.append(Polygon(poly_coords[0]))
        except:
            continue

    parks_gdf = gpd.GeoDataFrame(geometry=park_polygons, crs="EPSG:4326")
    parks_gdf["geometry"] = parks_gdf.buffer(0)
    print(f"Парков загружено: {len(parks_gdf)}")
    return parks_gdf

# -----------------------------
# Функция расчёта park_score
# -----------------------------
def calc_park_score(hex_poly, parks_gdf):
    hex_area = hex_poly.area
    total_ratio = 0
    for park_poly in parks_gdf.geometry:
        inter = park_poly.intersection(hex_poly)
        if not inter.is_empty:
            total_ratio += inter.area / hex_area

    if total_ratio < 0.05:
        return 0
    elif total_ratio <= 0.20:
        return (total_ratio - 0.05) / 0.15
    elif total_ratio <= 0.40:
        return 1 - (total_ratio - 0.20) / 0.20
    else:
        return 0