# LLM-Driven Corroboration Pipeline for High-Affinity STEM Leads

## Executive summary
A reliable “huge if true” system should treat high-affinity platforms (fast spread, mixed credibility) as **lead surfaces**, then run a **trace-first corroboration workflow** that collapses repeated coverage into **independent evidence families** before assigning any credibility. This is essential because repetition across posts and syndicated articles can create pseudo-consensus that still originates from a single press release, preprint, or misread figure. This design principle is reinforced by practical fact-checking requirements for explainability (show evidence, show uncertainty, show gaps) and by rumor-verification research emphasizing evolving context over time. citeturn6search0turn2search1

A pragmatic architecture uses an orchestrator plus containerized browser workers and three LLM-agent roles: **Scout** (find candidate “huge” leads), **Trace** (reduce each lead to atomic claims and root artifacts), and **Corroborator** (search for independent corroboration, check retractions/corrections, and assemble an auditable evidence packet). This pattern aligns with action+reasoning agent paradigms (ReAct) and browser-assisted, reference-collecting systems (WebGPT). citeturn2search3turn3search0

The system’s output should not be a single “true/false.” It should be an **auditable evidence packet** with provenance (who/what/when produced the evidence), replayable captures (snapshots/WARC), cryptographic hashes, timestamps, explicit independence analysis, and a two-axis score: **H (impact)** and **T (truth/corroboration state)**. Provenance concepts map cleanly to W3C PROV-DM, and replayable capture is well-supported by the WARC archival format. citeturn3search2turn7search0

## Assumptions and scope boundaries
This report assumes: English (en-US), timezone America/Los_Angeles, prepared on April 11, 2026; implementation language and compute budget are unspecified. It treats Reddit and X as example lead sources but generalizes to other high-affinity channels. citeturn6search15turn6search10

The pipeline’s primary objective is **auditable corroboration state** over time (“as of t”), not omniscient truth. This is consistent with how rumor verification is framed as an evolving decision problem that incorporates conversation dynamics and later updates. citeturn2search1

An internal draft review (user-provided) highlights common failure modes to design against: conceptual drift between “corroboration” and “verification,” lack of formal independence/citation-collapse, weak temporal/versioning model, and insufficient provenance discipline. fileciteturn0file0

## Scope and definitions for “huge if true” in STEM
“Huge if true” works best when formalized as **impact priors** over **claim types**, rather than as a vibe-based label. A STEM claim is “huge if true” when validation would plausibly shift accepted limits, enable major new capability, or meaningfully change decision-making in research/engineering practice.

A workable operationalization is to define “huge” (H) by *consequence* and “true” (T) by *corroboration state*:

- **H (Impact axis):** expected downstream consequence if validated (e.g., order-of-magnitude improvements; new fundamental discovery; safety-critical failure mode; standards/regulatory change; replication of a disputed result).
- **T (Truth axis):** evidence-supported corroboration state, ideally tri-state or multi-state rather than binary; at minimum “supported / refuted / insufficient information,” mirroring standard fact-verification benchmarks. citeturn2search0turn2search2

### Atomic claims
An **atomic claim** is a single proposition with enough structure to test, trace, or bound, e.g., “System A achieved metric M on benchmark B under conditions C,” rather than “Breakthrough in AI!” Claim atomicity matters because evidence is typically scoped and conditional; FEVER-style fact verification explicitly separates claims and identifies evidence needed for support/refutation. citeturn2search0

### Trace-first corroboration
“Trace-first” means you do not treat social posts or even news articles as confirmation; you treat them as pointers. Corroboration begins only after tracing to **root artifacts** (papers, datasets, filings, official notices) and then seeking **independent corroboration** beyond derivative coverage. RumourEval’s framing—needing evolving conversation and news updates to reach veracity—supports designing for time-dependent, evidence-driven state changes. citeturn2search1

## Signal sources and ingestion options
A high-recall system benefits from multiple signal streams: (1) high-affinity leads, (2) primary artifact streams, (3) credible secondary coverage, and (4) archives/feeds that reduce reliance on fragile scraping.

