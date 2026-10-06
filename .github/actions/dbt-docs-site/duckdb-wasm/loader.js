// The module dbt's /data/ page imports DuckDB-WASM from, served from our own
// site instead of jsDelivr (pipeline/ELT.md decision 93, SEC-1 of PR #1805's
// second review). stage.mjs bundles this file with @duckdb/duckdb-wasm and
// apache-arrow, at the versions package-lock.json pins, into
// /data/duckdb/duckdb.js.
//
// WHY A MODULE OF OUR OWN RATHER THAN A MIRROR OF jsDelivr's FILES. dbt
// 2.0.6's page builds every DuckDB URL from one base, `duckdb_cdn_base`
// (`--duckdb-cdn-base`), in jsDelivr's layout: it imports `${base}/+esm` and
// hands DuckDB `${base}/dist/duckdb-{mvp,eh}.wasm` and
// `${base}/dist/duckdb-browser-{mvp,eh}.worker.js`. Copied as they are, two
// of those cannot be served from our hosts:
//
// - `+esm` has no file extension. GitHub Pages types a file by its
//   extension, and serves one without as application/octet-stream (measured
//   2026-10-06: ourhike.org/CNAME), and a browser refuses a module with that
//   type (measured the same day in Chromium, against `python -m http.server`,
//   which does the same: "Expected a JavaScript-or-Wasm module script but the
//   server responded with a MIME type of application/octet-stream").
// - The two WASM files are 34,242,586 and 39,362,651 bytes, and Cloudflare
//   Pages, which serves every pull request's preview, refuses any file over
//   25 MiB: wrangler 4.147.0's `pages deploy` throws on
//   `filestat.size > MAX_ASSET_SIZE`, 25 * 1024 * 1024 (its cli.js, read
//   2026-10-06).
//
// So build.sh passes the base `/data/duckdb/duckdb.js?`. The page's import of
// `${base}/+esm` becomes `/data/duckdb/duckdb.js?/+esm`, which a static host
// answers with this file, the query ignored (measured 2026-10-06:
// ourhike.org/CNAME?/+esm answered the same 12 bytes as /CNAME). Every other
// URL the page builds from the base arrives here, in selectBundle(), as
// `duckdb.js?/<path>`, and is answered with `<path>` beside this file, a WASM
// file put back together from the parts stage.mjs cut it into.
//
// AND THE EXTENSIONS. DuckDB fetches the extensions a query needs when it
// first needs one, and its default repository is extensions.duckdb.org:
// measured 2026-10-06, the page's first query asked that host 18 times for
// v1.4.3/wasm_eh/parquet.duckdb_extension.wasm. AsyncDuckDB below points the
// repository at `extensions/` beside this file before the page runs a single
// query, so an extension we do not ship fails to load rather than coming from
// another origin. DuckDB still checks the signature of the copy we serve:
// with one bit of it flipped, the same day, it refused to load it ("its
// signature is either missing or invalid").

import * as duckdb from '@duckdb/duckdb-wasm'

export * from '@duckdb/duckdb-wasm'

// { "dist/duckdb-eh.wasm": ["dist/duckdb-eh.part0.wasm", ...], ... }, written
// in by stage.mjs (esbuild's --define) from the parts it cut.
const PARTS = __OURHIKE_DUCKDB_PARTS__

const here = new URL(import.meta.url)

/** The path a URL the page built from its base names, beside this file. */
function pathFromBase(url) {
  const asked = new URL(url, here)
  if (asked.origin !== here.origin || asked.pathname !== here.pathname || !asked.search.startsWith('?/')) {
    throw new Error(`/data/duckdb/duckdb.js was asked for ${url}, which is not under the base the page was built with`)
  }
  return asked.search.slice(2)
}

/** A URL for the file at `path` beside this file: the file itself, or its parts put back together. */
async function fileUrl(path) {
  const parts = PARTS[path]
  if (parts === undefined) return new URL(path, here).href
  const blobs = await Promise.all(
    parts.map(async (part) => {
      const response = await fetch(new URL(part, here))
      if (!response.ok) throw new Error(`${response.status} ${response.statusText} fetching ${part}`)
      return response.blob()
    }),
  )
  // application/wasm because DuckDB's worker compiles it with
  // WebAssembly.instantiateStreaming, which refuses a response of any other
  // type.
  return URL.createObjectURL(new Blob(blobs, { type: 'application/wasm' }))
}

export async function selectBundle(bundles) {
  const chosen = await duckdb.selectBundle(bundles)
  return {
    ...chosen,
    mainModule: await fileUrl(pathFromBase(chosen.mainModule)),
    // Absolute: the page starts the worker from a blob: URL whose script
    // calls importScripts() with this, and a blob: URL is no base to resolve
    // a relative one against.
    mainWorker: new URL(pathFromBase(chosen.mainWorker), here).href,
    pthreadWorker: chosen.pthreadWorker ? new URL(pathFromBase(chosen.pthreadWorker), here).href : null,
  }
}

export class AsyncDuckDB extends duckdb.AsyncDuckDB {
  async instantiate(mainModule, pthreadWorker = null, progress = () => {}) {
    const result = await super.instantiate(mainModule, pthreadWorker, progress)
    // The parts' bytes, held by the blob: URL until the page closes otherwise.
    if (mainModule.startsWith('blob:')) URL.revokeObjectURL(mainModule)
    const repository = new URL('extensions', here).href
    const connection = await this.connect()
    try {
      // custom_extension_repository is the one this build reads when a query
      // loads an extension: measured 2026-10-06, with only
      // autoinstall_extension_repository set, the parquet extension came
      // from extensions.duckdb.org again. That one is set too, because
      // DuckDB's documentation names it for loading on demand and a later
      // build may read it. lock_configuration then refuses any later SET
      // (measured the same day: "the configuration has been locked"), so no
      // query the page runs can point either back at another origin.
      await connection.query(`SET custom_extension_repository = '${repository}'`)
      await connection.query(`SET autoinstall_extension_repository = '${repository}'`)
      await connection.query('SET lock_configuration = true')
    } finally {
      await connection.close()
    }
    return result
  }
}
