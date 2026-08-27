# Bundled nsfwjs MobileNetV2 weights

The nudity half of the on-device share screen (#837), the twin of
`../blazeface/` — read that README for why these live under the app's own
origin and stay out of the service worker's precache. The finding this model
produces is the one with a hold behind it: a share flagged `nudity` waits
for one human glance at the maintaining club before it appears on any card
(#570's flag-never-block posture, and the share sheet's "Hidden until you
tap" step says so to the hiker in advance).

## Contents and provenance

`model.json` (117,928 bytes, sha256
`feffc6868d61e412a4e7a22657a3d07a8a48df6e11688a9e25b77c23cb7b45c9`) and
`group1-shard1of1` (2,619,461 bytes, sha256
`8e7dddbb16acacc1bf1601b1b8a761e730ff934b7f2d7771312b2f000e5f5f13`),
extracted 2026-08-20 from the `nsfwjs@4.3.0` npm package's own bundled
MobileNetV2 model by `scripts/extract-nsfw-model.mjs` — run it after an
nsfwjs upgrade and the diff of these two files is the model change. The
script's header says why the package's bundled-import path cannot be used
directly (its loader needs Node's `Buffer`) and why the weights file has no
extension (the name is the manifest's, verbatim).

## Licence

nsfwjs and its published model are © Infinite Red, Inc., MIT-licensed
([infinitered/nsfwjs](https://github.com/infinitered/nsfwjs)); the model
descends from [GantMan/nsfw_model](https://github.com/GantMan/nsfw_model)
(same licence). See CONTRIBUTING.md's "A note on data and licences".
