"""Roanoke Appalachian Trail Club: closures, 2 notice sources read here: decision 53's drafted rows, registered
2026-10-10 (section K's hand-back) once www.ratc.org's robots.txt answered 200; it answered 502 on 2026-10-03 and
2026-10-04, which RFC 9309 reads as a full disallow.

- `ratc_closures_posts`: the club's Closures category (WordPress category 78), one row a post (WordpressPosts).
  Dormant: 3 posts, 2022-01-11 to 2023-10-25.
- `ratc_news_posts`: RATC News (category 13), one row a post (WordpressPosts): 25 posts back to 2015, where closure
  posts have gone untagged since (the Catawba Mountain Fire Road's closure, reopening and 2025 work), beside the
  club's news. Which posts are notices is decision 7's classifier and a person's review in dbt, never a filter here.
  Post 9351 sits in both categories, so it lands in both tables.

Both rows list `content` and `excerpt` as person_fields (decision 59): the posts' bodies carried e-mail addresses and
telephone numbers on 2026-10-10, so no body reaches the raw store, and a notice publishes its title, dates, category
and link (decisions 55 and 107). Both are held from hikers, as every WordPress category that keeps every post it ever
filed: nothing expires a post yet (their rows' reaches_hikers_comment).

Not read, as decision 53's inventory drafted neither: the Andy Layne Trail page (/andy-layne-trail/, the trail's
2026 reroute, which ATC's own update carries as 'Virginia: Andy Layne Trail Relocation'), and the club's Facebook
page, which its McAfee Knob page names for 'the latest news and alerts', a social channel with no reader here.

Each source's row in sources.json holds its terms verbatim, its live read of 2026-10-10 and its measured key.
The readers are extract/_kinds.py's WordpressPosts and extract/_notices.py's PageNotice. A page is read every run, one
request, and is FRESH only when what would land hashes as the last committed load did; so is a category, its posts
read whole each run beside its count. No prose and no person lands (decisions 55 and 59).
"""

from extract._kinds import wordpress_posts

CLAIMS = ("ratc_closures_posts", "ratc_news_posts")
RESOURCES = [wordpress_posts("ratc_closures_posts"), wordpress_posts("ratc_news_posts")]
