# Vendored front-end libraries

Served locally (no CDN calls at runtime) so no data or usage leaves the machine and the app works offline.
Downloaded from jsDelivr (npm) at the pinned versions below; SHA-384 digests are in `CHECKSUMS.txt`.

| File | Package | Version | License |
|------|---------|---------|---------|
| `alpine-3.14.9.min.js` | alpinejs (`dist/cdn.min.js`) | 3.14.9 | MIT |
| `plotly-2.35.2.min.js` | plotly.js-dist-min | 2.35.2 | MIT |
| `tabulator-6.3.1.min.js`, `tabulator_simple-6.3.1.min.css` | tabulator-tables | 6.3.1 | MIT |

To upgrade: download the new version, update the file names in `app/web/index.html`, regenerate `CHECKSUMS.txt`
(`shasum -a 384 *.js *.css`), and update this table.
