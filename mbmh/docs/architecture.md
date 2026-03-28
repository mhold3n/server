# Architecture

## Training Layer
Strictly internal. Manages dataset loading, metrics collection, PEFT application, and checkpoint saving.

## Runtime Layer
Consumed by agents or APIs via packaged bundles. Cannot import `src.training.*`.

## Integration Layer
Adapters map runtime payloads into consumer-specific payload schemas (e.g. OpenClaw).

## Platform Rules
- Primary training is PyTorch native (accelerate/TRL).
- Apple Silicon defaults explicitly bounded in configs.
- NVIDIA defaults use FSDP internally.
