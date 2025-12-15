import math
import geopandas as gpd
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
import streamlit as st
import osmnx as ox

@st.cache_data
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