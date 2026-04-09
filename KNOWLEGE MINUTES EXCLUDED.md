# KNOWLEGE MINUTES EXCLUDED

Generated from `knowledge/coding-tools/substrate/minutes-inventory.json`.

Phase state values: `planned`, `installing`, `installed`, `kb_linking`, `linked`, `deferred`.

Manual intervention is reserved for proprietary/license-gated modules or modules that still require website/email-delivered artifacts.

## Remaining User Intervention Required

| name | user intervention class | acquisition status | reason excluded |
| --- | --- | --- | --- |
| FEMM | website_download | awaiting_website_downloadable_windows_installer | website-delivered Windows installer has not yet been mirrored into the wine-backed canonical runtime |
| MA87 | proprietary_license | awaiting_license_and_binary_delivery | licensed sparse direct solver backend not packaged in this sprint |
| PYLEECAN | website_download | awaiting_website_or_git_dependency_source | package depends on a URL-only swat-em source that was not locked into a canonical isolated runtime in this sprint |

## By Install Method

### I1 containerized_native_solver_platform -> K1 executable_solver_platform_pack

| name | install batch | kb build batch | cli install channel | cli phase1 status | phase target | phase state | blocked by | acquisition status | reason excluded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CalculiX | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no viable canonical Docker runtime verified in this sprint |
| Code_Aster | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no viable canonical Docker runtime was verified in this sprint |
| code_saturne | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no viable canonical Docker runtime was verified in this sprint |
| Dakota | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no isolated runtime package was verified in this sprint |
| deal.II | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no isolated runtime package was verified in this sprint |
| FEniCSx | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no isolated runtime package was verified in this sprint |
| Hermes | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no isolated runtime package was verified in this sprint |
| Kratos Multiphysics | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no viable canonical Docker runtime was verified in this sprint |
| MBDyn | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | reserve-list runtime not prioritized in this sprint |
| MOOSE | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no viable canonical Docker runtime was verified in this sprint |
| OpenFOAM | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no viable canonical Docker runtime verified in this sprint |
| OpenModelica | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no canonical headless Modelica toolchain was verified in this sprint |
| OpenSMOKE++ | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no isolated runtime package was verified in this sprint |
| OpenWAM | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no isolated runtime package was verified in this sprint |
| ParaView | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | GUI-heavy visualization stack was not packaged in this sprint |
| Project Chrono | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no reliable isolated runtime package was verified in this sprint |
| SALOME | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | GUI-heavy platform was not packaged in this sprint |
| SU2 | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | phase1 | planned | - | not_required | no viable canonical Docker runtime was verified in this sprint |

### I2 containerized_native_backend_family -> K2 backend_family_pack

