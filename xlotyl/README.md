# xlotyl integration pin (this repository)

**Canonical source code and versioning live in the [xlotyl](https://github.com/XLOTYL/xlotyl) product repository** (and its [openclaw](https://github.com/XLOTYL/openclaw) submodule for `extensions/birtha-bridge`). This directory does **not** duplicate those trees.

Use [`INTEGRATION.json`](INTEGRATION.json) to record which **xlotyl** commit (and optional tag) this **server** repo is aligned with for docs, CI, and deployment pins (`config/xlotyl-images.env`, etc.).

When you merge tool-model lane or bridge changes in xlotyl, update `INTEGRATION.json` with the new full commit SHA.
