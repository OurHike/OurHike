// Rebuilds public/models/nsfw/ from the nsfwjs package in node_modules.
//
//   node scripts/extract-nsfw-model.mjs
//
// nsfwjs 4.x ships its MobileNetV2 model as two UMD JavaScript bundles - the
// topology as an object, the weights as one base64 string - meant to be
// loaded through the package's own bundled-import path. That path is
// unusable in this app: its loader decodes the base64 with Buffer.from, a
// Node API no browser has (nsfwjs core.js, JSONHandler). So the raw
// tfjs-layers files are extracted here instead and served from
// public/models/nsfw/, where src/lib/photoScreenEngine.ts loads them over
// plain fetch - same bytes, no Node dependency, and the package's other two
// models (35MB of InceptionV3 + MobileNetV2Mid) never enter the build.
//
// The weights file is named `group1-shard1of1` - no extension - because
// that is the exact path the model.json's weightsManifest declares and
// tf.loadLayersModel resolves relative to the model.json URL. Renaming it
// would mean editing the manifest, and shipping the manifest unmodified is
// the whole provenance story.
//
// Re-run after an nsfwjs upgrade; the diff of the two output files is the
// model change, reviewable as such.

import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const root = join(dirname(fileURLToPath(import.meta.url)), '..')

// The UMD bundles take their CommonJS branch under require() and export the
// model JSON / the base64 weight string directly. By filesystem path, not
// package subpath - nsfwjs's exports map (correctly) does not export its
// model bundles, and this script is doing surgery on the installed package
// on purpose.
const models = join(root, 'node_modules', 'nsfwjs', 'dist', 'models', 'mobilenet_v2')
const model = require(join(models, 'model.min.js'))
const shard = require(join(models, 'group1-shard1of1.min.js'))

const outDir = join(root, 'public', 'models', 'nsfw')
mkdirSync(outDir, { recursive: true })
writeFileSync(join(outDir, 'model.json'), JSON.stringify(model))
writeFileSync(join(outDir, 'group1-shard1of1'), Buffer.from(shard, 'base64'))
console.log(`Extracted MobileNetV2 (${shard.length} base64 chars) -> ${outDir}`)
