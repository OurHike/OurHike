"""Smoky Mountains Hiking Club: challenges, its 900 Miler Club trail list read here (section K's hand-back, read
2026-10-10).

- `smhc_900_miler_trails`: the club's workbook of every official trail in Great Smoky Mountains National Park, the
  900 Miler Club's list (a member who hikes them all joins it). 157 trails on 2026-10-10, 238 sections between them,
  summing to 796.73 miles, the sheet's own total. One row a trail: its name, its total miles, the feet its sections
  sum to and how many it has, and the link.

The reader is extract/_sheet_content.py's ContentSheet with the `smhc_900_miler_trails` family: a conditional GET
with the file's own validators (Last-Modified 2024-09-21 with its Content-Length; the host sends no ETag), xlrd for
the .xls, and the one sheet '900 Mile Club Spreadsheet' read, never the file's properties, which name people. Its
column F, 'Date Completed', and G, notes, are a member's own checklist and are never read. smhclub.org answers the
link with one redirect to the club's Wild Apricot CDN, which its row names in `redirect_hosts`. Its row in
sources.json holds the terms as found (none), the live read and the measured key, the trail's name.

The trails are the park's (nps/), so this is the club's list of them, never a second copy of their lines. The
club's roster of members who finished, on the same page, is a list of people and is never read.
"""

from extract._sheet_content import content_sheet

CLAIMS = ("smhc_900_miler_trails",)
RESOURCES = [content_sheet("smhc_900_miler_trails", crawl_delay=10.0)]
