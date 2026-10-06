"""Decision 54, wave 2: a GIS file read whole, one row per feature (the `gis_file` kind).

    gis_file(key)   a KML, KMZ, GPX, GeoJSON, zipped shapefile, zip of KML or GPX files, or CSV of points

pipeline/ELT.md, "Loading everything the clubs publish (decision 54)", wave 2:
"GIS files: KML, KMZ, GPX, GeoJSON, shapefiles, Google My Maps | one `gis_file`
kind | the kind, and a change check per file (ETag or length, never a site-wide
validator)". It lives here rather than in extract/_kinds.py, which is long
enough, and is a builder like the rest: it takes a sources.json key, never a
URL, so a club file cannot fetch a file the registry does not hold.

THE ROW. One per feature: a KML or KMZ placemark, a GPX waypoint, route or
track, a GeoJSON feature, a shapefile record, or a CSV row. Every row carries
`source_file` (the file's URL, `#<member>` added for a file read out of a zip)
and `feature_index` (its position in that file, counted from 0), then the
file's own properties flattened one column each, then `geometry` as GeoJSON
under rule 1's JSON hint. `feature_index` is a position, which a re-saved file
renumbers, so it is never a key on its own (decision 40); the measured key on
each sources.json row names what is.

EVERY PROPERTY LANDS AS TEXT: a string as the file spells it, anything else as
its JSON (`1.5`, `true`, an object). A file declares no field types the way an
ArcGIS layer's `fields` do, so a column typed from one month's values could
change type the next, which dlt splits into a variant column no staging model
reads (ELT.md, "dlt configuration requirements"). Text cannot drift; the base
model casts what it reads (Reasoned).

What each format's own columns are:
- KML and KMZ: `folder` (the folders the placemark sits in, outermost first,
  joined by " / "), `name`, `description` (as served, HTML or plain),
  `style_url`, `placemark_id`, then each ExtendedData `Data` and `SimpleData`
  value under its own name. A name that collides with one of those, as BMECC's
  `Name` does with `name`, lands as `property_<name>`. A NetworkLink is not
  followed: it is a pointer to another file, which needs a registry row of its
  own, and the read says so.
- GPX: `feature_kind` (`waypoint`, `route` or `track`), and each child element
  GPX names (`name`, `desc`, `cmt`, `sym`, `type`, `src`, `ele`, `time`,
  `number`), a `link`'s href as `link`. Each vertex's `<ele>` is its Z.
- GeoJSON: `feature_id` (the feature's own `id`), then its properties.
- Shapefile: its .dbf columns. CSV: its columns, named by the row's
  `header_row` (the line they are on, 1 unless a title line sits above them),
  a repeated name landing as `property_<name>`, and, where the row names an
  `as_of_label`, `source_as_of`: the date the sheet gives itself above the
  header, verbatim.

PERSON FIELDS never load (ELT.md, "Who may publish", rule 8): extract/_kinds.py's
PersonRule leaves out a property whose name is in PERSON_FIELDS or the row's
`person_fields`, or reads as a person's by PERSON_SHAPED unless the row's
`not_person_fields` clears it, before dlt sees the row, and the read prints it. A free
text column that carries a person's details is the row's `person_fields` too
(decision 59), since rule 8 excludes in dlt and never redacts in dbt.

THE CHANGE CHECK is per file (rule 4): a HEAD of each file, and its ETag, else
its Last-Modified with its Content-Length, never one validator for a whole
site. Any file that sends neither makes the answer UNKNOWN, and the dataset is
read in full; FRESH needs every file's validator unchanged. Google My Maps sends
neither (`cache-control: no-store`, measured 2026-10-04 on 9 exports), so a My
Maps dataset is read every run.

THE PROOF for an allowed zero, and the count every read is held to, is the
file's own feature count read in the same run: the rows are built from the very
documents that are counted, so the proof is exact (Resource.exact_proof). A file
that parses to no feature at all is a broken read for every type here but one a
row allows to be empty, never a quiet trail.

WHAT A FILE MUST LOOK LIKE before it is read: the format its row declares (an
HTML page served where a KML was is a moved file or a wall, and raises), in
longitude-latitude degrees. A GeoJSON `crs` other than CRS84 or EPSG:4326, a
shapefile whose .prj is projected, or a first vertex outside +-180/+-90 raises,
because a reprojection needs a library the extract job does not pin
(requirements-extract.in: no pyproj, no GDAL), and a file read in the wrong
coordinates would land a trail in the ocean.

ACCESS: every request sends lib/user_agent.py's USER_AGENT through
extract/_kinds.py's session(), and passes extract/_notices.py's per-host gate,
POLITE_SECONDS after the last request to that host ended, or the row's
`crawl_delay` where the host's robots.txt asks for more. robots.txt is read when
a row is registered (decision 53, "Access is checked, never assumed"), and a
row records what it said. A wall (extract/_notices.py's wall()) raises, and so
does a redirect to another host the row does not name in `redirect_hosts`
(extract/_notices.py's redirect_refused).
"""

