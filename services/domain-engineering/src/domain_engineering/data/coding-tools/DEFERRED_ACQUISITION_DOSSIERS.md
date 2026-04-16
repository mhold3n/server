# Deferred Acquisition Dossiers

These modules stay deferred until the listed external inputs are provided.

| name | acquisition status | requested from user | recommended runtime target | next sprint entry condition |
| --- | --- | --- | --- | --- |
| FEMM | awaiting_website_downloadable_windows_installer | Provide the approved FEMM installer URL, mirrored binary, or downloaded installer artifact so it can be staged inside the wine-backed runtime. | wine_backed_docker_runtime | A non-interactive FEMM installer artifact is available for canonical packaging into the wine runtime. |
| MA87 | awaiting_license_and_binary_delivery | Provide HSL license entitlement plus source or binaries for MA87 packaging. | licensed_containerized_backend_family | Licensed source or binaries are available for canonical build automation. |
| PYLEECAN | awaiting_website_or_git_dependency_source | Provide a pinned vendored swat-em source or an internal mirror that can replace the current URL dependency with a reproducible CLI install input. | uv_venv_with_locked_dependency_source | The swat-em dependency is pinned to a canonical source that can be installed non-interactively. |
