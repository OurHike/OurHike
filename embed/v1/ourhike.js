/**
 * The four embeds, as one file an organization pastes a script tag for.
 *
 * WHAT AN ORGANIZATION IS PROMISED ON THE CONSOLE'S OWN SCREEN, and what each
 * promise costs here:
 *
 * **NO COOKIES AND NO TRACKING.** Nothing below touches `document.cookie`,
 * `localStorage`, `sessionStorage` or IndexedDB, and there is no beacon, no
 * pixel and no analytics call. A widget that quietly set a cookie would put
 * an organization's own site inside somebody else's consent banner, which is
 * a cost they did not agree to and would not find out about.
 *
 * **NO OURHIKE BRANDING THEY CANNOT REMOVE.** The one mark is the attribution
 * line, and `data-credit="off"` takes it away. It is on by default because
 * "drawn by OurHike" is how a visitor works out who to tell when a mile is
 * wrong, not because it is ours to insist on.
 *
 * **IT INHERITS THEIR FONTS AND COLOURS.** Every rule this file writes is
 * `font: inherit` / `color: inherit` or a `currentColor` derivative. There is
 * no palette here, no web font, and no `!important`. An embed that imposed a
 * typeface would look like an advert on somebody's own page.
 *
 * **IF OUR SERVERS ARE DOWN THEIR PAGE STILL RENDERS.** Every fetch failure
 * removes the widget's contents and stops. No error text, no retry storm, no
 * exception escaping into their page's console. The host element is left
 * empty, which is indistinguishable from an org that has not pasted it yet -
 * and that is the right failure, because the alternative is our outage
 * printing itself on their homepage.
 *
 * **THE FOURTH ONE IS DIFFERENT AND SAYS SO.** Three are public and need no
 * account. The console embed is private: the organization's own server calls
 * `POST /console/session` with its key and the signed-in person's email, and
 * hands this file the short-lived token that comes back. The secret never
 * reaches a browser - if it did, anybody reading the page source could mint
 * tokens for anybody. This file refuses a secret in an attribute for exactly
 * that reason, rather than trusting nobody will try.
 *
 * NO BUILD STEP, ON PURPOSE. This is served byte-for-byte from `public/`, so
 * what an organization audits is what runs. It is ES2019, no imports, no
 * polyfills and no dependencies; anything that needed bundling would need a
 * source map to audit and would then be a different file from the one that
 * runs.
 */

