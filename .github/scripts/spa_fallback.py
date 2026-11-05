"""Write `_site/404.html`, the single-page apps' fallback on production GitHub Pages (#2014).

    python .github/scripts/spa_fallback.py _site

GitHub Pages answers a path with no file behind it with the root `404.html`,
and with its own "Page not found" when there is none. Until this file existed
there was none, so every deep link into an app - `/app/my/tread`,
`/app/org/<slug>/setup`, the addresses client/src/lib/orgRoute.ts exists to
read - answered 404 in production (measured 2026-09-17, written up in
features/ORG_ONBOARDING.md's Known gaps). Pages takes one `404.html` for the
whole site, so the file cannot simply BE the app shell, as the Cloudflare
previews' copy is: the survey (features/STRUCTURE_INVENTORY.md, conflict 6) is
a second shell at `/survey/`, and a mistyped address on the marketing site
should still say it is not there rather than boot the map.

So the page written here is a dispatcher. For a path under the base of a shell
this deploy holds, it fetches that shell - the same bytes `/app/` serves - and
replaces itself with it, keeping the address, so the app boots exactly as it
would have at its own root and reads the real path off `location`. Every
shell's built `index.html` names its scripts and styles by absolute path
(Vite's `base`), which is why the same document works one directory deeper.
For any other path, for a browser running no script, and when the shell cannot
be fetched, it is a plain not-found page.

The status stays 404: GitHub Pages sends it with the page, and nothing here
can change that. A browser renders the page all the same, and once the app's
service worker is installed it answers navigations under its scope itself, so
this page is only ever the first visit's.

A shell is named in SHELLS and included only when the deploy holds it, so the
survey's door opens in the deploy that first carries `survey/index.html`, with
no change here. The app's shell is required: without it this deploy has no app
to fall back to, and that is a broken assembly rather than a choice.

Exit 1 when `_site` holds no `app/index.html`, or already holds a `404.html`:
the site bringing a not-found page of its own is a decision about which one
production serves, to be made here rather than by whichever copy ran last.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: Each single-page app's base path under the site root, as its Vite `base` spells it.
SHELLS = ("/app/", "/survey/")
#: The one shell every production deploy must hold.
REQUIRED = "/app/"
NOT_FOUND = "404.html"


class Refused(Exception):
    """The assembly cannot be given a fallback as it stands; the message says why."""


def shells_in(site: Path) -> list[str]:
    """The bases in SHELLS whose `index.html` this assembled site holds, in SHELLS' order."""
    return [base for base in SHELLS if (site / base.strip("/") / "index.html").is_file()]


def page(shells: list[str]) -> str:
    """The 404.html: a shell for a path under its base, a not-found page for everything else."""
    bases = json.dumps(shells)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="robots" content="noindex" />
    <title>Page not found — OurHike</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <script>
      // Written by .github/scripts/spa_fallback.py; its docstring says why.
      (function () {{
        var bases = {bases};
        var path = location.pathname;
        var base = null;
        for (var i = 0; i < bases.length; i++) {{
          if (path.indexOf(bases[i]) === 0) {{
            base = bases[i];
            break;
          }}
        }}
        function notFound() {{
          var page = document.getElementById("not-found");
          if (page) page.hidden = false;
          else document.addEventListener("DOMContentLoaded", notFound);
        }}
        if (base === null) {{
          notFound();
          return;
        }}
        fetch(base, {{ cache: "no-cache", credentials: "same-origin" }})
          .then(function (response) {{
            if (!response.ok) throw new Error(response.status);
            return response.text();
          }})
          .then(function (shell) {{
            document.open();
            document.write(shell);
            document.close();
          }})
          .catch(notFound);
      }})();
    </script>
  </head>
  <body>
    <main id="not-found" hidden>
      <h1>Page not found</h1>
      <p>There is no page at this address.</p>
      <p><a href="/">OurHike</a> &middot; <a href="/app/">Open the map</a></p>
    </main>
    <noscript>
      <h1>Page not found</h1>
      <p>There is no page at this address, or it needs JavaScript to open.</p>
      <p><a href="/">OurHike</a> &middot; <a href="/app/">Open the map</a></p>
    </noscript>
  </body>
</html>
"""


def write(site: Path) -> list[str]:
    """Write `site/404.html` and return the shell bases it falls back to."""
    if (site / NOT_FOUND).exists():
        raise Refused(
            f"{site / NOT_FOUND} already exists, so something else in this assembly brings a not-found page. "
            "Decide which one production serves here rather than letting the last copy win."
        )
    shells = shells_in(site)
    if REQUIRED not in shells:
        raise Refused(f"{site}{REQUIRED}index.html is missing, so this deploy has no app for a deep link to fall back to.")
    (site / NOT_FOUND).write_text(page(shells), encoding="utf-8")
    return shells


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: spa_fallback.py <assembled site directory>", file=sys.stderr)
        return 2
    try:
        shells = write(Path(argv[0]))
    except Refused as refusal:
        print(f"::error::{refusal}")
        return 1
    print(f"{NOT_FOUND} falls back to the shell at {', '.join(shells)} and is a not-found page everywhere else.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