| name | install batch | kb build batch | cli install channel | cli phase1 status | phase target | phase state | blocked by | acquisition status | reason excluded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CGAL | phase1_batch1e_geometry_native_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | no viable isolated runtime package was verified in this sprint |
| CHOLMOD | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native sparse factorization backend was not verified in this sprint |
| hypre | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native AMG backend was not verified in this sprint |
| IPOPT | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build_with_local_hsl | ready | phase1 | planned | - | not_required | canonical Docker path is defined for open IPOPT with staged local HSL inputs and Intel oneMKL, but the container build has not been verified in this sprint |
| KLU | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native sparse factorization backend was not verified in this sprint |
| MA57 | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build_with_local_hsl | ready | phase1 | planned | - | not_required | local HSL source is staged for containerized backend packaging, but the canonical Docker build has not been verified in this sprint |
| MA77 | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build_with_local_hsl | ready | phase1 | planned | - | not_required | local HSL source is staged for containerized backend packaging, but the canonical Docker build has not been verified in this sprint |
| MA86 | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build_with_local_hsl | ready | phase1 | planned | - | not_required | local HSL source is staged for containerized backend packaging, but the canonical Docker build has not been verified in this sprint |
| MA97 | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build_with_local_hsl | ready | phase1 | planned | - | not_required | local HSL source is staged for containerized backend packaging, but the canonical Docker build has not been verified in this sprint |
| MUMPS | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native sparse direct backend was not verified in this sprint |
| OpenCAMLib | phase1_batch1e_geometry_native_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | no reliable isolated runtime was verified in this sprint |
| PARDISO | phase1_batch1f_onemkl_family | phase2_batch_k2_backend_families | docker_build_with_onemkl | ready | phase1 | planned | - | not_required | licensed PARDISO acquisition has been replaced with an Intel oneMKL container path, but that canonical Docker build has not been verified in this sprint |
| PETSc | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | HPC native runtime was not verified in this sprint |
| PETSc GAMG | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | minutes-module://petsc | not_required | PETSc runtime was not verified in this sprint |
| PETSc KSP | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | minutes-module://petsc | not_required | PETSc runtime was not verified in this sprint |
| PicoGK / ShapeKernel | phase1_batch1e_geometry_native_family | phase2_batch_k2_backend_families | dotnet_nuget | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and runtime-verified in the shared .NET knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| PRIMME | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native eigensolver runtime was not verified in this sprint |
| SLEPc | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | minutes-module://petsc | not_required | PETSc-based eigensolver runtime was not verified in this sprint |
| STRUMPACK | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native sparse direct backend was not verified in this sprint |
| SuiteSparse | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native sparse factorization backend was not verified in this sprint |
| SUNDIALS | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native solver stack was not verified in this sprint |
| SuperLU | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native sparse direct backend was not verified in this sprint |
| SuperLU_DIST | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native sparse direct backend was not verified in this sprint |
| TChem | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | HPC chemistry runtime was not verified in this sprint |
| Trilinos | phase1_batch1b_trilinos_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | Trilinos runtime was not verified in this sprint |
| Trilinos Belos | phase1_batch1b_trilinos_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | minutes-module://trilinos | not_required | Trilinos runtime was not verified in this sprint |
| Trilinos Ifpack2 | phase1_batch1b_trilinos_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | minutes-module://trilinos | not_required | Trilinos runtime was not verified in this sprint |
| Trilinos MueLu | phase1_batch1b_trilinos_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | minutes-module://trilinos | not_required | Trilinos runtime was not verified in this sprint |
| UMFPACK | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | phase1 | planned | - | not_required | native sparse factorization backend was not verified in this sprint |

### I3 python_first_venv_package -> K3 python_framework_pack

| name | install batch | kb build batch | cli install channel | cli phase1 status | phase target | phase state | blocked by | acquisition status | reason excluded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BoTorch | phase1_batch4d_distributed_ml_reserve | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| Compas | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| Dymos | phase1_batch4a_openmdao_adjacent | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| IDAES | phase1_batch4b_process_system | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| MPhys | phase1_batch4a_openmdao_adjacent | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| Nevergrad | phase1_batch4d_distributed_ml_reserve | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| OpenPNM | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| OptaS | phase1_batch4b_process_system | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| PorePy | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | ready | phase1 | planned | - | not_required | reserve-list runtime not prioritized in this sprint |
| PyPHS | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | ready | phase1 | planned | - | not_required | not prioritized for this sprint |
| Ray | phase1_batch4d_distributed_ml_reserve | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| RMG-Py | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | ready | phase1 | planned | - | not_required | reserve-list runtime not prioritized in this sprint |
| SimPEG | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| SimPy | phase1_batch4b_process_system | phase2_batch_k3_python_frameworks | uv_pip | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and import-verified in the knowledge runtime, but runtime-linked knowledge artifacts have not been built in this sprint |

### I4 host_companion_wrapper -> K4 companion_host_bound_pack

