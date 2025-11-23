import streamlit as st
from shapely.geometry import MultiPolygon, Polygon
import pandas as pd
import geopandas as gpd

@st.cache_data
def load_districts(csv_path="districts.csv"):
    import ast, json
    df = pd.read_csv(csv_path)
    geom_col = df.columns[-1]

    def rings_to_polygon(rings):
        if not rings:
            return None
        exterior = [(lon, lat) for lat, lon in rings]
        return Polygon(exterior)

    geoms = []
    for v in df[geom_col]:
        if pd.isna(v):
            geoms.append(None)
            continue
        try:
            arr = ast.literal_eval(v)
        except Exception:
            try:
                arr = json.loads(v)
            except Exception:
                geoms.append(None)
                continue

        polys = []
        for poly_coords in arr:
            poly = rings_to_polygon(poly_coords)
            if poly is not None:
                polys.append(poly)

        if len(polys) == 0:
            geom = None
        elif len(polys) == 1:
            geom = polys[0]
        else:
            geom = MultiPolygon(polys)

        geoms.append(geom)

    gdf = gpd.GeoDataFrame(df, geometry=geoms, crs="EPSG:4326")
    gdf = gdf[gdf.geometry.notnull()]
    return gdf