High-leverage primary/official sources relevant to STEM corroboration include:
- Scholarly metadata and update signals via Crossref REST API and Crossmark (corrections/retractions/updates). citeturn0search0turn5search1
- Retraction and correction data via the Retraction Watch dataset and its availability in Crossref’s API. citeturn5search12turn9search7
- Preprint streams and disclaimers from arXiv and medRxiv; both explicitly note “not peer review,” but medRxiv’s medical context includes stronger cautions about uncertified work. citeturn1search0turn1search1
- Biomedical literature metadata via NCBI E-utilities (Entrez) for PubMed/PMC lookups and linkage. citeturn1search2turn1search14
- Scholarly graph/citations via Semantic Scholar’s Academic Graph API (useful for citation networks and related work discovery). citeturn1search3turn1search7
- News/event aggregation APIs (third-party) such as GDELT (open event/news datasets + APIs) as a backstop for coverage discovery. citeturn5search3turn9search1
- Web archives such as Common Crawl (useful for large-scale retrospective evidence discovery but constrained by underlying copyright/rights). citeturn4search3turn4search11

### Ingestion options comparison
| Ingestion mode | Typical use in this system | Pros | Cons | Compliance risk profile |
|---|---|---|---|---|
| **API-first (platform + primary sources)** | Pull leads from platform APIs; pull primary artifacts from scholarly APIs/feeds | Stable, explicit rate limits; better ToS alignment; structured metadata; easier auditing of “what was fetched” | Coverage constraints; access costs; rate limits; some platform data unavailable | Lowest risk when adhering to platform terms; X explicitly warns non‑API automation can lead to permanent suspension; rate limits enforced. citeturn0search1turn6search7turn6search10 |
| **Headless browsing (containerized browsers)** | Downstream corroboration on open web sources; rendering JS-heavy pages; capturing exact viewed text | High coverage; handles dynamic pages; captures human-viewable context; enables WebGPT-style reference collection | CAPTCHAs/anti-bot friction; brittle selectors; higher security risk on untrusted pages; ToS often restrictive | Medium to high risk depending on target; Playwright recommends separate user + seccomp on untrusted sites; robots.txt is advisory and not authorization. citeturn0search3turn3search1 |
| **Third-party news/event feeds and archives** | Broad corroboration search; “better coverage” discovery; retrospective lookup | High scale; reduces per-site scraping; can improve recall across publishers; archives can support replay | Vendor lock-in; licensing/copyright constraints; incomplete/biased coverage; timeliness varies | Variable; requires respecting feed ToS (e.g., NewsAPI terms) and underlying content rights (Common Crawl does not grant rights to crawled content). citeturn8search0turn4search11turn5search3 |

## Trace-first corroboration workflow and agent architecture
A robust workflow should enforce “trace-first” as a hard invariant: no claim can be labeled “supported” until a root artifact is captured and cited.

The design is well supported by agentic tool-use literature: ReAct formalizes interleaving reasoning with actions (search/lookup), and WebGPT operationalizes browsing with mandatory reference collection to support human evaluation. citeturn2search3turn3search0

```mermaid
flowchart TD
  A[Lead Intake: high-affinity posts, threads, alerts] --> B[Scout: detect candidate "huge" leads]
  B --> C[Claim Extraction: normalize + split into atomic claims]
  C --> D[Trace: open linked article(s) and extract citations]
  D --> E{Root artifact found?}
  E -- No --> E1[Packet: "Untraced" + gaps + follow-up queries]
  E -- Yes --> F[Fetch root artifacts: paper/preprint/dataset/filing/notice]
  F --> G[Provenance capture: snapshot/WARC + hashes + timestamps]
  G --> H[Lineage collapse: cluster derivative sources into evidence families]
  H --> I[Corroborator: independent corroboration search]
  I --> J[Update checks: retractions/corrections/versioning signals]
  J --> K[Score H (impact) + T (truth/corroboration state)]
  K --> L[Auditable evidence packet + report]
  L --> M[Revisit schedule for high-H items to catch updates]
```

