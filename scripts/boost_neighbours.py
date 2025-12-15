import numpy as np

def boost_neighbors(
    hex_gdf,
    column="park_score",
    influence_radius_m=2000,
    boost_factor=0.07,
    new_col=None,
    min_base_score=0.1
):
    """
    Усиливает значение score у соседних сот рядом с высокими.
    
    Работает с любым столбцом score (park_score, school_score и т.д.).
    - influence_radius_m — радиус влияния (в метрах)
    - boost_factor — доля разницы, добавляемая соседям (0.05–0.15 обычно)
    - new_col — если задано, результат сохраняется в новом столбце
    - min_base_score — минимальный порог, с которого сота начинает влиять на соседей
    """
    # --- Копируем и переводим в метрическую систему ---
    gdf_m = hex_gdf.to_crs(epsg=3857).copy()
    sindex = gdf_m.sindex
    scores = gdf_m[column].fillna(0).astype(float).copy()

    # --- Итерация по сотам ---
    for idx, row in gdf_m.iterrows():
        base_score = scores[idx]
        if base_score < min_base_score:
            continue  # очень слабые соты не распространяют влияние

        geom = row.geometry
        # Ищем кандидатов в радиусе
        possible_idx = list(sindex.intersection(geom.buffer(influence_radius_m).bounds))
        neighbors = gdf_m.iloc[possible_idx]
        neighbors = neighbors[neighbors.intersects(geom.buffer(influence_radius_m))]

        # Повышаем значения у соседей, если они слабее
        for n_idx in neighbors.index:
            if n_idx == idx:
                continue
            diff = base_score - scores[n_idx]
            if diff > 0:
                scores[n_idx] += boost_factor * diff

    # --- Ограничиваем диапазон ---
    boosted = np.clip(scores, 0, 1)

    # --- Обновляем GeoDataFrame ---
    result = gdf_m.copy()
    if new_col:
        result[new_col] = boosted
    else:
        result[column] = boosted

    return result.to_crs(epsg=4326)