# Bundled BlazeFace weights

The face half of the on-device share screen (#837): before a photo leaves the
phone, `src/lib/photoScreenEngine.ts` runs Google's BlazeFace detector over it
so the share can be flagged for the moderation queue — on the phone, which is
the entire point. The check must never need signal (a hiker shares from a
shelter with none) and must never send the photo anywhere to be looked at, so
the weights are served from the app's own origin like the glyphs one
directory up.

Deliberately **not** in the service worker's precache: `vite.config.ts`'s
workbox `globPatterns` match `.js`/`.css`/`.html`, glyph `.pbf`s and
`.woff2`s, and nothing here — these files are fetched (and then held in the
browser's HTTP cache) only the first time someone actually opens the share
sheet. A hiker who never shares a photo never downloads a face detector.

## Contents and provenance

`model.json` (64,036 bytes, sha256
`7b6bb6f35e5a7899232de51dda8bf514ef9664ca7ec58388c9fecc088c883b58`) and
`group1-shard1of1.bin` (401,768 bytes, sha256
`60b481ab6c19352673cdb21e02e639f90883db1393ac52d07c7ea4e1e11cb2cd`), fetched
2026-08-20 from TensorFlow Hub —
`https://tfhub.dev/tensorflow/tfjs-model/blazeface/1/default/1` with
`?tfjs-format=file` — which is the exact URL the
`@tensorflow-models/blazeface` npm package (0.1.0, in package.json) loads by
default. Vendoring it swaps the third-party fetch for our origin and changes
no bytes.

The nudity half of the same screen has no directory here on purpose: nsfwjs
4.x ships its MobileNetV2 weights inside the npm package as lazy JS chunks,
so those arrive through the bundler (and are excluded from the precache by
name — see `globIgnores` in vite.config.ts).

## Licence

BlazeFace is © Google LLC, Apache License 2.0 — the licence of both the
[tensorflow/tfjs-models](https://github.com/tensorflow/tfjs-models)
repository that published the model and the TF Hub listing it was fetched
from. See CONTRIBUTING.md's "A note on data and licences".