from __future__ import annotations

import csv
import io
import json
import re
import struct
import xml.etree.ElementTree as ElementTree
import zipfile
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from extract import _kinds, _notices
from extract._contract import Resource
from lib.freshness_state import Freshness, compare_marker
from lib.http_retry import request_with_retry

#: The formats a row's `file_format` may name.
FORMATS = ("kml", "kmz", "gpx", "geojson", "shapefile_zip", "zip", "csv_points")

#: The gap kept between two requests to one host when its robots.txt asks for none: decision 53's inventory
#: rule ("at least 2 s between requests to one host otherwise"), extract/_notices.py's DEFAULT_HOST_GAP_SECONDS.
#: A courtesy, not a measurement of what any host can bear (@unvalidated; a host telling us otherwise settles it).
POLITE_SECONDS = _notices.DEFAULT_HOST_GAP_SECONDS

#: The columns every row carries, whatever its format, which a property never overwrites.
BASE_COLUMNS = ("source_file", "feature_index", "geometry")

#: Each format's own columns, which a property of the same name never overwrites either.
OWN_COLUMNS = {
    "kml": ("folder", "name", "description", "style_url", "placemark_id"),
    "gpx": ("feature_kind", "name", "desc", "cmt", "sym", "type", "src", "ele", "time", "number", "link"),
    "geojson": ("feature_id",),
}

