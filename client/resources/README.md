# Native shell asset sources

The five PNGs here are the inputs `@capacitor/assets` turns into every iOS
and Android icon and splash size in `ios/` and `android/` (#101 — Wrap the
PWA with Capacitor). Each PNG sits beside the SVG it was rasterized from, so
the provenance does not stop at pixels.

The geometry is the shipped PWA icon's, measured rather than eyeballed: the
white blaze in `public/icons/icon-512.png` spans 17.6% of the canvas wide ×
69.9% tall (white-pixel bounding box at threshold ≥180, measured 2026-08-20;
`icon-192.png` agrees at 17.7% × 69.8%), and the SVGs here draw it at exactly
those proportions over the same forest/stone diagonal split.

The colours, per asset — all design-system tokens
(`src/design-system/tokens/colors.css`): the split is forest-600 `#355c3a` /
stone-700 `#5a5346` everywhere; the blaze is white `#ffffff` on the icons and
the light splash, matching the shipped icon; the dark splash alone uses
blaze-white `#fdfaf2`, deliberately — a pure-white mark on ink-900 `#15140f`
glares, and blaze-white is the token the palette holds for white-on-dark.
Splash backgrounds are paper-100 `#f7f3e9` (light) and ink-900 (dark).

| file                          | consumed as                                                                         |
| ----------------------------- | ----------------------------------------------------------------------------------- |
| `icon-only.png` (1024²)       | iOS app icon, full bleed — iOS applies its own corner radius                        |
| `icon-background.png` (1024²) | Android adaptive icon, background layer                                             |
| `icon-foreground.png` (1024²) | Android adaptive icon, foreground layer — blaze at 62% so no launcher mask clips it |
| `splash.png` (2732²)          | launch screens, light — paper-100 behind the app tile                               |
| `splash-dark.png` (2732²)     | launch screens, dark — ink-900 behind the same tile, blaze-white blaze              |

To regenerate after changing a source (the version is pinned because its
output is committed and a different generator would churn every PNG in both
trees):

```
cd client
npx @capacitor/assets@3.0.5 generate --ios --android --assetPath resources
```

One known quirk of that pinned version, carried knowingly: it emits the
Android adaptive-icon layers at the legacy 48dp launcher sizes (36–192px)
instead of the 108dp layer sizes (81–432px) its own templates define, so API
26+ launchers upscale them ~1.5× — a slight softness, reproduced identically
by the command above. Traced 2026-08-20 to its
`generateAdaptiveIconForeground/Background` filtering `kind === "icon"`
templates; a future @capacitor/assets bump that fixes it will churn the
layer PNGs and sharpen the icon, both expected.

Rasterizing an edited SVG back into its PNG is any SVG renderer at the sizes
above; the PNGs were produced with sharp (librsvg) on 2026-08-20.
