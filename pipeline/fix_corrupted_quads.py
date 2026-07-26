"""Fix known-corrupted USGS US Topo quads.

Three quads (out of 1,654) failed a full-read validation with LZW decode
errors: NC_Glade_Valley, VA_Marion, WV_Princeton. Confirmed genuinely
corrupted at the source (a byte-exact re-download of NC_Glade_Valley still
failed), not a truncated download on our end.

Strategy per quad:
1. Re-download once (cheap, and not every quad has been double-checked this
   way - only NC_Glade_Valley was confirmed byte-exact-and-still-bad).
2. If still bad, fall back to basemap.nationalmap.gov's live export service
   (the same one validated in spike_raster_clip.py) for that quad's exact
   bounding box (from the ustopo_current.csv metadata inventory) - producing
   a substitute raster covering the same footprint, saved alongside the
   originals so the mosaic step can use it as a drop-in replacement.
"""

from pathlib import Path

import duckdb
import rasterio
import requests

QUADS_DIR = Path(__file__).parent / "data" / "raw" / "topo_quads"
METADATA_CSV = Path(__file__).parent / "data" / "raw" / "topo_metadata" / "ustopo_current.csv"
FALLBACK_DIR = Path(__file__).parent / "data" / "raw" / "topo_quads_fallback"
EXPORT_URL = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/export"

BAD_QUADS = {
    "NC_Glade_Valley": "NC/NC_Glade_Valley_20220908_TM_geo.tif",
    "VA_Marion": "VA/VA_Marion_20220916_TM_geo.tif",
    "WV_Princeton": "WV/WV_Princeton_20230615_TM_geo.tif",
}


def validate(path: Path) -> bool:
    try:
        with rasterio.open(path) as src:
            src.read(1)
        return True
    except Exception:
        return False


def redownload(path: Path) -> bool:
    state = path.parts[-2]
    filename = path.name
    url = f"https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/USTopo/GeoTIFF/{state}/{filename}"
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return validate(path)


def fetch_fallback(quad_key: str, out_path: Path):
    con = duckdb.connect()
    con.execute(f"CREATE TABLE quads AS SELECT * FROM read_csv_auto('{METADATA_CSV.as_posix()}')")
    row = con.execute(f"""
        SELECT westbc, eastbc, northbc, southbc FROM quads
        WHERE product_filename LIKE '{quad_key}%'
    """).fetchone()
    west, east, north, south = row

    # Small margin so the substitute fully covers the original quad's footprint.
    margin = 0.01
    params = {
        "bbox": f"{west - margin},{south - margin},{east + margin},{north + margin}",
        "bboxSR": 4326,
        "imageSR": 4326,
        "size": "2400,2400",
        "format": "png32",
        "f": "image",
    }
    resp = requests.get(EXPORT_URL, params=params, timeout=90)
    resp.raise_for_status()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    png_path = out_path.with_suffix(".png")
    png_path.write_bytes(resp.content)

    transform = rasterio.transform.from_bounds(west - margin, south - margin, east + margin, north + margin, 2400, 2400)
    with rasterio.open(png_path) as src:
        data = src.read((1, 2, 3))  # drop the alpha band - bulk quads are 3-band RGB, and
        profile = src.profile  # merge() requires matching band counts across inputs
    profile.update(driver="GTiff", crs="EPSG:4326", transform=transform, count=3)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data)
    png_path.unlink()


def main():
    for quad_key, rel_path in BAD_QUADS.items():
        path = QUADS_DIR / rel_path
        print(f"{quad_key}: re-downloading...")
        if redownload(path):
            print("  fixed by re-download.")
            continue

        print("  still corrupted after re-download - falling back to live export service...")
        fallback_path = FALLBACK_DIR / f"{quad_key}.tif"
        fetch_fallback(quad_key, fallback_path)
        if validate(fallback_path):
            print(f"  fallback substitute created -> {fallback_path}")
        else:
            print(f"  FALLBACK ALSO FAILED for {quad_key} - needs manual attention")


if __name__ == "__main__":
    main()