| name | install batch | kb build batch | cli install channel | cli phase1 status | phase target | phase state | blocked by | acquisition status | reason excluded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MEDCoupling | phase1_batch3f_salome_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | blocked_by_parent_runtime | phase1 | planned | minutes-module://salome | not_required | native SALOME dependency stack was not verified in this sprint |
| OMPython | phase1_batch3d_modelica_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | installed | phase1 | installed | minutes-module://openmodelica | verified_in_knowledge_runtime_parent_pending | installed and import-verified in the knowledge runtime, but the parent host runtime and runtime-linked knowledge artifacts have not been fully built in this sprint |
| petsc4py | phase1_batch3a_petsc_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | blocked_by_parent_runtime | phase1 | planned | minutes-module://petsc | not_required | depends on PETSc runtime that was not verified in this sprint |
| preCICE | phase1_batch3c_coupling_wrapper | phase2_batch_k4_host_companions | docker_or_source_build_after_parent_runtime | blocked_by_parent_runtime | phase1 | planned | minutes-module://openfoam, minutes-module://calculix | not_required | no viable canonical Docker runtime was verified in this sprint |
| PyFMI | phase1_batch3e_fmu_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | blocked_by_parent_runtime | phase1 | planned | minutes-module://openmodelica | not_required | native FMI backend was not verified in this sprint |
| pyOptSparse | phase1_batch3b_nlp_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | blocked_by_parent_runtime | phase1 | planned | minutes-module://ipopt | not_required | depends on the open IPOPT plus oneMKL/HSL container path that has not been verified in this sprint |
| RhinoCommon | phase1_batch3h_rhino_host_wrapper | phase2_batch_k4_host_companions | host_app_cli | installed | phase1 | installed | - | verified_in_knowledge_runtime | installed and CLI-verified in the Rhino 8 host runtime, but runtime-linked knowledge artifacts have not been built in this sprint |
| VTK | phase1_batch3g_visualization_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | installed | phase1 | installed | minutes-module://paraview | verified_in_knowledge_runtime_parent_pending | installed and import-verified in the knowledge runtime, but the parent host runtime and runtime-linked knowledge artifacts have not been fully built in this sprint |

### I5 knowledge_only_standard -> K5 standard_spec_pack

| name | install batch | kb build batch | cli install channel | cli phase1 status | phase target | phase state | blocked by | acquisition status | reason excluded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CGNS | phase1_batch5_standards | phase2_batch_k5_standards | knowledge_only | knowledge_only | phase1 | planned | - | not_required | standard/format, not a standalone runtime installation |
| Exodus II | phase1_batch5_standards | phase2_batch_k5_standards | knowledge_only | knowledge_only | phase1 | planned | - | not_required | standard/format, not a standalone runtime installation |
| FMI / FMUs | phase1_batch5_standards | phase2_batch_k5_standards | knowledge_only | knowledge_only | phase1 | planned | - | not_required | standard/specification, not a standalone runtime installation |
| Modelica Standard Library | phase1_batch5_standards | phase2_batch_k5_standards | knowledge_only | knowledge_only | phase1 | planned | minutes-module://openmodelica | not_required | depends on a verified Modelica host that was not packaged in this sprint |

### I6 deferred_external_manual -> K6 acquisition_deferred_pack

| name | install batch | kb build batch | cli install channel | cli phase1 status | phase target | phase state | blocked by | acquisition status | reason excluded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FEMM | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | wine_installer_after_download | manual_acquisition_required | next_sprint | deferred | - | awaiting_website_downloadable_windows_installer | website-delivered Windows installer has not yet been mirrored into the wine-backed canonical runtime |
| MA87 | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | licensed_binary_delivery | manual_acquisition_required | next_sprint | deferred | - | awaiting_license_and_binary_delivery | licensed sparse direct solver backend not packaged in this sprint |
| PYLEECAN | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | uv_pip_with_url_dependency | manual_acquisition_required | next_sprint | deferred | - | awaiting_website_or_git_dependency_source | package depends on a URL-only swat-em source that was not locked into a canonical isolated runtime in this sprint |

## By Knowledge Build Method

### K1 executable_solver_platform_pack