This workflow explicitly encodes (1) atomic claim extraction, (2) root artifact tracing, (3) evidence-family collapse, (4) independent corroboration, (5) update checking, and (6) temporal revisits—features emphasized by rumor verification tasks and by real-world verification datasets that penalize evidence leakage and weak evidence. citeturn2search1turn2search2

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["W3C PROV provenance graph example","WARC web archive file format visualization","browser automation container security seccomp diagram","fact checking evidence retrieval workflow diagram"],"num_per_query":1}

### Agent roles and container topology
A clean separation of labor reduces hallucination risk and improves auditability:

**Orchestrator (controller + scheduler).** Coordinates jobs, budgets, retries, and revisit schedules; enforces allowlists and per-domain policies; stores task state. This is the natural place to enforce rate-limit compliance and to attach immutable IDs to every “fetch” action for provenance. citeturn6search7turn6search10

**Browser workers (containerized, headless).** Execute browsing tasks: navigation, rendering, capture, and extraction. For untrusted sites, Playwright’s Docker guidance recommends launching browsers under a separate user and using a seccomp profile. citeturn0search3turn0search7

**LLM agents.**
- **Scout:** ranks candidate leads by impact heuristics and novelty signals; minimizes cost by operating on truncated context until a candidate passes thresholds.
- **Trace:** converts lead→atomic claims and locates root artifacts (DOI, preprint ID, dataset repo, standards body document, regulator notice).
- **Corroborator:** searches independent corroboration and synthesizes the packet, but only from captured evidence; WebGPT-style workflows explicitly require collecting references during browsing to support factual evaluation. citeturn3search0

### Content extraction as a first-class stage
Web pages are noisy; deterministic extraction improves downstream grounding. Mozilla’s Readability library is a commonly used approach (Firefox Reader View) and can be applied after capture to isolate main article text for claim extraction and evidence snippets. citeturn4search2turn4search6

## Evidence hierarchy, H/T scoring, and auditable evidence packets
A central design requirement is to prevent **pseudo-corroboration**: ten sources repeating one origin should count as one evidence family. The user-provided draft review flags this as a primary failure mode (“citation-collapse / lineage-collapse”). fileciteturn0file0

### Evidence tiers and automated checks
| Tier | Examples in STEM | What it can legitimately prove | Automated checks that strengthen T |
|---|---|---|---|
| Social lead (non-evidence) | posts, threads, screenshots | that a claim is circulating; not that it is true | deduplicate / cluster; extract atomic claims; identify link targets and timestamps citeturn2search1 |
| Mixed secondary | blogs, influencer summaries | at best: phrasing variants; often derivative | lineage collapse (shared URLs/quotes); require step-down to primary artifacts citeturn6search0 |
| Credible secondary | major science/tech outlets citing source | interpretation; context; sometimes expert quotes | verify cited DOI/preprint; check if coverage is independent or press-release-based citeturn2search2 |
| Primary scholarly artifact | journal article (DOI), conference paper, preprint | what authors claim + methods + results; not necessarily replicated | DOI validation + metadata via Crossref REST; check update-type/corrections; cross-link via scholarly graph citeturn0search0turn9search3turn1search3 |
| Preprint (explicitly uncertified) | arXiv / medRxiv preprints | preliminary claims; high update risk | flag “not peer reviewed”; downgrade T; schedule revisit; search for later journal version citeturn1search0turn1search1 |
| Post-publication updates | retraction, correction, expression of concern | that status changed; impacts reliance | Crossmark updates; Retraction Watch in Crossref API; update-type filters citeturn5search1turn9search23turn5search12 |
| Regulatory/standards artifacts | standards body docs, agency notices | official requirements, compliance, safety actions | verify issuer domain; capture PDF with hash; cross-check announcements across official channels citeturn3search1turn7search0 |
| Reproducibility artifacts | datasets, code, benchmarks | availability enabling partial reproduction | link integrity; release tags; hash archives; verify repository immutability where possible citeturn7search0turn3search2 |

### Scoring model: separate H and T axes
**T (truth/corroboration state)** should be treated as a *state machine* rather than a scalar, then mapped to a score for ranking. AVeriTeC and FEVER illustrate why: evidence quality and “not enough evidence” outcomes are first-class, and real-world verification needs evidence that existed at the time of the claim. citeturn2search2turn2search0