GEOJSON_GEOMETRIES = frozenset(
    {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon", "GeometryCollection"}
)
#: The `crs` names that mean longitude-latitude degrees (RFC 7946's default, and the old GeoJSON spec's spellings).
LONLAT_CRS = frozenset(
    {"urn:ogc:def:crs:OGC:1.3:CRS84", "urn:ogc:def:crs:OGC::CRS84", "urn:ogc:def:crs:EPSG::4326", "EPSG:4326", "CRS84"}
)


class GisFileUnreadable(ValueError):
    """The file answered, and is not the file its row registers: another format, a wall, a projected CRS."""


def _canonical(marker: dict) -> str:
    return json.dumps(marker, sort_keys=True)


def _text(value) -> str | None:
    """A property value as it lands: text as spelled, None as null, anything else as its JSON."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _normal(name: str) -> str:
    """A column name as dlt's sql_ci_v1 naming would fold it, near enough to see two names that would collide."""
    return re.sub(r"[^0-9a-z]+", "_", name.lower()).strip("_")


def _local(tag: str) -> str:
    """An XML tag without its namespace: KML 2.1 and 2.2, GPX 1.0 and 1.1 are read alike."""
    return tag.rsplit("}", 1)[-1]


def _check_lonlat(geometry: dict | None, where: str) -> None:
    """Raise when the first vertex is not a longitude and latitude in degrees."""
    if not geometry:
        return
    coordinates = geometry.get("coordinates")
    if geometry.get("type") == "GeometryCollection":
        for part in geometry.get("geometries") or []:
            _check_lonlat(part, where)
            return
        return
    while isinstance(coordinates, list) and coordinates and isinstance(coordinates[0], list):
        coordinates = coordinates[0]
    if not coordinates:
        return
    lon, lat = coordinates[0], coordinates[1]
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise GisFileUnreadable(f"{where}: a first vertex of ({lon}, {lat}) is not longitude-latitude degrees")


# --- KML and KMZ ----------------------------------------------------------------


def _kml_positions(text: str | None) -> list[list[float]]:
    """A KML `coordinates` value, `lon,lat[,alt]` tuples split by whitespace, as GeoJSON positions, altitude kept."""
    positions = []
    for token in (text or "").split():
        parts = [part for part in token.split(",") if part != ""]
        if len(parts) >= 2:
            positions.append([float(part) for part in parts[:3]])
    return positions


def _find(element, name: str):
    return next((child for child in element if _local(child.tag) == name), None)


def _findall(element, name: str):
    return [child for child in element if _local(child.tag) == name]


def _ring(element) -> list[list[float]]:
    ring = _find(element, "LinearRing")
    return _kml_positions(_find(ring, "coordinates").text if ring is not None and _find(ring, "coordinates") is not None else "")


KML_GEOMETRIES = ("Point", "LineString", "LinearRing", "Polygon", "MultiGeometry", "Track", "MultiTrack")


def _kml_geometry(element) -> dict | None:
    """One KML geometry element as GeoJSON, or None for one with no coordinates or a kind this reader does not know."""
    tag = _local(element.tag)
    if tag in ("Point", "LineString", "LinearRing"):
        coordinates = _find(element, "coordinates")
        positions = _kml_positions(coordinates.text if coordinates is not None else "")
        if not positions:
            return None
        if tag == "Point":
            return {"type": "Point", "coordinates": positions[0]}
        if tag == "LinearRing":
            return {"type": "Polygon", "coordinates": [positions]}
        return {"type": "LineString", "coordinates": positions} if len(positions) > 1 else None
    if tag == "Polygon":
        outer = _find(element, "outerBoundaryIs")
        rings = [_ring(outer)] if outer is not None else []
        rings += [_ring(inner) for inner in _findall(element, "innerBoundaryIs")]
        rings = [ring for ring in rings if ring]
        return {"type": "Polygon", "coordinates": rings} if rings else None
    if tag == "Track":
        positions = []
        for coord in element:
            if _local(coord.tag) == "coord":
                parts = (coord.text or "").split()
                if len(parts) >= 2:
                    positions.append([float(part) for part in parts[:3]])
        return {"type": "LineString", "coordinates": positions} if len(positions) > 1 else None
    if tag in ("MultiGeometry", "MultiTrack"):
        parts = [_kml_geometry(child) for child in element if _local(child.tag) in KML_GEOMETRIES]
        parts = [part for part in parts if part is not None]
        if not parts:
            return None
        kinds = {part["type"] for part in parts}
        if len(kinds) == 1 and kinds <= {"Point", "LineString", "Polygon"}:
            kind = kinds.pop()
            return {"type": f"Multi{kind}", "coordinates": [part["coordinates"] for part in parts]}
        return {"type": "GeometryCollection", "geometries": parts}
    return None


def _put(row: dict, name: str | None, value, reserved: set[str]) -> None:
    """Add one property under its own name, or `property_<name>` where that would collide with a column already set."""
    if not name:
        return
    column = name
    if _normal(column) in reserved:
        column = f"property_{name}"
        n = 2
        while _normal(column) in reserved:
            column, n = f"property_{name}_{n}", n + 1
    reserved.add(_normal(column))
    row[column] = _text(value)


_PREFIXED = re.compile(rb"[<\s/]([A-Za-z_][\w.-]*):[A-Za-z_][\w.-]*")
_DECLARED = re.compile(rb"xmlns:([A-Za-z_][\w.-]*)\s*=")


def _xml_root(body: bytes, source: str):
    """A document's root element, tolerating one fault Google Earth itself tolerates: a prefix never declared.

    NBATC's NBATC_Trails_015.kml puts `xsi:schemaLocation` on its <Document>
    with no `xmlns:xsi` anywhere (read 2026-10-04), which a strict parser
    refuses as "unbound prefix". Each such prefix is declared on the root,
    under a namespace that says it was made up here, and the document is parsed
    again; nothing a row reads sits in that namespace.
    """
    try:
        return ElementTree.fromstring(body)
    except ElementTree.ParseError as error:
        if "unbound prefix" not in str(error):
            raise GisFileUnreadable(f"{source}: not XML ({error})") from error
    used = set(_PREFIXED.findall(body)) - set(_DECLARED.findall(body)) - {b"xml", b"xmlns", b"http", b"https"}
    declarations = b"".join(b' xmlns:%s="urn:ourhike:undeclared:%s"' % (prefix, prefix) for prefix in sorted(used))
    start = re.search(rb"<(?![?!])[A-Za-z_][\w.:-]*", body)
    if start is None:
        raise GisFileUnreadable(f"{source}: not XML (no root element)")
    patched = body[: start.end()] + declarations + body[start.end() :]
    try:
        return ElementTree.fromstring(patched)
    except ElementTree.ParseError as error:
        raise GisFileUnreadable(f"{source}: not XML ({error})") from error


def parse_kml(body: bytes, source: str) -> tuple[list[dict], int]:
    """Every Placemark in a KML document, in document order: (rows, NetworkLinks not followed)."""
    root = _xml_root(body, source)
    if _local(root.tag) != "kml":
        raise GisFileUnreadable(f"{source}: the document is <{_local(root.tag)}>, not <kml>")
    rows: list[dict] = []
    links = 0

    def walk(node, folders: tuple[str, ...]) -> None:
        nonlocal links
        for child in node:
            tag = _local(child.tag)
            if tag == "Folder":
                name = _find(child, "name")
                walk(child, (*folders, (name.text or "").strip() if name is not None else ""))
            elif tag == "Document":
                walk(child, folders)
            elif tag == "NetworkLink":
                links += 1
            elif tag == "Placemark":
                row: dict = {"source_file": source, "feature_index": len(rows)}
                for column in ("name", "description", "styleUrl"):
                    element = _find(child, column)
                    row["style_url" if column == "styleUrl" else column] = element.text if element is not None else None
                row["folder"] = " / ".join(folders) if folders else None
                row["placemark_id"] = child.get("id")
                reserved = {_normal(name) for name in (*BASE_COLUMNS, *OWN_COLUMNS["kml"])}
                extended = _find(child, "ExtendedData")
                if extended is not None:
                    for data in extended.iter():
                        local = _local(data.tag)
                        if local == "Data":
                            value = _find(data, "value")
                            _put(row, data.get("name"), value.text if value is not None else None, reserved)
                        elif local == "SimpleData":
                            _put(row, data.get("name"), data.text, reserved)
                geometry = next((g for g in child if _local(g.tag) in KML_GEOMETRIES), None)
                row["geometry"] = _kml_geometry(geometry) if geometry is not None else None
                _check_lonlat(row["geometry"], source)
                rows.append(row)

    walk(root, ())
    return rows, links


def _kmz_document(body: bytes, source: str) -> tuple[bytes, str]:
    """A KMZ's main document: `doc.kml` where it has one, else its first .kml at the shallowest depth."""
    archive = _zip(body, source)
    names = [name for name in archive.namelist() if name.lower().endswith(".kml") and not _skipped_member(name)]
    if not names:
        raise GisFileUnreadable(f"{source}: the KMZ holds no .kml")
    chosen = "doc.kml" if "doc.kml" in names else sorted(names, key=lambda name: (name.count("/"), name))[0]
    return archive.read(chosen), chosen


# --- GPX ------------------------------------------------------------------------

GPX_TEXT = ("name", "cmt", "desc", "src", "sym", "type", "number")


def _gpx_position(point) -> list[float] | None:
    try:
        position = [float(point.get("lon")), float(point.get("lat"))]
    except (TypeError, ValueError):
        return None
    ele = _find(point, "ele")
    if ele is not None and (ele.text or "").strip():
        try:
            position.append(float(ele.text))
        except ValueError:
            pass
    return position


def _gpx_row(element, kind: str, source: str, index: int, geometry: dict | None) -> dict:
    row: dict = {"source_file": source, "feature_index": index, "feature_kind": kind}
    for name in GPX_TEXT:
        child = _find(element, name)
        row[name] = child.text if child is not None else None
    link = _find(element, "link")
    row["link"] = (link.get("href") or link.text) if link is not None else None
    if kind == "waypoint":
        for name in ("ele", "time"):
            child = _find(element, name)
            row[name] = child.text if child is not None else None
    else:
        row["ele"], row["time"] = None, None
    row["geometry"] = geometry
    _check_lonlat(geometry, source)
    return row


def parse_gpx(body: bytes, source: str) -> list[dict]:
    """Every waypoint, route and track of a GPX file, in document order: a track's segments are one MultiLineString."""
    root = _xml_root(body, source)
    if _local(root.tag) != "gpx":
        raise GisFileUnreadable(f"{source}: the document is <{_local(root.tag)}>, not <gpx>")
    rows: list[dict] = []
    for element in root:
        tag = _local(element.tag)
        if tag == "wpt":
            position = _gpx_position(element)
            geometry = {"type": "Point", "coordinates": position} if position else None
            rows.append(_gpx_row(element, "waypoint", source, len(rows), geometry))
        elif tag == "rte":
            line = [p for p in (_gpx_position(point) for point in _findall(element, "rtept")) if p]
            geometry = {"type": "LineString", "coordinates": line} if len(line) > 1 else None
            rows.append(_gpx_row(element, "route", source, len(rows), geometry))
        elif tag == "trk":
            segments = []
            for segment in _findall(element, "trkseg"):
                line = [p for p in (_gpx_position(point) for point in _findall(segment, "trkpt")) if p]
                if len(line) > 1:  # a one-point segment is not a line, and GeoJSON has no shape for it
                    segments.append(line)
            if not segments:
                geometry = None
            elif len(segments) == 1:
                geometry = {"type": "LineString", "coordinates": segments[0]}
            else:
                geometry = {"type": "MultiLineString", "coordinates": segments}
            rows.append(_gpx_row(element, "track", source, len(rows), geometry))
    return rows


# --- GeoJSON --------------------------------------------------------------------


def parse_geojson(body: bytes, source: str) -> list[dict]:
    """Every feature of a GeoJSON document: a FeatureCollection's features, a lone Feature, or a bare geometry."""
    try:
        document = json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as error:
        raise GisFileUnreadable(f"{source}: not JSON ({error})") from error
    if not isinstance(document, dict):
        raise GisFileUnreadable(f"{source}: the document is not a GeoJSON object")
    crs = ((document.get("crs") or {}).get("properties") or {}).get("name")
    if crs is not None and crs not in LONLAT_CRS:
        raise GisFileUnreadable(f"{source}: its crs is {crs!r}, and reprojecting needs a library the extract does not pin")
    kind = document.get("type")
    if kind == "FeatureCollection":
        features = document.get("features") or []
    elif kind == "Feature":
        features = [document]
    elif kind in GEOJSON_GEOMETRIES:
        features = [{"type": "Feature", "properties": {}, "geometry": document}]
    else:
        raise GisFileUnreadable(f"{source}: a GeoJSON document of type {kind!r}")
    rows = []
    for index, feature in enumerate(features):
        row: dict = {"source_file": source, "feature_index": index, "feature_id": _text(feature.get("id"))}
        reserved = {_normal(name) for name in (*BASE_COLUMNS, *OWN_COLUMNS["geojson"])}
        for name, value in (feature.get("properties") or {}).items():
            _put(row, name, value, reserved)
        row["geometry"] = feature.get("geometry")
        _check_lonlat(row["geometry"], source)
        rows.append(row)
    return rows


# --- Shapefile (zipped) ---------------------------------------------------------

# Shape types (ESRI's whitepaper, "ESRI Shapefile Technical Description", 1998): the plain, Z and M forms.
SHP_POINT, SHP_LINE, SHP_POLYGON, SHP_MULTIPOINT = (1, 11, 21), (3, 13, 23), (5, 15, 25), (8, 18, 28)


def _signed_area(ring: list[list[float]]) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:], strict=False)) / 2