| name | install method | install batch | kb build batch | cli install channel | cli phase1 status | phase state | manual acquisition | blocked by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CalculiX | I1_containerized_native_solver_platform | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| Code_Aster | I1_containerized_native_solver_platform | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| code_saturne | I1_containerized_native_solver_platform | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| Dakota | I1_containerized_native_solver_platform | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| deal.II | I1_containerized_native_solver_platform | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| FEniCSx | I1_containerized_native_solver_platform | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| Hermes | I1_containerized_native_solver_platform | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| Kratos Multiphysics | I1_containerized_native_solver_platform | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| MBDyn | I1_containerized_native_solver_platform | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| MOOSE | I1_containerized_native_solver_platform | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| OpenFOAM | I1_containerized_native_solver_platform | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| OpenModelica | I1_containerized_native_solver_platform | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| OpenSMOKE++ | I1_containerized_native_solver_platform | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| OpenWAM | I1_containerized_native_solver_platform | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| ParaView | I1_containerized_native_solver_platform | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| Project Chrono | I1_containerized_native_solver_platform | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| SALOME | I1_containerized_native_solver_platform | phase1_batch2b_solver_platforms_second_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |
| SU2 | I1_containerized_native_solver_platform | phase1_batch2a_solver_platforms_first_wave | phase2_batch_k1_solver_platforms | docker_build | ready | planned | no | - |

### K2 backend_family_pack

| name | install method | install batch | kb build batch | cli install channel | cli phase1 status | phase state | manual acquisition | blocked by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CGAL | I2_containerized_native_backend_family | phase1_batch1e_geometry_native_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| CHOLMOD | I2_containerized_native_backend_family | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| hypre | I2_containerized_native_backend_family | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| IPOPT | I2_containerized_native_backend_family | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build_with_local_hsl | ready | planned | no | - |
| KLU | I2_containerized_native_backend_family | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| MA57 | I2_containerized_native_backend_family | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build_with_local_hsl | ready | planned | no | - |
| MA77 | I2_containerized_native_backend_family | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build_with_local_hsl | ready | planned | no | - |
| MA86 | I2_containerized_native_backend_family | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build_with_local_hsl | ready | planned | no | - |
| MA97 | I2_containerized_native_backend_family | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build_with_local_hsl | ready | planned | no | - |
| MUMPS | I2_containerized_native_backend_family | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| OpenCAMLib | I2_containerized_native_backend_family | phase1_batch1e_geometry_native_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| PARDISO | I2_containerized_native_backend_family | phase1_batch1f_onemkl_family | phase2_batch_k2_backend_families | docker_build_with_onemkl | ready | planned | no | - |
| PETSc | I2_containerized_native_backend_family | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| PETSc GAMG | I2_containerized_native_backend_family | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | minutes-module://petsc |
| PETSc KSP | I2_containerized_native_backend_family | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | minutes-module://petsc |
| PicoGK / ShapeKernel | I2_containerized_native_backend_family | phase1_batch1e_geometry_native_family | phase2_batch_k2_backend_families | dotnet_nuget | installed | installed | no | - |
| PRIMME | I2_containerized_native_backend_family | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| SLEPc | I2_containerized_native_backend_family | phase1_batch1a_petsc_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | minutes-module://petsc |
| STRUMPACK | I2_containerized_native_backend_family | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| SuiteSparse | I2_containerized_native_backend_family | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| SUNDIALS | I2_containerized_native_backend_family | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| SuperLU | I2_containerized_native_backend_family | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| SuperLU_DIST | I2_containerized_native_backend_family | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| TChem | I2_containerized_native_backend_family | phase1_batch1d_nlp_time_chem_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| Trilinos | I2_containerized_native_backend_family | phase1_batch1b_trilinos_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |
| Trilinos Belos | I2_containerized_native_backend_family | phase1_batch1b_trilinos_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | minutes-module://trilinos |
| Trilinos Ifpack2 | I2_containerized_native_backend_family | phase1_batch1b_trilinos_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | minutes-module://trilinos |
| Trilinos MueLu | I2_containerized_native_backend_family | phase1_batch1b_trilinos_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | minutes-module://trilinos |
| UMFPACK | I2_containerized_native_backend_family | phase1_batch1c_sparse_direct_family | phase2_batch_k2_backend_families | docker_build | ready | planned | no | - |

### K3 python_framework_pack