A practical T state set for STEM corroboration:
- **Untraced:** claim exists but root artifact not found.
- **Traced:** root artifact found and captured.
- **Source-consistent:** root artifact supports at least a weaker/conditional version.
- **Independently corroborated:** ≥2 independent evidence families align (e.g., separate lab replication, third-party benchmark, regulator confirmation).
- **Contested/conflicting:** credible contradiction or mixed evidence.
- **Superseded/retracted/corrected:** official update materially changes reliance.

Proof-of-implementation hooks exist in official scholarly metadata systems: Crossref’s REST API exposes license info and post-publication updates, and Crossmark is explicitly designed for corrections/retractions/update notices. citeturn0search0turn5search1

**H (impact)** should be computed from claim type + affected domain + magnitude + externalities (safety/health/economic stakes). Importantly, H is a prior on “how much you care,” not on “truth.” This separation is emphasized in the user-provided review as a way to avoid conceptual drift and miscalibration. fileciteturn0file0

### Weighting rules that reduce false positives
Weighting rules should privilege *traceability* and *independence* over volume:

- **Independence weighting:** additional sources only increase T if they form independent evidence families; RumourEval’s setting explicitly involves many posts about the same rumor, so “counting posts” is not verification. citeturn2search1
- **Preprint downgrade:** arXiv moderation is not peer review; medRxiv explicitly warns manuscripts are not certified by peer review and may contain errors. citeturn1search0turn1search1
- **Update overrides:** Crossmark and Retraction Watch signals should be treated as high-priority modifiers because they represent formal scholarly record changes and integrity reporting. citeturn5search1turn5search12
- **Grounded synthesis only:** any LLM-generated claim about the world must be linked to captured evidence (WebGPT’s “collect references while browsing” is a concrete model for this constraint). citeturn3search0

### Provenance and auditable evidence packets
An “evidence packet” should be a structured object that can be replayed and independently audited. W3C PROV-DM provides a domain-agnostic vocabulary for provenance (entities, activities, agents, derivations). citeturn3search2turn3search14

A minimum viable (but audit-grade) packet usually includes:
- Atomic claim text(s) + normalization metadata (units, scope, conditions).
- Lead metadata (platform/thread IDs, timestamps, canonical URLs).
- Root artifact identifiers (DOI, arXiv ID, etc.) and captured content.
- Evidence snippets with exact offsets into captured text.
- Independence graph (which sources derive from which origin).
- Update status checks (corrections/retractions) and results. citeturn9search3turn5search12
- Capture artifacts: HTML/PDF snapshots and/or WARC records; plus hashes and capture timestamps.

For replayable capture, WARC is a standard web-archiving container format that aggregates harvested resources plus metadata, supporting later access and exchange among archiving systems; it is widely documented by preservation authorities and standards bodies. citeturn7search0turn7search5

## Compliance risks, mitigations, evaluation, and ethics
### Compliance risks (ToS, robots.txt, rate limits)
Automation for ingestion and corroboration must be designed around platform rules:

- **X:** both the Help policy and developer guidelines explicitly warn that non‑API automation (e.g., scripting the website/browser automation) can lead to permanent suspension; rate-limit circumvention is also an explicit enforcement trigger. citeturn0search1turn0search5turn6search3
- **Reddit:** official Data API terms prohibit using user content to train ML/AI models without rightsholder permission and prohibit attempts to circumvent limitations; official help documentation specifies rate-limit headers and a free-access rate limit example (e.g., 100 QPM per OAuth client id). citeturn0search2turn6search10turn8search15
- **robots.txt:** RFC 9309 standardizes robots semantics and explicitly states robots rules are not access authorization and not a substitute for security controls. citeturn3search1

### Mitigation strategy
A durable pipeline generally uses:
- **API-first ingestion** for platforms with explicit anti-scraping posture (especially X). citeturn0search1turn8search2
- **Headless browsing primarily downstream** for open-web corroboration, not for platform ingestion; harden containers per Playwright’s guidance on untrusted sites (separate user + seccomp). citeturn0search3
- **Replayable evidence capture** (WARC or equivalent) so that every verdict can be reproduced even if pages change or disappear. citeturn7search0turn7search1
- **Policy registry per domain** (rate limits, allowed paths, retention rules) because this content drifts over time; the X and Reddit policy surfaces are explicitly versioned and updated. citeturn6search3turn6search10

