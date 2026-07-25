"""Raster background prototype (ROADMAP.md Phase 1 follow-up to the DuckDB spike).

Pulls a real USGS US Topo image for a bbox straddling the 30-mile corridor
edge, then clips it to the actual corridor polygon shape (not just a bbox)
using it as a cutline - proving the "clip the background to the corridor"
step before building it out for real.

Uses basemap.nationalmap.gov's live export service, which is fine for a
small prototype pull like this one but is a shared interactive tile
service, not meant for bulk scraping. The production pipeline should pull
USGS's bulk-download products (US Topo GeoTIFFs / National Map Download
Manager) instead - see ROADMAP.md.
"""
import json
from pathlib import Path

import rasterio
import rasterio.mask
import requests

OUT_DIR = Path(__file__).parent / "data" / "spike"
EXPORT_URL = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/export"

# Chosen because it straddles the corridor edge (~82% inside, per corridor
# polygon check) rather than sitting entirely inside it - so the clip below
# actually removes visible pixels instead of being a no-op.
BBOX = (-74.6, 40.7, -73.3, 41.8)  # west, south, east, north (EPSG:4326)
WIDTH_PX = 1420
HEIGHT_PX = 1200


def fetch_export(bbox=BBOX, out_path=OUT_DIR / "topo_raw.png"):
    west, south, east, north = bbox
    params = {
        "bbox": f"{west},{south},{east},{north}",
        "bboxSR": 4326,
        "imageSR": 4326,
        "size": f"{WIDTH_PX},{HEIGHT_PX}",
        "format": "png32",
        "f": "image",
    }
    resp = requests.get(EXPORT_URL, params=params, timeout=60)
    resp.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(resp.content)
    return out_path


def georeference(png_path: Path, bbox=BBOX, out_path=OUT_DIR / "topo_raw.tif"):
    west, south, east, north = bbox
    transform = rasterio.transform.from_bounds(west, south, east, north, WIDTH_PX, HEIGHT_PX)
    with rasterio.open(png_path) as src:
        data = src.read()
        profile = src.profile

    profile.update(driver="GTiff", crs="EPSG:4326", transform=transform)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data)
    return out_path


def clip_to_corridor(geotiff_path: Path, corridor_path="data/spike/corridor.geojson", out_path=OUT_DIR / "topo_clipped.tif"):
    corridor = json.loads(Path(corridor_path).read_text())
    geoms = [f["geometry"] for f in corridor["features"]] if "features" in corridor else [corridor["geometry"]]

    with rasterio.open(geotiff_path) as src:
        clipped, clipped_transform = rasterio.mask.mask(src, geoms, crop=False, nodata=0)
        profile = src.profile

    profile.update(transform=clipped_transform)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(clipped)
    return out_path


def to_png(geotiff_path: Path, out_path: Path):
    with rasterio.open(geotiff_path) as src:
        data = src.read()
        profile = src.profile
    profile.update(driver="PNG")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data)


def main():
    print(f"Fetching USGS US Topo export for bbox {BBOX} ...")
    png_path = fetch_export()
    print(f"  -> {png_path}")

    print("Georeferencing as GeoTIFF (EPSG:4326)...")
    tif_path = georeference(png_path)
    print(f"  -> {tif_path}")

    print("Clipping to the real 30-mile corridor polygon (from spike_corridor.py)...")
    clipped_path = clip_to_corridor(tif_path)
    print(f"  -> {clipped_path}")

    to_png(tif_path, OUT_DIR / "topo_raw_view.png")
    to_png(clipped_path, OUT_DIR / "topo_clipped_view.png")
    print(f"Viewable PNGs -> {OUT_DIR}/topo_raw_view.png, {OUT_DIR}/topo_clipped_view.png")


if __name__ == "__main__":
    main()