| name | install method | install batch | kb build batch | cli install channel | cli phase1 status | phase state | manual acquisition | blocked by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BoTorch | I3_python_first_venv_package | phase1_batch4d_distributed_ml_reserve | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |
| Compas | I3_python_first_venv_package | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |
| Dymos | I3_python_first_venv_package | phase1_batch4a_openmdao_adjacent | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |
| IDAES | I3_python_first_venv_package | phase1_batch4b_process_system | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |
| MPhys | I3_python_first_venv_package | phase1_batch4a_openmdao_adjacent | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |
| Nevergrad | I3_python_first_venv_package | phase1_batch4d_distributed_ml_reserve | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |
| OpenPNM | I3_python_first_venv_package | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |
| OptaS | I3_python_first_venv_package | phase1_batch4b_process_system | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |
| PorePy | I3_python_first_venv_package | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | ready | planned | no | - |
| PyPHS | I3_python_first_venv_package | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | ready | planned | no | - |
| Ray | I3_python_first_venv_package | phase1_batch4d_distributed_ml_reserve | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |
| RMG-Py | I3_python_first_venv_package | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | ready | planned | no | - |
| SimPEG | I3_python_first_venv_package | phase1_batch4c_inverse_physics_domain | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |
| SimPy | I3_python_first_venv_package | phase1_batch4b_process_system | phase2_batch_k3_python_frameworks | uv_pip | installed | installed | no | - |

### K4 companion_host_bound_pack

| name | install method | install batch | kb build batch | cli install channel | cli phase1 status | phase state | manual acquisition | blocked by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MEDCoupling | I4_host_companion_wrapper | phase1_batch3f_salome_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | blocked_by_parent_runtime | planned | no | minutes-module://salome |
| OMPython | I4_host_companion_wrapper | phase1_batch3d_modelica_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | installed | installed | no | minutes-module://openmodelica |
| petsc4py | I4_host_companion_wrapper | phase1_batch3a_petsc_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | blocked_by_parent_runtime | planned | no | minutes-module://petsc |
| preCICE | I4_host_companion_wrapper | phase1_batch3c_coupling_wrapper | phase2_batch_k4_host_companions | docker_or_source_build_after_parent_runtime | blocked_by_parent_runtime | planned | no | minutes-module://openfoam, minutes-module://calculix |
| PyFMI | I4_host_companion_wrapper | phase1_batch3e_fmu_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | blocked_by_parent_runtime | planned | no | minutes-module://openmodelica |
| pyOptSparse | I4_host_companion_wrapper | phase1_batch3b_nlp_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | blocked_by_parent_runtime | planned | no | minutes-module://ipopt |
| RhinoCommon | I4_host_companion_wrapper | phase1_batch3h_rhino_host_wrapper | phase2_batch_k4_host_companions | host_app_cli | installed | installed | no | - |
| VTK | I4_host_companion_wrapper | phase1_batch3g_visualization_wrapper | phase2_batch_k4_host_companions | uv_pip_after_parent_runtime | installed | installed | no | minutes-module://paraview |

### K5 standard_spec_pack

| name | install method | install batch | kb build batch | cli install channel | cli phase1 status | phase state | manual acquisition | blocked by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CGNS | I5_knowledge_only_standard | phase1_batch5_standards | phase2_batch_k5_standards | knowledge_only | knowledge_only | planned | no | - |
| Exodus II | I5_knowledge_only_standard | phase1_batch5_standards | phase2_batch_k5_standards | knowledge_only | knowledge_only | planned | no | - |
| FMI / FMUs | I5_knowledge_only_standard | phase1_batch5_standards | phase2_batch_k5_standards | knowledge_only | knowledge_only | planned | no | - |
| Modelica Standard Library | I5_knowledge_only_standard | phase1_batch5_standards | phase2_batch_k5_standards | knowledge_only | knowledge_only | planned | no | minutes-module://openmodelica |

### K6 acquisition_deferred_pack

| name | install method | install batch | kb build batch | cli install channel | cli phase1 status | phase state | manual acquisition | blocked by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FEMM | I6_deferred_external_manual | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | wine_installer_after_download | manual_acquisition_required | deferred | yes | - |
| MA87 | I6_deferred_external_manual | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | licensed_binary_delivery | manual_acquisition_required | deferred | yes | - |
| PYLEECAN | I6_deferred_external_manual | phase1_batch6_deferred_external_manual | phase2_batch_k6_deferred_acquisition | uv_pip_with_url_dependency | manual_acquisition_required | deferred | yes | - |