### Security and operational notes
Web automation increases attack surface: malicious pages can exploit browser vulnerabilities or trick automation into downloading harmful content. Playwright’s Docker guidance for crawling on untrusted sites explicitly recommends a dedicated user plus seccomp confinement, which should be treated as baseline hardening. citeturn0search3

Operationally, anti-bot measures (e.g., CAPTCHAs) are common and should be treated as signals to (a) fall back to API/archives, (b) request human intervention, or (c) skip the domain—rather than to escalate evasion, which can violate ToS and increase risk. citeturn0search1turn3search1

### Human-in-the-loop checkpoints
Fact-checker research emphasizes that decision-making hinges on evidence quality, traceability of reasoning, and explicit uncertainty/gaps—requirements that map directly to a human review gate for high-impact or ambiguous cases. citeturn6search0turn6search4

A practical HITL design is to require manual sign-off when:
- H is above a threshold and T is not yet “independently corroborated,”
- the system detects “contested/conflicting evidence,”
- the claim depends on interpretation of a figure/table or a nuanced methodological caveat (high hallucination risk). citeturn4search0turn6search0

### Datasets, evaluation metrics, and testing plan
Benchmarks should test both **verdict accuracy** and **evidence quality**, because AVeriTeC-style real-world verification explicitly targets the limitations of datasets where evidence is artificial or temporally leaked. citeturn2search2turn2search0

| Evaluation target | Suggested metric(s) | Why it matters for this pipeline | Recommended datasets / sources |
|---|---|---|---|
| Claim-level corroboration state | macro-F1 over states; abstention accuracy; calibration (ECE) | discourages overconfident guesses; rewards “insufficient evidence” when appropriate | FEVER (Supported/Refuted/NEI). citeturn2search0 |
| Social rumor handling | veracity F1 + stance accuracy; time-to-correct-state | tests evolving rumor context and conversation structure | RumourEval (stance + veracity tasks). citeturn2search1 |
| Evidence retrieval quality | evidence recall/precision; “supported-with-evidence” accuracy | ensures the system can find and cite the right artifacts | FEVER evidence annotations; AVeriTeC evidence/Q-A structure. citeturn2search0turn2search2 |
| Trace-to-root artifact accuracy | % claims with correct root artifact ID (DOI/arXiv/etc.) | prevents “ten sources, one origin” pseudo-corroboration | AVeriTeC (real-world web evidence); internal gold sets built from captured packets. citeturn2search2 |
| Update sensitivity | retraction/correction detection rate; stale-verdict regression | validates that the system reacts to scholarly record changes | Crossmark + Retraction Watch in Crossref API; Retraction Watch database. citeturn5search1turn5search12turn5search0 |
| End-to-end auditability | % packets replayable; hash-verification pass rate | ensures evidence packets remain verifiable over time | WARC capture conformance; PROV completeness checks. citeturn7search0turn3search2 |

### Ethical considerations: privacy, PII, and copyright
Ethically and legally, a corroboration system should minimize retention of personal data from social platforms, and it should avoid republishing sensitive information. Platform policies explicitly highlight user privacy and compliance expectations, and platform/API terms may impose deletion/retention requirements. citeturn0search1turn6search3turn0search2

Copyright is a hard constraint for “evidence packets.” Even when using large archives, Common Crawl explicitly does not grant a license to the underlying page content; your system should store only what is necessary for auditing, respect rights, and consider storing cryptographic hashes + minimal excerpts rather than bulk redistribution. citeturn4search11turn4search3

Finally, hallucination risk is structural: LLMs can fabricate plausible but unsupported details. Surveys emphasize that mitigation often requires grounding, retrieval, and evaluation strategies rather than relying on the model alone—supporting an architecture where the LLM is constrained to cite captured evidence and to surface uncertainty. citeturn4search0turn4search1turn3search0