(function () {
  'use strict'

  /** Where the backend is.
   *
   *  `window.__OURHIKE_API__` is the seam a deployment sets, the same one
   *  `src/scripts/claimOrgForm.js` reads. With nothing set the embeds do not
   *  draw - an unconfigured page renders empty rather than pointing at a
   *  guessed host.
   */
  function apiBase() {
    var base = window.__OURHIKE_API__
    return typeof base === 'string' && base ? base.replace(/\/$/, '') : null
  }

  /** A GET that resolves to null on every failure.
   *
   *  Every failure, deliberately: a 404, a 500, a CORS refusal, an offline
   *  laptop and a malformed body all answer the same null, and the caller
   *  draws nothing. Distinguishing them would only give the host page
   *  something to print.
   */
  function read(path, done) {
    var base = apiBase()
    if (base === null) {
      done(null)
      return
    }
    var request = new XMLHttpRequest()
    request.open('GET', base + path, true)
    request.setRequestHeader('Accept', 'application/json')
    request.onreadystatechange = function () {
      if (request.readyState !== 4) return
      if (request.status < 200 || request.status >= 300) {
        done(null)
        return
      }
      try {
        done(JSON.parse(request.responseText))
      } catch (error) {
        done(null)
      }
    }
    request.onerror = function () {
      done(null)
    }
    try {
      request.send()
    } catch (error) {
      done(null)
    }
  }

  function el(tag, className, text) {
    var node = document.createElement(tag)
    if (className) node.className = className
    if (text !== undefined && text !== null) node.textContent = String(text)
    return node
  }

  /** Empty a host element without touching anything around it. */
  /** The schemes a URL we were handed may carry, and nothing else.
   *
   *  THIS FILE RUNS ON THE ORGANIZATION'S OWN PAGE. A `javascript:` or
   *  `data:` URL rendered here is stored XSS on their site, put there by
   *  us - which makes this the worst of the three sinks that read these
   *  fields, and the only one with no framework quietly rewriting
   *  `javascript:` first.
   *
   *  A HAND-KEPT THIRD COPY, and deliberately so. `client/src/lib/
   *  safeLink.ts` is the app's list and `backend/app/schemas/org.py`'s
   *  SAFE_CONTACT_SCHEMES is the server's. This file has no build step on
   *  purpose - what an organization audits is what runs - so it cannot
   *  import either, and `client/src/test/orgEmbeds.test.ts` is what stops
   *  the three drifting. An allowlist rather than a blocklist because the
   *  set of schemes a browser will act on is not a list this file could
   *  keep up with.
   */
  var SAFE_SCHEMES = ['http:', 'https:', 'mailto:', 'tel:']

  /** `url` if a browser may be pointed at it, else null.
   *
   *  Resolved through the URL parser rather than matched as text, because
   *  what matters is the scheme the BROWSER lands on: leading whitespace,
   *  `JaVaScRiPt:` and an embedded newline are all things a regular
   *  expression reads differently from an anchor. A caller that gets null
   *  renders no link at all - absent is the honest answer, and a link the
   *  visitor's phone would act on is worse than none.
   */
  function safeHref(url) {
    if (!url) return null
    var parsed
    try {
      parsed = new URL(String(url), window.location.href)
    } catch (err) {
      return null
    }
    for (var i = 0; i < SAFE_SCHEMES.length; i += 1) {
      if (parsed.protocol === SAFE_SCHEMES[i]) return String(url)
    }
    return null
  }

  function clear(host) {
    while (host.firstChild) host.removeChild(host.firstChild)
  }

  /**
   * The one stylesheet, inserted once.
   *
   * Everything inherits. There is no colour value in here that is not derived
   * from `currentColor`, and no font at all - so a widget on a dark site is
   * dark, and on a serif site is serif, without the organization configuring
   * anything.
   */
  var STYLE_ID = 'ourhike-embed-style'
  var CSS = [
    '.ourhike{font:inherit;color:inherit;line-height:1.45}',
    '.ourhike *{box-sizing:border-box}',
    '.ourhike table{width:100%;border-collapse:collapse;font:inherit;color:inherit}',
    '.ourhike th,.ourhike td{text-align:left;padding:8px 10px;border-bottom:1px solid currentColor;' +
      'border-bottom-color:rgba(128,128,128,.28);vertical-align:top}',
    '.ourhike th{font-weight:600;font-size:.82em;letter-spacing:.04em;text-transform:uppercase;opacity:.7}',
    '.ourhike__filters{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px;align-items:flex-end}',
    '.ourhike__field{display:flex;flex-direction:column;gap:4px}',
    '.ourhike__label{font-size:.78em;letter-spacing:.04em;text-transform:uppercase;opacity:.7}',
    '.ourhike select,.ourhike button{font:inherit;color:inherit;background:transparent;' +
      'border:1px solid rgba(128,128,128,.4);border-radius:6px;padding:6px 10px;cursor:pointer}',
    '.ourhike button[disabled]{opacity:.45;cursor:default}',
    '.ourhike__name{font-weight:600}',
    '.ourhike__meta{font-size:.85em;opacity:.72}',
    // No colour value of ours: the whole embed inherits the host page's,
    // which is one of the four promises the console makes about this file.
    '.ourhike__spots{font-size:.85em;font-weight:600;margin-top:2px}',
    '.ourhike__foot{display:flex;flex-wrap:wrap;gap:10px;align-items:center;' +
      'justify-content:space-between;margin-top:12px;font-size:.85em;opacity:.75}',
    '.ourhike__card{border:1px solid rgba(128,128,128,.28);border-radius:8px;padding:12px;margin-bottom:10px}',
    '.ourhike__badge{border:1px solid rgba(128,128,128,.28);border-radius:8px;padding:14px}',
    '.ourhike__count{font-size:2em;font-weight:700;line-height:1.1}',
    '.ourhike__links{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px}',
    '.ourhike__empty{opacity:.75;font-size:.92em}',
    // The coverage badge's two shapes. No colour value in either, the same
    // promise the rest of this file keeps: everything inherits the host page.
    '.ourhike__strip{display:flex;flex-wrap:wrap;gap:22px;align-items:baseline;' +
      'border:1px solid rgba(128,128,128,.28);border-radius:8px;padding:12px 14px}',
    '.ourhike__figure{display:flex;flex-direction:column;gap:2px}',
    '.ourhike__value{font-size:1.6em;font-weight:700;line-height:1.1}',
    '.ourhike__label{font-size:.82em;opacity:.72}',
    '.ourhike__rows{display:flex;flex-direction:column;gap:8px;margin-top:10px}',
    '.ourhike__row{display:flex;justify-content:space-between;gap:16px;align-items:baseline}',
  ].join('')

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return
    var style = document.createElement('style')
    style.id = STYLE_ID
    style.appendChild(document.createTextNode(CSS))
    document.head.appendChild(style)
  }

  /**
   * The attribution line, and the switch that removes it.
   *
   * On by default, because a visitor reading a hike list needs to know who
   * publishes it and who drew it - that is the route by which a wrong mile
   * gets reported at all. `data-credit="off"` takes it away, because the
   * console promises branding they can remove and a promise with an
   * exception is not one.
   */
  function credit(host, orgName) {
    if (host.getAttribute('data-credit') === 'off') return null
    var line = el('div', 'ourhike__meta')
    line.appendChild(document.createTextNode('Published by ' + (orgName || 'this organization')))
    line.appendChild(document.createTextNode(' · drawn by OurHike'))
    return line
  }

  /** The org's own membership and donation links, never ours.
   *
   *  The design's line is that the embeds "carry your own membership and
   *  donation links, not ours", so these come off the org record and are
   *  omitted entirely when it carries none. No money passes through OurHike
   *  and there is nothing of ours to link to here.
   */
  function givingLinks(org) {
    if (!org) return null
    var wrap = el('div', 'ourhike__links')
    var any = false
    var joinAt = safeHref(org.membership_url)
    if (joinAt) {
      var join = el('a', null, 'Join ' + (org.name || 'us'))
      join.href = joinAt
      join.rel = 'noopener'
      wrap.appendChild(join)
      any = true
    }
    var giveAt = safeHref(org.donation_url)
    if (giveAt) {
      var give = el('a', null, 'Support this work')
      give.href = giveAt
      give.rel = 'noopener'
      wrap.appendChild(give)
      any = true
    }
    return any ? wrap : null
  }

  function number(value, digits) {
    return typeof value === 'number' ? value.toFixed(digits === undefined ? 1 : digits) : '—'
  }

  /* ------------------------------------------------------------------ *
   * 1 · Find a hike
   * ------------------------------------------------------------------ */

  var LENGTH_BANDS = [
    { label: 'Any length', test: function () { return true } },
    { label: 'Under 3 miles', test: function (m) { return m !== null && m < 3 } },
    { label: '3 to 6 miles', test: function (m) { return m !== null && m >= 3 && m <= 6 } },
    { label: 'Over 6 miles', test: function (m) { return m !== null && m > 6 } },
  ]

  /**
   * The featured hikes, filterable, read from the registry they signed off.
   *
   * **Filtering is client-side over one fetch on purpose.** The whole list is
   * a page of an organization's own hikes, not a search index, and a filter
   * that made a request per keystroke would put our latency inside their
   * page. It also means the filters keep working when the connection dies
   * after the first read.
   */
  function mountHikes(host) {
    var slug = host.getAttribute('data-org')
    if (!slug) return
    var rows = parseInt(host.getAttribute('data-rows') || '25', 10)
    if (!(rows > 0)) rows = 25
    var wanted = (host.getAttribute('data-filters') || 'region,difficulty,length')
      .split(',')
      .map(function (name) { return name.trim() })

    read('/clubs/' + encodeURIComponent(slug), function (org) {
      read('/clubs/' + encodeURIComponent(slug) + '/registry', function (parks) {
        if (parks === null) {
          clear(host)
          return
        }
        var hikes = []
        for (var p = 0; p < parks.length; p += 1) {
          for (var t = 0; t < parks[p].trails.length; t += 1) {
            var trail = parks[p].trails[t]
            for (var s = 0; s < trail.sections.length; s += 1) {
              var section = trail.sections[s]
              hikes.push({
                name: section.name,
                park: parks[p].name,
                region: section.region || '',
                miles: typeof section.miles === 'number' ? section.miles : null,
              })
            }
          }
        }

        var state = { region: '', length: 0, page: 0 }

        function matching() {
          return hikes.filter(function (hike) {
            if (state.region && hike.region !== state.region) return false
            return LENGTH_BANDS[state.length].test(hike.miles)
          })
        }

        function draw() {
          ensureStyle()
          clear(host)
          host.className = host.className ? host.className + ' ourhike' : 'ourhike'

          var filters = el('div', 'ourhike__filters')
          if (wanted.indexOf('region') !== -1) {
            var regions = []
            for (var i = 0; i < hikes.length; i += 1) {
              if (hikes[i].region && regions.indexOf(hikes[i].region) === -1) {
                regions.push(hikes[i].region)
              }
            }
            if (regions.length > 0) {
              var regionField = el('label', 'ourhike__field')
              regionField.appendChild(el('span', 'ourhike__label', 'Region'))
              var regionSelect = el('select')
              regionSelect.appendChild(new Option('All regions', ''))
              for (var r = 0; r < regions.length; r += 1) {
                regionSelect.appendChild(new Option(regions[r], regions[r]))
              }
              regionSelect.value = state.region
              regionSelect.onchange = function () {
                state.region = regionSelect.value
                state.page = 0
                draw()
              }
              regionField.appendChild(regionSelect)
              filters.appendChild(regionField)
            }
          }
          if (wanted.indexOf('length') !== -1) {
            var lengthField = el('label', 'ourhike__field')
            lengthField.appendChild(el('span', 'ourhike__label', 'Length'))
            var lengthSelect = el('select')
            for (var b = 0; b < LENGTH_BANDS.length; b += 1) {
              lengthSelect.appendChild(new Option(LENGTH_BANDS[b].label, String(b)))
            }
            lengthSelect.value = String(state.length)
            lengthSelect.onchange = function () {
              state.length = parseInt(lengthSelect.value, 10)
              state.page = 0
              draw()
            }
            lengthField.appendChild(lengthSelect)
            filters.appendChild(lengthField)
          }
          if (filters.childNodes.length > 0) {
            var clearButton = el('button', null, 'Clear')
            clearButton.type = 'button'
            clearButton.onclick = function () {
              state.region = ''
              state.length = 0
              state.page = 0
              draw()
            }
            filters.appendChild(clearButton)
            host.appendChild(filters)
          }

          var found = matching()
          if (found.length === 0) {
            host.appendChild(
              el(
                'p',
                'ourhike__empty',
                'Nothing matches those filters. That is the whole answer rather than a widened search.',
              ),
            )
          } else {
            var pages = Math.ceil(found.length / rows)
            if (state.page >= pages) state.page = 0
            var from = state.page * rows
            var slice = found.slice(from, from + rows)

            var table = el('table')
            var head = el('tr')
            head.appendChild(el('th', null, 'Hike'))
            head.appendChild(el('th', null, 'Park'))
            head.appendChild(el('th', null, 'Length'))
            var thead = el('thead')
            thead.appendChild(head)
            table.appendChild(thead)

            var body = el('tbody')
            for (var k = 0; k < slice.length; k += 1) {
              var row = el('tr')
              var nameCell = el('td')
              nameCell.appendChild(el('span', 'ourhike__name', slice[k].name))
              if (slice[k].region) {
                nameCell.appendChild(el('div', 'ourhike__meta', slice[k].region))
              }
              row.appendChild(nameCell)
              row.appendChild(el('td', null, slice[k].park))
              row.appendChild(
                el('td', null, slice[k].miles === null ? 'not measured' : number(slice[k].miles) + ' mi'),
              )
              body.appendChild(row)
            }
            table.appendChild(body)
            host.appendChild(table)

            var foot = el('div', 'ourhike__foot')
            foot.appendChild(
              el(
                'span',
                null,
                'Showing ' +
                  (from + 1) +
                  '–' +
                  Math.min(from + rows, found.length) +
                  ' of ' +
                  found.length,
              ),
            )
            if (pages > 1) {
              var nav = el('span')
              var back = el('button', null, '‹ Back')
              back.type = 'button'
              back.disabled = state.page === 0
              back.onclick = function () {
                state.page -= 1
                draw()
              }
              var next = el('button', null, 'Next ›')
              next.type = 'button'
              next.disabled = state.page >= pages - 1
              next.onclick = function () {
                state.page += 1
                draw()
              }
              nav.appendChild(back)
              nav.appendChild(document.createTextNode(' Page ' + (state.page + 1) + ' of ' + pages + ' '))
              nav.appendChild(next)
              foot.appendChild(nav)
            }
            host.appendChild(foot)
          }

          var links = givingLinks(org)
          if (links) host.appendChild(links)
          var line = credit(host, org && org.name)
          if (line) host.appendChild(line)
        }

        draw()
      })
    })
  }

  /* ------------------------------------------------------------------ *
   * 2 · Workdays
   * ------------------------------------------------------------------ */

  /**
   * Upcoming work, with each signup going where it actually goes.
   *
   * **A mirrored workday links to the organization's own form and says so.**
   * One button that quietly did two different things is how somebody ends up
   * believing they are on a roster they never reached - the same argument
   * `WorkdaysWidget` makes in the app, applied on somebody else's page where
   * we have even less chance to correct it afterwards.
   */
  function mountWorkdays(host) {
    var slug = host.getAttribute('data-org')
    if (!slug) return
    var days = parseInt(host.getAttribute('data-window') || '60', 10)
    if (!(days > 0)) days = 60

    read('/clubs/' + encodeURIComponent(slug), function (org) {
      read(
        '/workdays?org=' + encodeURIComponent(slug) + '&days=' + days,
        function (workdays) {
          if (workdays === null) {
            clear(host)
            return
          }
          ensureStyle()
          clear(host)
          host.className = host.className ? host.className + ' ourhike' : 'ourhike'

          if (workdays.length === 0) {
            host.appendChild(
              el(
                'p',
                'ourhike__empty',
                'No workdays on the calendar in the next ' + days + ' days.',
              ),
            )
          }

          for (var i = 0; i < workdays.length; i += 1) {
            var workday = workdays[i]
            var card = el('div', 'ourhike__card')
            card.appendChild(el('div', 'ourhike__name', workday.title))
            var meta = workday.starts_on
            if (workday.ends_on && workday.ends_on !== workday.starts_on) {
              meta += ' – ' + workday.ends_on
            }
            if (workday.meet_point) meta += ' · ' + workday.meet_point
            card.appendChild(el('div', 'ourhike__meta', meta))
            // HOW FULL IT IS, and only when the organization said. The
            // design's Workdays Widget draws a `spots` field on every card;
            // without it a visitor cannot tell a workday with places left
            // from one with none until they have followed the link.
            //
            // A workday with no `cap` published has no ceiling we know of, so
            // nothing is drawn - absent means unknown here as everywhere
            // else, and "0 of 0" would be a number nobody stands behind.
            //
            // CONFIRMED, never interested. A signup is an introduction and
            // not an enrolment: counting the people who said "maybe" would
            // tell a visitor a workday is full when nobody is on the crew.
            if (typeof workday.cap === 'number' && workday.cap > 0) {
              var taken = typeof workday.confirmed_count === 'number' ? workday.confirmed_count : 0
              card.appendChild(
                el(
                  'div',
                  'ourhike__spots',
                  taken >= workday.cap
                    ? 'Full \u2014 ' + workday.cap + ' confirmed'
                    : taken + ' of ' + workday.cap + ' places confirmed',
                ),
              )
            }
            if (workday.description) {
              card.appendChild(el('p', null, workday.description))
            }

            if (workday.status === 'cancelled') {
              card.appendChild(el('div', 'ourhike__meta', 'Called off. Nothing to sign up to.'))
            } else {
              var mirrored = workday.source === 'mirrored' || workday.signup_mode === 'contact'
              var where = safeHref(workday.signup_url)
              if (mirrored && where) {
                var out = el('a', null, 'Sign up on our site')
                out.href = where
                out.rel = 'noopener'
                card.appendChild(out)
              } else if (mirrored && workday.signup_contact) {
                card.appendChild(
                  el('div', 'ourhike__meta', 'To join, contact ' + workday.signup_contact),
                )
              } else {
                card.appendChild(
                  el(
                    'div',
                    'ourhike__meta',
                    'Signups for this one are handled in the OurHike app.',
                  ),
                )
              }
            }
            host.appendChild(card)
          }

          var line = credit(host, org && org.name)
          if (line) host.appendChild(line)
        },
      )
    })
  }

  /* ------------------------------------------------------------------ *
   * 3 · Coverage badge
   * ------------------------------------------------------------------ */

  /**
   * The three numbers an organization puts on its own website.
   *
   * **ONE SNIPPET, TWO SHAPES** - the design's own words. `data-shape="card"`
   * is the sidebar card a donate page carries; anything else is the footer
   * strip. Both draw the same three figures, because they are the same claim
   * in two places and a reader who saw different numbers on the same site
   * would be right to trust neither.
   *
   * **IT USED TO READ `/coverage` AND COULD NEVER HAVE WORKED.** That endpoint
   * depends on `org_access`, which depends on a signed-in caller, so an
   * anonymous visitor got a 401 and this drew nothing - on every real site,
   * always. It only ever appeared to work on `/for-orgs/demo/`, where a
   * fixture serves it with no auth. The coverage report is right to be gated:
   * a public list of which miles nobody is looking after is a list of miles to
   * avoid. Pointing a public embed at it was the mistake, and
   * `GET /clubs/{slug}/scoreboard` is the public shape.
   *
   * **THREE COUNTS, AND THE SHAPE IS THE ENFORCEMENT.** The old badge read
   * `coverage.gaps.length` and discarded the names beside it, which put a
   * safety property in a browser where the next edit could drop it. The
   * scoreboard has no array in it to discard.
   *
   * **THE FOOT SAYS WHAT THE NUMBERS ARE, not what the design's mock-up said.**
   * That card reads "Updated nightly from our own registry"; this is computed
   * when the badge loads, so it says so. A line claiming a freshness the
   * mechanism does not have is the same defect as a heading claiming a reading
   * nobody did.
   */
  function mountCoverage(host) {
    var slug = host.getAttribute('data-org')
    if (!slug) return

    read('/clubs/' + encodeURIComponent(slug), function (org) {
      read('/clubs/' + encodeURIComponent(slug) + '/scoreboard', function (board) {
        if (board === null) {
          clear(host)
          return
        }
        ensureStyle()
        clear(host)
        host.className = host.className ? host.className + ' ourhike' : 'ourhike'

        var figures = [
          [format(board.miles_maintained), 'miles maintained'],
          [String(board.active_volunteers), 'active volunteers'],
          [format(board.hours_this_season), 'hours this season'],
        ]
        var card = host.getAttribute('data-shape') === 'card'
        host.appendChild(card ? sidebarCard(host, org, figures) : footerStrip(figures))

        var line = credit(host, org && org.name)
        if (line) host.appendChild(line)
      })
    })
  }

  /** A number a person reads: 13.8 stays 13.8, 164.0 becomes 164. */
  function format(value) {
    var number = typeof value === 'number' ? value : 0
    return number % 1 === 0 ? String(number) : number.toFixed(1)
  }

  function footerStrip(figures) {
    var strip = el('div', 'ourhike__strip')
    for (var i = 0; i < figures.length; i++) {
      var figure = el('div', 'ourhike__figure')
      figure.appendChild(el('div', 'ourhike__value', figures[i][0]))
      figure.appendChild(el('div', 'ourhike__label', figures[i][1]))
      strip.appendChild(figure)
    }
    return strip
  }

  function sidebarCard(host, org, figures) {
    var card = el('div', 'ourhike__badge')
    // THE HEADING IS THEIRS. The design's mock-up says "Our park, live", which
    // is an organization's own words about its own page and not something we
    // can know - so `data-title` is how they say it, and their name is the
    // fallback rather than a phrase we made up for them.
    card.appendChild(
      el('div', 'ourhike__name', host.getAttribute('data-title') || (org && org.name) || ''),
    )
    var rows = el('div', 'ourhike__rows')
    for (var i = 0; i < figures.length; i++) {
      var row = el('div', 'ourhike__row')
      row.appendChild(el('span', 'ourhike__label', figures[i][1]))
      row.appendChild(el('span', 'ourhike__value', figures[i][0]))
      rows.appendChild(row)
    }
    card.appendChild(rows)
    card.appendChild(
      el('div', 'ourhike__meta', 'Counted from their own registry when this page loaded.'),
    )
    return card
  }

  /* ------------------------------------------------------------------ *
   * 4 · The private console
   * ------------------------------------------------------------------ */

  /**
   * The management console, inside an organization's own members area.
   *
   * **THE SECRET NEVER REACHES A BROWSER, AND THIS FILE ENFORCES THAT.** A
   * `data-secret` attribute is refused outright rather than used, because a
   * secret in page source is a secret anybody reading the page can mint
   * tokens with - and the refusal has to be louder than the mistake, which
   * is the one case in this file that writes an error where somebody can see
   * it. The organization's own server calls `POST /console/session` and puts
   * the token it gets back into `data-token`.
   *
   * **A PERSON WITH NO PERMISSIONS GETS AN EMPTY CONSOLE, NOT AN ERROR.**
   * `ConsoleSessionOut` returns a no-permission token for somebody not on the
   * roster, deliberately, so an organization's members area shows a page with
   * nothing on it rather than a stack trace. This draws that page.
   *
   * **THE TOKEN IS SHORT-LIVED AND THIS DOES NOT REFRESH IT.** Fifteen
   * minutes, and when it lapses the console says so and asks the person to
   * reload - a silent refresh would need the secret, which is the thing that
   * must not be here.
   */
  function mountConsole(host) {
    ensureStyle()
    host.className = host.className ? host.className + ' ourhike' : 'ourhike'

    if (host.getAttribute('data-secret')) {
      clear(host)
      var refusal = el('div', 'ourhike__card')
      refusal.appendChild(el('div', 'ourhike__name', 'This console will not start'))
      refusal.appendChild(
        el(
          'p',
          null,
          'A console key secret was put in the page. Anybody who can read this page could mint ' +
            'sessions with it, so it has been ignored rather than used. Revoke that key, then have ' +
            'your server call POST /console/session and pass the token it returns as data-token.',
        ),
      )
      host.appendChild(refusal)
      return
    }

    var token = host.getAttribute('data-token')
    if (!token) {
      clear(host)
      host.appendChild(
        el(
          'p',
          'ourhike__empty',
          'Nobody is signed in here yet. Your server mints a token for whoever is, and passes it ' +
            'as data-token.',
        ),
      )
      return
    }

    var base = apiBase()
    if (base === null) {
      clear(host)
      return
    }
    var request = new XMLHttpRequest()
    request.open('GET', base + '/console/whoami', true)
    request.setRequestHeader('Accept', 'application/json')
    request.setRequestHeader('Authorization', 'Bearer ' + token)
    request.onreadystatechange = function () {
      if (request.readyState !== 4) return
      clear(host)
      if (request.status === 401 || request.status === 403) {
        host.appendChild(
          el(
            'p',
            'ourhike__empty',
            'This console session has expired. Reload the page and your site will start a new one.',
          ),
        )
        return
      }
      if (request.status < 200 || request.status >= 300) return
      var session
      try {
        session = JSON.parse(request.responseText)
      } catch (error) {
        return
      }

      var card = el('div', 'ourhike__card')
      card.appendChild(
        el('div', 'ourhike__name', session.display_name || 'Signed in'),
      )
      var permissions = session.permissions || []
      if (permissions.length === 0) {
        card.appendChild(
          el(
            'p',
            null,
            'You are signed in, and you do not hold a role with this organization — so there is ' +
              'nothing here for you to manage. That is not an error.',
          ),
        )
      } else {
        card.appendChild(
          el('p', null, 'You can manage: ' + permissions.join(', ') + '.'),
        )
        var open = el('a', null, 'Open the full console')
        open.href = '/org/' + encodeURIComponent(session.org_slug) + '/setup'
        open.rel = 'noopener'
        card.appendChild(open)
      }
      host.appendChild(card)
    }
    request.onerror = function () {
      clear(host)
    }
    try {
      request.send()
    } catch (error) {
      clear(host)
    }
  }

  /* ------------------------------------------------------------------ *
   * Mounting
   * ------------------------------------------------------------------ */

  var WIDGETS = [
    { id: 'ourhike-hikes', mount: mountHikes },
    { id: 'ourhike-workdays', mount: mountWorkdays },
    { id: 'ourhike-coverage', mount: mountCoverage },
    // A SECOND ID FOR THE SAME WIDGET, so one page can show both shapes at
    // once. An organization pastes ONE of these and picks its shape with
    // `data-shape` - the design's "one snippet, two shapes". The only page
    // that wants both side by side is /for-orgs/demo/, which exists to show
    // what the snippet can do, and mounting by id is what this file does.
    { id: 'ourhike-coverage-card', mount: mountCoverage },
    { id: 'ourhike-console', mount: mountConsole },
  ]

  /**
   * Mount whatever is on the page, and never throw into it.
   *
   * Each widget is wrapped on its own: one failing leaves the other three
   * drawn, and nothing this file does surfaces in the host page's console as
   * an unhandled error. A script tag that throws is a script tag a web
   * developer removes.
   */
  function mountAll() {
    for (var i = 0; i < WIDGETS.length; i += 1) {
      var host = document.getElementById(WIDGETS[i].id)
      if (!host) continue
      if (host.getAttribute('data-ourhike-mounted') === 'true') continue
      host.setAttribute('data-ourhike-mounted', 'true')
      try {
        WIDGETS[i].mount(host)
      } catch (error) {
        /* An embed that takes somebody's page down with it is worse than an
           embed that does not appear. */
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountAll)
  } else {
    mountAll()
  }
})()