def _shp_record(content: bytes) -> dict | None:
    """One .shp record's content as GeoJSON: points, multipoints, lines and polygons, Z kept where the type has it."""
    (shape_type,) = struct.unpack_from("<i", content, 0)
    if shape_type == 0:
        return None
    has_z = shape_type in (11, 13, 15, 18)
    if shape_type in SHP_POINT:
        x, y = struct.unpack_from("<2d", content, 4)
        position = [x, y]
        if has_z:
            position.append(struct.unpack_from("<d", content, 20)[0])
        return {"type": "Point", "coordinates": position}
    if shape_type in SHP_MULTIPOINT:
        (count,) = struct.unpack_from("<i", content, 36)
        points = [list(struct.unpack_from("<2d", content, 40 + 16 * n)) for n in range(count)]
        if has_z:
            z_at = 40 + 16 * count + 16
            for n, point in enumerate(points):
                point.append(struct.unpack_from("<d", content, z_at + 8 * n)[0])
        return {"type": "MultiPoint", "coordinates": points}
    if shape_type in SHP_LINE + SHP_POLYGON:
        parts_count, points_count = struct.unpack_from("<2i", content, 36)
        starts = list(struct.unpack_from(f"<{parts_count}i", content, 44))
        points_at = 44 + 4 * parts_count
        points = [list(struct.unpack_from("<2d", content, points_at + 16 * n)) for n in range(points_count)]
        if has_z:
            z_at = points_at + 16 * points_count + 16
            for n, point in enumerate(points):
                point.append(struct.unpack_from("<d", content, z_at + 8 * n)[0])
        parts = [points[start:end] for start, end in zip(starts, [*starts[1:], points_count], strict=True)]
        if shape_type in SHP_LINE:
            parts = [part for part in parts if len(part) > 1]
            if not parts:
                return None
            return (
                {"type": "LineString", "coordinates": parts[0]}
                if len(parts) == 1
                else {"type": "MultiLineString", "coordinates": parts}
            )
        # A clockwise ring is an outer ring and a counter-clockwise one a hole in the polygon before it (the whitepaper).
        polygons: list[list] = []
        for ring in parts:
            if len(ring) < 4:
                continue
            if _signed_area(ring) <= 0 or not polygons:
                polygons.append([ring])
            else:
                polygons[-1].append(ring)
        if not polygons:
            return None
        return (
            {"type": "Polygon", "coordinates": polygons[0]}
            if len(polygons) == 1
            else {"type": "MultiPolygon", "coordinates": polygons}
        )
    raise GisFileUnreadable(f"shape type {shape_type} is not one this reader knows")


