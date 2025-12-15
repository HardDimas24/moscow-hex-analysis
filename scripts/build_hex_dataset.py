from districts import load_districts
from hex_grid_generation import generate_hex_grid, add_administrative_info, get_moscow_polygon
from parks import load_parks, calc_park_score
from schools import load_schools, count_schools_per_hex
from transport import load_transport, calc_metro_score
from renovation import add_housing_renovation_scores, add_promzone_renovation_scores
from boost_neighbours import boost_neighbors

moscow_gdf = get_moscow_polygon()
hex_gdf = generate_hex_grid(moscow_gdf, hex_diameter_km=2.0)
districts_gdf = load_districts()
hex_gdf = add_administrative_info(hex_gdf, districts_gdf)

parks_gdf = load_parks("data/parks.json")

# Переводим в метрическую проекцию для расчёта площадей пересечения
hex_gdf_m = hex_gdf.to_crs(epsg=3857)
parks_gdf_m = parks_gdf.to_crs(epsg=3857)

# -----------------------------
# Считаем park_score
# -----------------------------
scores = []
for i, hex_poly in enumerate(hex_gdf_m.geometry):
    score = calc_park_score(hex_poly, parks_gdf_m)
    scores.append(score)
    if i < 5:
        print(f"Сота {i}: park_score={score:.3f}")

hex_gdf["park_score"] = scores

hex_gdf = boost_neighbors(hex_gdf,
                          column="park_score",
                          influence_radius_m=2000,
                          boost_factor=0.07)

schools_gdf = load_schools("data/schools.csv")
hex_gdf = count_schools_per_hex(hex_gdf, schools_gdf, max_good=4, alpha=1.0)

hex_gdf = boost_neighbors(hex_gdf,
                          column="school_score",
                          influence_radius_m=2000,
                          boost_factor=0.005)

# transport_gdf — твой метро + МЦД (EPSG:4326)
transport_gdf = load_transport()

# Переводим в метры
transport_gdf_m = transport_gdf.to_crs(epsg=3857)

# Считаем metro_score
metro_scores = []
for i, hex_poly in enumerate(hex_gdf_m.geometry):
    score = calc_metro_score(hex_poly, transport_gdf_m)
    metro_scores.append(score)
    if i < 5:
        print(f"Сота {i}: metro_score={score:.3f}")

hex_gdf["metro_score"] = metro_scores

hex_gdf = add_housing_renovation_scores(
    hex_gdf,
    houses_csv_path="data/houses.csv",
    year_from=1953,
    year_to=1972,
    x0=0.04,
    k=73.2
)

hex_gdf = add_promzone_renovation_scores(
    hex_gdf,
    promzone_json_path="data/promzone.json",
    x0=0.02,
    k=100)

hex_gdf.to_file("hex_grid_with_score.gpkg", layer="hexes", driver="GPKG")
print("Готово! Файл 'hex_grid_with_score.gpkg' сохранён.")