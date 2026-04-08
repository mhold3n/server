# Routing policy (narrative)

<!--
For agents: machine-readable contract is `routing-policy.schema.json`. This page explains intent.
-->

## Role

The routing policy binds **task_packet.routing_metadata.router_policy_version** to:

- default **budget** and **escalation** behavior,
- **cost ceilings** per trace,
- **plane ↔ tool** admissibility (who may call which tools and with what side effects),
- optional **cache key** hints.

## Escalation

Rules in `escalation_rules[]` map **signals** (e.g. open conflict count, verification failures) to **actions** (`ESCALATE`, `REQUEST_HUMAN`, `RECOMPRESS`, `STOP`). Thresholds are numeric comparators evaluated by the control plane **after** deterministic gates.

## Planes

`plane_tool_matrix[]` lists allowed tool names per **plane** (`research`, `multimodal`, `coding`, `analysis_simulation`, `review_verification`, etc.) and a **side_effects** tier. This is the mechanical enforcement of “no symmetric model chat”: specialists only receive **task packets** and **artifacts**, not peer messages.

## Versioning

Changing policy semantics requires a new `router_policy_version` string and, when stored as an artifact, a new `routing_policy_id` / `schema_version` as appropriate. Downstream task packets must reference the policy version they were issued under.
