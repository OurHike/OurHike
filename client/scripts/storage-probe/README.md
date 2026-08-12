# Storage probe — the real download, in a real browser

The unit suite mocks `idb-keyval`, so between it and a full phone there is
nothing: no real IndexedDB, no quota pressure, for the app's headline feature.
[TESTING.md](../../../TESTING.md) names that gap. This is the first thing that
looks into it, and it found [#544](https://github.com/OurHike/OurHike/issues/544)
there.

It drives the **real** `lib/archiveDownload.ts` — same fetch loop, same Blob
accumulation, same hash verification, same `set()` — against a local server that
streams an arbitrary number of deterministic, incompressible bytes with `ETag`,
`Range` and `latest.json` support. Nothing is re-implemented; the point is to
measure the code a hiker runs.

**Manual on purpose, not part of CI.** It moves gigabytes, and its numbers
depend on the machine's free disk, which is not something to assert against in a
gate. Same category as the full USGS fetch in TESTING.md.

## Running it

```
cd client
node scripts/storage-probe/run.mjs                     # the three published tiers
node scripts/storage-probe/run.mjs --size 1184700000   # one size, in bytes
node scripts/storage-probe/run.mjs --unlimited         # quota taken out of the way
node scripts/storage-probe/run.mjs --store-only        # no network, the store alone
node scripts/storage-probe/run.mjs --watch             # what is on disk mid-transfer
node scripts/storage-probe/run.mjs --reclaim           # when a delete gives the space back
```

`CHROMIUM_EXECUTABLE_PATH` overrides the browser, for an environment that has
one preinstalled and cannot download — the same escape hatch
`check-deployed-app.mjs` uses.

Each line of output is JSON. `elapsedMs` beside `error` is the number that
matters: a failure that took as long as the transfer is a failure that spent the
hiker's data allowance to discover something the browser knew in advance.

## What it measured — 2026-08-12, Chromium 1194, quota ~1.0 GB, 29 GB free disk

Before #544's fix, the Fine tier:

```
{"bytes":1184700000,"elapsedMs":45280,"storedBytes":null,"partial":null,
 "error":"QuotaExceededError: ","chunks":573,
 "firstQuarterMBps":27.7,"lastQuarterMBps":25.7}
```

All 1,184,700,000 bytes transferred over 45 seconds, then nothing stored,
nothing kept, and an error whose message is the empty string. After the fix, the
same file on the same browser:

```
{"bytes":1184700000,"elapsedMs":30,"storedBytes":null,"partial":null,
 "error":"ArchiveTooLargeError: There is not enough room on this phone for this
 map. It needs about 1.18 GB and about 1.09 GB is free for the app. Nothing was
 downloaded, so none of your data was spent...","chunks":0}
```

Four things this ruled OUT as causes, each a plausible suspect beforehand:

| Suspect                                                    | Measurement                                                                           |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Streaming SHA-256 wrong past 2³² bits                      | 1.18 GB verifies against its published digest with `--unlimited`                      |
| `new Blob([accumulated, chunk])` per chunk being quadratic | 27.7 MB/s over the first quarter, 25.7 MB/s over the last, 573 chunks                 |
| A per-record IndexedDB ceiling                             | 1.18 GB stores in one record with `--unlimited`; 734 MB stores inside a 1.05 GB quota |
| `content-length` absent, service worker interfering        | Neither is in the path                                                                |

Two findings this turned up, both visible from `--store-only` and `--watch`.
Both are now closed — the first by #553, the second by #554:

- ~~**Nothing is checkpointed during a transfer.**~~ **Fixed by #553.** Every
  record was `null` eight seconds into an eleven-second download, with `usage` at
  1,016 bytes: the bytes existed only in the renderer, so a tab the OS killed
  lost all of them — contradicting `useArchiveDownload.ts`'s claim that a
  download interrupted by the app closing resumes on the next launch.

  The bytes are now written as they arrive, in append-only segment records
  (`src/lib/archiveStore.ts`), and completion is a marker rather than a second
  copy of the archive. `--watch` shows this directly: `survey` reports the
  segments per generation (`…:g0` → `0:33554432 1:33554432 …`) alongside the
  records it always did, so what is on disk mid-transfer is observed rather than
  assumed. A killed transfer now costs at most the last unflushed segment, 32 MiB.

  Note for anyone re-running the ruled-out table above: the second row measured
  `new Blob([accumulated, chunk])`, which no longer exists. Nothing is
  accumulated in memory now, so per-chunk cost cannot grow with what is held.

- ~~**A delete does not return the quota promptly.**~~ **Measured and worked
  around by #554.** The original observation was that usage stayed at 524 MB
  through a `clear()`. `--reclaim` now answers the three questions #554 asked,
  storing 200 MiB as the seven segment records a real download leaves and
  deleting it through the app's own `deleteArchive`:

  |                           |                                                  |
  | ------------------------- | ------------------------------------------------ |
  | usage after storing       | 209,717,908                                      |
  | delete completed in       | 10 ms, and the archive is unreadable immediately |
  | usage 10 s later          | 209,718,780 — unmoved                            |
  | usage after a page reload | 209,718,780 — unmoved                            |

  So **the bytes are gone and the accounting is not**, and it is not a flush or a
  transaction boundary that settles on its own: a page load does not shift it
  either. That is what decides where the fix belongs. Nothing `deleteArchive` can
  do reclaims harder, because there is nothing left to reclaim — so
  `estimateAvailableBytes` credits back the part of a release the browser has not
  yet accounted for, and the room check stops refusing on a figure it can prove
  is stale. The same run now reports both numbers, and the gap between them is
  the fix: `browserSaysFree` 637,729,630 against `appSaysFree` 847,444,830, which
  is the deleted 209,715,200 exactly.

  The credit cannot double-count — it decays as `usage` falls and is zero once
  the browser catches up — and it expires after a day, so a note that outlived
  its truth costs a download that starts and runs out partway, keeping every byte
  that arrived (#553), rather than one that is refused outright.
