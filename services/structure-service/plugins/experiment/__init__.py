from kernels.experiment import ExperimentKernel

# from policies import experiment_safety (if policies were python mods)

DOMAIN_ID = "experiment"

KEYWORDS = [
    "hypothesis",
    "control group",
    "randomization",
    "IRB",
    "protocol",
    "blinding",
    "cohort",
    "treatment arm",
]

KERNELS = [ExperimentKernel]

GATES: dict[str, object] = {}

POLICIES: list[object] = [
    # Path("policies/experiment_safety.yaml")
]
