// The download sizes a hiker is shown, read from what the bucket actually
// published rather than from a number somebody kept by hand (#505).
//
// downloadDetail.ts has carried the problem in its header for a while: its
// figures were copied from a build log, drifted from what was served, and the
// advertised Standard tier was 14.8 MB smaller than the object behind it - "in
// the direction that strands somebody who freed up exactly enough space". The
// fix it names is this one: publish.py measures every artifact it uploads, so
// the figure can come from `latest.json` and stop being hand-kept at all.
//
// WHAT IT READS, AND WHY NOT THE OTHER FIELD. `PublishedSnapshot.sizes` is
// publish.py's `transfer_bytes` - the bytes on the wire - and never
// `size_bytes`, which is the DECODED size. The two differ by about 3x for the
// gzipped text artifacts, and the number here is shown to somebody deciding
// whether to spend it on mobile data, so the decoded figure is not a cautious
// version of it but a wrong one. (For the .pmtiles archives the two coincide:
// publish.py's upload_args leaves BINARY_TYPES uncompressed, so what is stored
// is what is sent.)
//
// NEVER FATAL, AND NEVER EMPTY-MEANS-ZERO. An unreachable, malformed or older
// manifest yields no sizes, and every caller falls back to its own constant -
// the same discipline dataManifest.ts already applies to hashes ("a download
// that would have succeeded yesterday must not start failing because a metadata
// file moved"). This matters more than usual right now: the six .pmtiles
// entries in the live manifest carry only a hash, because they were published
// by build-basemap.yml and build-dem.yml before sizes were measured and
// publish.py's merge is additive - it lets "a remote entry from before sizes
// were published survive without one rather than gaining a guess". So today
// this hook improves the vector artifacts and changes nothing for the map
// archives, and the moment those workflows publish again it starts answering
// for them too, with no client change.
//
// A SIZE THAT ARRIVES LATE IS NOT A SIZE THAT WAS WRONG. The fetch resolves
// after first paint, so a screen reads its constant and then re-renders with
// the published figure. That is the honest ordering: the constant is the best
// answer available until the bucket has been asked.

import { useEffect, useState } from 'react'
import { DATA_CONFIGURED } from './config'
import { publishedSnapshot } from './dataManifest'
import { useOnline } from './useOnline'

/** Published transfer sizes by artifact key - `latest.json`'s spelling, which
 *  is also what `packageArtifactKey()` returns, so a caller looks a package up
 *  with the key the catalog already computes rather than a second mapping. */
export type PublishedSizes = Record<string, number>

/** Nothing has been read yet, or there was nothing to read. Every consumer
 *  treats this as "use your own constant", never as zero. */
export const NO_PUBLISHED_SIZES: PublishedSizes = {}

export function usePublishedSizes(): PublishedSizes {
  const [sizes, setSizes] = useState<PublishedSizes>(NO_PUBLISHED_SIZES)
  const online = useOnline()

  useEffect(() => {
    // A build with no bucket (a preview, a test) has nothing to ask and must
    // not spend a failed round trip finding that out on every mount.
    //
    // AND NEVER WITH NO SIGNAL, which is the same gate useTrailData.ts puts on
    // its own manifest read. A phone offline at a trailhead is the case this
    // whole app is built around: it must reach the network zero times, not
    // once-and-fail, and App.trailData.test.tsx pins exactly that. The size on
    // screen then is the catalog's constant, which is the right answer for a
    // phone that cannot ask. Coming back online re-runs this and the figure
    // refreshes itself.
    if (!DATA_CONFIGURED || !online) return

    const controller = new AbortController()
    let wanted = true

    void publishedSnapshot({ signal: controller.signal })
      .then((snapshot) => {
        if (wanted) setSizes(snapshot.sizes)
      })
      .catch(() => {
        // publishedSnapshot resolves rather than rejects on an unreadable
        // manifest, so this is the abort path. Either way the answer is the
        // one already held: no published sizes, so callers keep their
        // constants.
      })

    return () => {
      wanted = false
      controller.abort()
    }
  }, [online])

  return sizes
}