def _dbf_records(body: bytes, encoding: str) -> list[dict | None]:
    """A dBASE III table's records as text, every value stripped, an empty one null, a deleted record None.

    None, never skipped: the .shp keeps a deleted record's geometry, and
    attributes are matched to geometries by position, so a skipped record
    shifted every later name onto the wrong point (review finding EXD-11).
    """
    count, header_length, record_length = struct.unpack_from("<IHH", body, 4)
    fields = []
    at = 32
    while at < header_length - 1 and body[at] != 0x0D:
        name = body[at : at + 11].split(b"\x00", 1)[0].decode(encoding, errors="replace")
        fields.append((name, body[at + 16]))
        at += 32
    records = []
    for n in range(count):
        start = header_length + n * record_length
        record = body[start : start + record_length]
        if not record:
            continue
        if record[:1] == b"*":
            records.append(None)
            continue
        values, offset = {}, 1
        for name, length in fields:
            value = record[offset : offset + length].decode(encoding, errors="replace").strip()
            values[name] = value or None
            offset += length
        records.append(values)
    return records


def parse_shapefile_zip(body: bytes, source: str, member: str | None = None) -> list[dict]:
    """A zipped shapefile's records, its .dbf columns beside each geometry. A projected .prj raises (the docstring)."""
    archive = _zip(body, source)
    shps = sorted(name for name in archive.namelist() if name.lower().endswith(".shp") and not _skipped_member(name))
    if member is not None:
        shps = [name for name in shps if name == member]
    if len(shps) != 1:
        raise GisFileUnreadable(f"{source}: {len(shps)} shapefiles in the zip; a row names the one it reads in `zip_members`")
    stem = shps[0][:-4]
    names = {name.lower(): name for name in archive.namelist()}
    prj = names.get(f"{stem}.prj".lower())
    if prj is not None:
        wkt = archive.read(prj).decode("latin-1")
        if "PROJCS" in wkt.upper() or "GEOGCS" not in wkt.upper():
            raise GisFileUnreadable(
                f"{source}: the shapefile's .prj is not geographic, and reprojecting needs a library the extract does not pin"
            )
    cpg = names.get(f"{stem}.cpg".lower())
    encoding = archive.read(cpg).decode("ascii").strip() if cpg is not None else "latin-1"
    dbf = names.get(f"{stem}.dbf".lower())
    records = _dbf_records(archive.read(dbf), encoding) if dbf is not None else []
    shp = archive.read(shps[0])
    rows, at, index = [], 100, 0
    label = f"{source}#{shps[0]}"
    while at + 8 <= len(shp):
        (length_words,) = struct.unpack_from(">i", shp, at + 4)
        content = shp[at + 8 : at + 8 + 2 * length_words]
        at += 8 + 2 * length_words
        record = records[index] if index < len(records) else {}
        if record is None:  # deleted in the .dbf: its geometry goes with it, and the index keeps its .shp position
            index += 1
            continue
        row: dict = {"source_file": label, "feature_index": index}
        reserved = {_normal(name) for name in BASE_COLUMNS}
        for name, value in record.items():
            _put(row, name, value, reserved)
        row["geometry"] = _shp_record(content)
        _check_lonlat(row["geometry"], label)
        rows.append(row)
        index += 1
    return rows


