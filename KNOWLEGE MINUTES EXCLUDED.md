# KNOWLEGE MINUTES EXCLUDED

Generated from `knowledge/coding-tools/substrate/minutes-inventory.json` and filtered to non-promoted recovery packages.

Phase state values: `planned`, `installing`, `installed`, `kb_linking`, `linked`, `deferred`.
Phase 3 completion values: `queued`, `smoke_verified`, `blocked_runtime`, `blocked_smoke`, `blocked_external`, `promoted`.

Manual intervention is reserved for proprietary/license-gated modules or modules that still require website/email-delivered artifacts.

## Remaining User Intervention Required

| name | phase3 status | user intervention class | acquisition status | reason excluded |
| --- | --- | --- | --- | --- |
| FEMM | blocked_external | website_download | awaiting_website_downloadable_windows_installer | website-delivered Windows installer has not yet been mirrored into the wine-backed canonical runtime |
| MA87 | blocked_external | proprietary_license | awaiting_license_and_binary_delivery | licensed sparse direct solver backend not packaged in this sprint |
| PYLEECAN | blocked_external | website_download | awaiting_website_or_git_dependency_source | package depends on a URL-only swat-em source that was not locked into a canonical isolated runtime in this sprint |

## By Install Method

### I6 deferred_external_manual -> K6 acquisition_deferred_pack

| name | install batch | kb build batch | cli install channel | cli phase1 status | phase3 status | phase target | phase state | blocked by | acquisition status | reason excluded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FEMM | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | wine_installer_after_download | manual_acquisition_required | blocked_external | next_sprint | deferred | - | awaiting_website_downloadable_windows_installer | website-delivered Windows installer has not yet been mirrored into the wine-backed canonical runtime |
| MA87 | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | licensed_binary_delivery | manual_acquisition_required | blocked_external | next_sprint | deferred | - | awaiting_license_and_binary_delivery | licensed sparse direct solver backend not packaged in this sprint |
| PYLEECAN | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | uv_pip_with_url_dependency | manual_acquisition_required | blocked_external | next_sprint | deferred | - | awaiting_website_or_git_dependency_source | package depends on a URL-only swat-em source that was not locked into a canonical isolated runtime in this sprint |

## By Knowledge Build Method

### K6 acquisition_deferred_pack

| name | install method | install batch | kb build batch | cli install channel | cli phase1 status | phase3 status | phase state | manual acquisition | blocked by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FEMM | I6_deferred_external_manual | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | wine_installer_after_download | manual_acquisition_required | blocked_external | deferred | yes | - |
| MA87 | I6_deferred_external_manual | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | licensed_binary_delivery | manual_acquisition_required | blocked_external | deferred | yes | - |
| PYLEECAN | I6_deferred_external_manual | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | uv_pip_with_url_dependency | manual_acquisition_required | blocked_external | deferred | yes | - |
