"""Tidewater Appalachian Trail Club: warnings, from the Tye River ridgerunner reports' index PDF, hourly
(decision 53 phase B, 2026-10-03). Its licence is UNRESOLVED.

`tatc_ridgerunner_reports` reads the index PDF
(https://tidewateratc.com/wp-content/uploads/2026/08/Tye-River-Ridge-Runner-Reports.pdf, 202,242 bytes)
as one PageNotice over a PDF (extract/_notices.py): the registry's title, the PDF's own ModDate
(2026-08-03) and the bytes' sha256, and none of its text. It links about 71 weekly ATC RIMS 'Stewardship
Report Digest' PDFs, 2022 week 1 to 2026 week 13 (the inventory), covering the NBATC, ODATC and TATC
sections with per-assessment coordinates, downed-tree counts and campsite notes. The reports name ATC
staff with e-mail addresses, which is why the index, and not a report, is what is read, and why nothing
of either lands. Read live under our agent on 2026-10-03 after tidewateratc.com's robots.txt
(WooCommerce paths and /wp-admin/ only); the file's strong ETag ("31602-65825f25d092d") is a static
file's, so a conditional GET answers 304 between edits (`trust_validators`; @unvalidated, one read).

THE LICENCE IS THE MAINTAINER'S OPEN QUESTION. The reports are ATC ridgerunner output the club
republishes; whether atc_licence covers them has been open since the coverage audit, so the row is
`licence_basis: unresolved` and would not publish even once a mart reads it. The upload path is
dated (2026/08), so a newer index may arrive at a new URL. Severity is low ('not really an obstacle').

Before decision 53 phase B this file was the coverage audit's note (confirmed 2026-10-01, batch
c2_at_clubs_mid), which named the index and its reports.
"""

from extract._kinds import page_notice

CLAIMS = ("tatc_ridgerunner_reports",)
RESOURCES = [page_notice("tatc_ridgerunner_reports", trust_validators=True)]