# --- CSV of points ----------------------------------------------------------------


def parse_csv_points(
    body: bytes, source: str, lat_field: str, lon_field: str, header_row: int = 1, as_of_label: str | None = None
) -> list[dict]:
    """A CSV's rows, every column as text, and a Point from the two columns the row names; no Point where either is not a number.

    `header_row` is the line the column names are on, counted from 1: a
    spreadsheet's export can open with a title line above them, as FMST's
    trailheads sheet does. A name the header repeats lands as
    `property_<name>` from its second use on, and the Point is read from the
    first column of each name, so a sheet listing a segment's two ends keeps
    both (FMST's `Latitude` twice). A row whose every cell is blank is a
    spreadsheet's spacing, not a feature, and is skipped; `feature_index`
    stays the row's position after the header.

    `as_of_label` names a cell above the header that a sheet dates itself
    by, FMST's `Current as of:` (decision 72): the next non-empty cell on
    that line lands verbatim on every row as `source_as_of`, so the date a
    card prints is the sheet's own on the day it was read. A sheet whose
    label or date has gone is unreadable, as a header without its columns
    is: the run says so rather than land the rows undated.
    """
    text = body.decode("utf-8-sig")
    if text.lstrip()[:1] == "<":
        raise GisFileUnreadable(f"{source}: answered markup, not CSV")
    lines = list(csv.reader(io.StringIO(text)))
    header = lines[header_row - 1] if 0 < header_row <= len(lines) else []
    if lat_field not in header or lon_field not in header:
        raise GisFileUnreadable(f"{source}: the CSV's header (line {header_row}) has no {lat_field!r} and {lon_field!r} columns")
    lat_at, lon_at = header.index(lat_field), header.index(lon_field)
    as_of = _csv_as_of(lines[: header_row - 1], as_of_label, source) if as_of_label else None
    rows = []
    for index, record in enumerate(lines[header_row:]):
        if not any(cell.strip() for cell in record):
            continue
        cells = [record[at].strip() if at < len(record) and record[at].strip() else None for at in range(len(header))]
        row: dict = {"source_file": source, "feature_index": index}
        reserved = {_normal(name) for name in BASE_COLUMNS}
        if as_of_label:
            row["source_as_of"] = as_of
            reserved.add(_normal("source_as_of"))
        for name, value in zip(header, cells, strict=True):
            _put(row, name, value, reserved)
        try:
            row["geometry"] = {"type": "Point", "coordinates": [float(cells[lon_at]), float(cells[lat_at])]}
        except (TypeError, ValueError):
            row["geometry"] = None
        _check_lonlat(row["geometry"], source)
        rows.append(row)
    return rows


