// Stages DuckDB-WASM for /data/duckdb/ from an `npm ci` of this directory.
//
//   node stage.mjs <installed dir> <out dir>
//
// <installed dir> holds this directory's package.json, package-lock.json and
// loader.js, and the node_modules `npm ci` wrote from them; build.sh makes it
// under a temporary directory, never in the checkout. <out dir> must not
// exist. Writes:
//
//   duckdb.js        loader.js bundled with @duckdb/duckdb-wasm and
//                    apache-arrow: the module dbt's page imports
//   dist/            the two workers the page can start, and the two WASM
//                    files it can load, each cut into parts (loader.js says
//                    why, and puts them back together)
//   LICENSES.txt     the licence of every package whose code is in the
//                    above, with its LICENSE and NOTICE files where it ships
//                    them (Apache-2.0's section 4 asks for both)
//
// Only the mvp and eh bundles: dbt 2.0.6's page offers DuckDB those two
// (loader.js names the URLs) and never coi, the threaded one.

import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join, relative, resolve, sep } from 'node:path'

const [installed, out] = process.argv.slice(2).map((path) => (path ? resolve(path) : path))
if (!installed || !out) {
  console.error('usage: node stage.mjs <installed dir> <out dir>')
  process.exit(2)
}
if (existsSync(out)) {
  console.error(`${out} already exists; give stage.mjs a directory that is not there yet.`)
  process.exit(1)
}

const require = createRequire(join(installed, 'package.json'))
const esbuild = require('esbuild')
const modules = join(installed, 'node_modules')
const duckdbDist = join(modules, '@duckdb', 'duckdb-wasm', 'dist')

// Reasoned, not measured: under the 25 MiB a Cloudflare Pages deploy accepts
// for one file (loader.js has the measurement), with the margin below it
// picked. Both WASM files of 1.32.0 come out as two parts.
const PART_BYTES = 20 * 1024 * 1024

const WORKERS = ['duckdb-browser-mvp.worker.js', 'duckdb-browser-eh.worker.js']
const WASM = ['duckdb-mvp.wasm', 'duckdb-eh.wasm']

mkdirSync(join(out, 'dist'), { recursive: true })

for (const worker of WORKERS) cpSync(join(duckdbDist, worker), join(out, 'dist', worker))

const parts = {}
for (const file of WASM) {
  const bytes = readFileSync(join(duckdbDist, file))
  const stem = file.replace(/\.wasm$/, '')
  parts[`dist/${file}`] = []
  for (let start = 0, n = 0; start < bytes.length; start += PART_BYTES, n += 1) {
    const name = `dist/${stem}.part${n}.wasm`
    writeFileSync(join(out, name), bytes.subarray(start, start + PART_BYTES))
    parts[`dist/${file}`].push(name)
  }
}

const built = await esbuild.build({
  // The metafile's input paths are relative to this, which packageOf() reads.
  absWorkingDir: installed,
  entryPoints: [join(installed, 'loader.js')],
  bundle: true,
  format: 'esm',
  platform: 'browser',
  minify: true,
  legalComments: 'eof',
  define: { __OURHIKE_DUCKDB_PARTS__: JSON.stringify(parts) },
  metafile: true,
  logLevel: 'warning',
  outfile: join(out, 'duckdb.js'),
})

/** The package directory under node_modules a bundled input belongs to. */
function packageOf(input) {
  const path = relative(modules, join(installed, input)).split(sep)
  if (path[0] === '..') return null
  return path[0].startsWith('@') ? join(path[0], path[1]) : path[0]
}

const packages = new Set(['@duckdb/duckdb-wasm'])
for (const input of Object.keys(built.metafile.inputs)) {
  const name = packageOf(input)
  if (name !== null) packages.add(name.split(sep).join('/'))
}

const licences = []
for (const name of [...packages].sort()) {
  const root = join(modules, ...name.split('/'))
  const manifest = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))
  licences.push(`${'='.repeat(72)}\n${name}@${manifest.version} (${manifest.license ?? 'no licence field'})\n`)
  for (const file of readdirSync(root).filter((f) => /^(licen[cs]e|notice)/i.test(f)).sort()) {
    licences.push(`--- ${file}\n${readFileSync(join(root, file), 'utf8').trimEnd()}\n`)
  }
}
writeFileSync(join(out, 'LICENSES.txt'), licences.join('\n'))

const files = []
const walk = (dir) => {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) walk(path)
    else files.push(path)
  }
}
walk(out)
const bytes = files.reduce((sum, path) => sum + readFileSync(path).length, 0)
console.log(
  `DuckDB-WASM ${JSON.parse(readFileSync(join(dirname(duckdbDist), 'package.json'), 'utf8')).version}: ` +
    `${files.length} files, ${bytes.toLocaleString('en-US')} bytes in ${out}; ` +
    `bundled from ${[...packages].sort().join(', ')}`,
)
