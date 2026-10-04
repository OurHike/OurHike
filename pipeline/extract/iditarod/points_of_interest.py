"""Iditarod Historic Trail Alliance: points of interest, published, and not landed (decision 54, wave 4, read
live 2026-10-04): the public shelter cabins are in a visitor guide only a person can read.

The Iditarod NHT Visitor Guide (published by Alaska Geographic with BLM) describes the "Public Shelter Cabins"
on page 17, spaced "about twenty miles apart", with no coordinate in its text layer (the coverage audit's text
read, 2026-10-01). The Chugach NF rental cabins on Johnson Pass and Crow Pass are recreation.gov's, a source of
its own. A winter trail's shelter cabins are what a hiker's safety turns on there, and placing them needs a
reviewed source with fixes; whether BLM's Iditarod layers, which wave 1 registered, hold the cabins is unchecked.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "robots.txt (`User-agent: *` disallows /ajax/ and /apps/ only, no Crawl-delay for our agent), then one HEAD "
        "of the guide, 2026-10-04 under lib/user_agent.py's agent: 200 application/pdf, 11,786,538 bytes, ETag "
        '"db04f23239b5093d965ad41b5cc8d44d", Last-Modified 2024-04-05. Not downloaded again.',
        "the coverage audit (2026-10-01, batch c11_nht): 'Public Shelter Cabins' on p.17, 'about twenty miles "
        "apart'; no coordinates, from a text read.",
    ),
    where=("https://www.iditarod100.org/uploads/5/2/4/5/52459009/iditarodnhtvisitorguide.pdf", "https://recreation.gov"),
    reason="a PDF only a person can read: the shelter cabins are described with no coordinate",
)