def _csv_as_of(lines: list[list[str]], label: str, source: str) -> str:
    """The cell after `label` on the lines above a CSV's header, as the sheet writes it."""
    wanted = label.strip().casefold()
    for record in lines:
        cells = [cell.strip() for cell in record]
        if wanted in (cell.casefold() for cell in cells):
            after = cells[[cell.casefold() for cell in cells].index(wanted) + 1 :]
            value = next((cell for cell in after if cell), None)
            if value is None:
                raise GisFileUnreadable(f"{source}: the {label!r} cell above the header has no value beside it")
            return value
    raise GisFileUnreadable(f"{source}: no {label!r} cell above the header, which this row's as_of_label names")


# --- Zips -------------------------------------------------------------------------


def _zip(body: bytes, source: str) -> zipfile.ZipFile:
    if body[:2] != b"PK":
        raise GisFileUnreadable(f"{source}: not a zip (it starts {body[:15]!r})")
    return zipfile.ZipFile(io.BytesIO(body))


def _skipped_member(name: str) -> bool:
    """A zip member that is an archiver's own bookkeeping: macOS's resource forks, a folder, a dot-file."""
    base = name.rsplit("/", 1)[-1]
    return name.startswith("__MACOSX/") or name.endswith("/") or base.startswith(".")


ZIP_MEMBER_FORMATS = {".kml": "kml", ".gpx": "gpx", ".geojson": "geojson", ".json": "geojson"}


# --- The resource -------------------------------------------------------------------


