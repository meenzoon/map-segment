import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point


def _cut_line(line: LineString, distance: float):
    """
    line을 시작점에서 distance만큼 떨어진 위치에서 두 개의 LineString으로 자름.
    distance가 0 또는 전체 길이보다 크면 원본 그대로 반환.
    """
    if distance <= 0.0 or distance >= line.length:
        return [LineString(line)]

    coords = list(line.coords)
    for i, p in enumerate(coords):
        pd = line.project(Point(p))
        if pd == distance:
            return [LineString(coords[: i + 1]), LineString(coords[i:])]
        if pd > distance:
            cp = line.interpolate(distance)
            cp_coord = (cp.x, cp.y)
            return [
                LineString(coords[:i] + [cp_coord]),
                LineString([cp_coord] + coords[i:]),
            ]

    # 혹시 루프를 다 돌 때까지 못 자른 경우
    return [LineString(line)]


def _split_line_by_length(line: LineString, seg_len: float):
    """
    하나의 LineString을 seg_len(예: 100m) 이하가 되도록 여러 LineString 세그먼트로 쪼갬.
    변곡점(각 vertex)마다 자르고, 길이가 seg_len보다 길면 추가로 자름.
    """
    segments = []
    coords = list(line.coords)

    for i in range(len(coords) - 1):
        sub_line = LineString([coords[i], coords[i + 1]])

        if sub_line.length > seg_len:
            current_sub = sub_line
            while current_sub.length > seg_len:
                first, rest = _cut_line(current_sub, seg_len)
                segments.append(first)
                current_sub = rest
            segments.append(current_sub)
        else:
            segments.append(sub_line)

    return segments


def _split_geometry_to_segments(geom, seg_len: float):
    """
    geometry가 LineString 또는 MultiLineString일 때
    seg_len 길이 기준으로 모두 잘라서 세그먼트 리스트 반환.
    """
    result = []
    if isinstance(geom, LineString):
        result.extend(_split_line_by_length(geom, seg_len))
    elif isinstance(geom, MultiLineString):
        for line in geom.geoms:
            result.extend(_split_line_by_length(line, seg_len))
    return result


def process_shapefile(
    in_path: str,
    out_path: str,
    out_file_type: str = "shp",  # "shp" 또는 "geojson"
    link_id_field: str = "link_id",
    id_mode: str = "dash",  # "dash" -> LINK-1, LINK-2 / "underscore" -> LINK_1, LINK_2
    seg_len: float = 100.0,
):
    """
    shp 파일에서 LINESTRING 링크를 읽어서 100m 단위(또는 seg_len)로 자른 Route Segment를 생성하고, 새 파일로 저장.
    """
    gdf = gpd.read_file(in_path)
    print(out_file_type)
    print("GeoJSON" if out_file_type == "geojson" else None)
    
    # meter 단위로 계산하기 위해서 UTM-K (EPSG:5179) 좌표계로 변환
    if gdf.crs != 'EPSG:5179':
        gdf = gdf.to_crs(epsg=5179)
    
    
    out_records = []

    for idx, row in gdf.iterrows():
        geom = row.geometry
        link_id = row[link_id_field]

        segments = _split_geometry_to_segments(geom, seg_len)

        # 세그먼트 순번 1, 2, 3, ...
        for i, seg in enumerate(segments, start=1):
            new_row = row.copy()
            # 새 ID 만들기
            if id_mode == "dash":
                new_id = f"{link_id}-{i}"
            else:
                new_id = f"{link_id}_{i}"

            new_row[link_id_field] = new_id
            new_row.geometry = seg
            new_row["len"] = seg.length
            out_records.append(new_row)

    out_gdf = gpd.GeoDataFrame(out_records, crs="EPSG:5179")
    out_gdf = out_gdf.to_crs(epsg=4326)
    out_gdf.to_file(out_path, driver=("GeoJSON" if out_file_type == "geojson" else None))


if __name__ == "__main__":
    # 사용 예시
    in_path = "out/route/link_20250903.shp"
    out_path = "out/output_route_segment.geojson"

    process_shapefile(
        in_path=in_path,
        out_path=out_path,
        link_id_field="link_id",  # 실제 필드명으로 변경
        id_mode="dash",  # "dash" 또는 "underscore"
        seg_len=100.0,  # 100m
    )