@dataclass(frozen=True)
class GisFile(_kinds.PersonRuled, Resource):
    """A GIS file, or a dataset spread over several, read whole: one row per feature (the module docstring)."""

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def files(self) -> tuple[str, ...]:
        """The files the dataset is: the row's `files`, or its `url` alone."""
        entry = self.entry
        return tuple(entry.get("files") or [entry["url"]])

    @property
    def file_format(self) -> str:
        return self.entry["file_format"]

    @property
    def may_be_empty(self) -> bool:
        return super().may_be_empty or bool(self.entry.get("may_be_empty"))

    @property
    def exact_proof(self) -> bool:
        return True

    def _session(self) -> requests.Session:
        delay = max(POLITE_SECONDS, float(self.entry.get("crawl_delay") or 0))
        return _notices.polite(_kinds.session(), delay)

    def _request(self, http: requests.Session, url: str, method: str = "get") -> requests.Response:
        response = request_with_retry(url, session=http, method=method, timeout=120, label=f"{self.key} {url}")
        blocked = _notices.wall(response)
        if blocked:
            raise GisFileUnreadable(f"{self.key}: {url} answered as a wall ({blocked})")
        if refused := _notices.redirect_refused(self.entry, url, response.url):
            raise GisFileUnreadable(f"{self.key}: {refused}")
        return response

    @staticmethod
    def _validator(response: requests.Response) -> dict | None:
        """One file's own validator: its ETag, else its Last-Modified with its Content-Length, else None."""
        headers = response.headers
        if headers.get("ETag"):
            return {"etag": headers["ETag"]}
        if headers.get("Last-Modified") and headers.get("Content-Length"):
            return {"last_modified": headers["Last-Modified"], "content_length": headers["Content-Length"]}
        return None

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """A HEAD of every file; FRESH only when each file's own validator is the one the last load recorded."""
        http = self._session()
        files = {}
        try:
            for url in self.files:
                validator = self._validator(self._request(http, url, method="head"))
                if validator is None:
                    return Freshness.UNKNOWN, None
                files[url] = validator
        except (requests.RequestException, GisFileUnreadable) as error:
            print(f"  {self.key}: change check failed ({error}); reading it")
            return Freshness.UNKNOWN, None
        marker = {"files": files}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def column_hints(self) -> dict:
        return {
            "source_file": {"data_type": "text"},
            "feature_index": {"data_type": "bigint"},
            "geometry": {"data_type": "json"},
        }

    def dropped(self, names: set[str]) -> dict[str, str]:
        """Which of a file's property names never load, lower-cased, with the rule that drops each (the docstring).

        The row's PersonRule (extract/_kinds.py), over every name but this reader's own BASE_COLUMNS.
        """
        ours = {_normal(name) for name in BASE_COLUMNS}
        return self.person_rule.left_out(name for name in names if _normal(name) not in ours)

    def parse(self, body: bytes, url: str) -> list[dict]:
        """One file's rows, by the row's `file_format`."""
        entry, fmt = self.entry, self.file_format
        if fmt in ("kml", "kmz"):
            if fmt == "kmz":
                document, member = _kmz_document(body, url)
                source = f"{url}#{member}"
            else:
                document, source = body, url
            rows, links = parse_kml(document, source)
            if links:
                print(f"  {self.key}: {url} holds {links} NetworkLink(s), not followed; each needs a registry row of its own")
            return rows
        if fmt == "gpx":
            return parse_gpx(body, url)
        if fmt == "geojson":
            return parse_geojson(body, url)
        if fmt == "shapefile_zip":
            members = entry.get("zip_members") or [None]
            return [row for member in members for row in parse_shapefile_zip(body, url, member)]
        if fmt == "csv_points":
            return parse_csv_points(
                body, url, entry["lat_field"], entry["lon_field"], entry.get("header_row") or 1, entry.get("as_of_label")
            )
        if fmt == "zip":
            archive = _zip(body, url)
            wanted = tuple(suffix.lower() for suffix in entry.get("zip_members") or ZIP_MEMBER_FORMATS)
            rows = []
            for member in sorted(archive.namelist()):
                suffix = "." + member.rsplit(".", 1)[-1].lower() if "." in member else ""
                if _skipped_member(member) or not member.lower().endswith(wanted) or suffix not in ZIP_MEMBER_FORMATS:
                    continue
                source = f"{url}#{member}"
                inner = archive.read(member)
                member_format = ZIP_MEMBER_FORMATS[suffix]
                if member_format == "kml":
                    rows.extend(parse_kml(inner, source)[0])
                elif member_format == "gpx":
                    rows.extend(parse_gpx(inner, source))
                else:
                    rows.extend(parse_geojson(inner, source))
            return rows
        raise GisFileUnreadable(f"{self.key}: file_format {fmt!r} is not one of {FORMATS}")

    def rows(self, proofs: dict[str, int]):
        """Every feature of every file, read whole before the first row is yielded, the count held as the proof."""
        http = self._session()
        rows: list[dict] = []
        for url in self.files:
            response = self._request(http, url)
            rows.extend(self.parse(response.content, url))
        names = {name for row in rows for name in row}
        dropped = self.dropped(names)
        _kinds.report_shaped(self.key, dropped, names)
        proofs[self.table] = len(rows)
        print(f"  {self.key}: {len(rows)} features from {len(self.files)} file(s)")
        for row in rows:
            yield {name: value for name, value in row.items() if name.lower() not in dropped}


def gis_file(key: str, **overrides) -> GisFile:
    entry = _kinds.registry_entry(key)  # a key that is not registered fails at import, in the layout test, not mid-run
    if entry.get("file_format") not in FORMATS:
        raise KeyError(f"{key}: a gis_file row names its file_format, one of {FORMATS}")
    for url in entry.get("files") or [entry["url"]]:
        if urlparse(url).scheme not in ("https", "http"):
            raise KeyError(f"{key}: {url} is not an http(s) URL")
    if entry["file_format"] == "csv_points" and not (entry.get("lat_field") and entry.get("lon_field")):
        raise KeyError(f"{key}: a csv_points row names its lat_field and lon_field")
    header_row = entry.get("header_row", 1)
    if not isinstance(header_row, int) or isinstance(header_row, bool) or header_row < 1:
        raise KeyError(f"{key}: header_row is the header's line number, counted from 1")
    as_of_label = entry.get("as_of_label")
    if as_of_label is not None and not (
        entry["file_format"] == "csv_points" and isinstance(as_of_label, str) and as_of_label.strip() and header_row > 1
    ):
        raise KeyError(f"{key}: as_of_label names a cell above a csv_points header, so it needs a header_row past 1")
    return GisFile(key=key, **overrides)
