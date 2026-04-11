# Designing an LLM-Driven Corroboration Pipeline for High-Velocity STEM Claims

## Why this pipeline exists and what “corroboration” needs to mean
High-affinity dissemination platforms (forums and social feeds) behave like high-gain sensors: they surface weak, early signals fast, but they also amplify errors, misinterpretations, and outright falsehoods. Empirically, false news has been shown to diffuse farther/faster/deeper than true news on Twitter in a large-scale study of verified true/false stories, and the observed advantage is not explained away by bots alone. citeturn1search0turn1search12turn1search4turn1search16

A corroboration system, therefore, should **treat social posts as leads, not evidence**. In research terms, what you want is closer to *rumour verification* than classical “is this sentence true?” fact-checking: the system must track an evolving claim, follow citations backward to the originating artifact, and incorporate credible updates as the story develops. Shared-task research on rumour verification explicitly frames the problem this way (evolving conversations + news updates), and even expands datasets to include both Twitter and Reddit—directly aligned with your target environment. citeturn10view2

There’s also a practical ceiling: fully automated verification is still widely described as hard in real fact-checking workflows because many important claims cannot be resolved by a single lookup; they require nuance, judgment, and careful evidence handling. That said, fact-checkers consistently ask for automation help in upstream steps like deciding what to check and retrieving relevant evidence—exactly where an LLM-driven corroboration pipeline can provide leverage. citeturn10view0turn11search3

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["fact checking workflow diagram evidence retrieval","rumor verification pipeline stance evidence diagram","headless browser automation diagram playwright","data provenance graph W3C PROV diagram"],"num_per_query":1}

## Evidence hierarchy for STEM stories
To make “huge if true” operational, you need an explicit **evidence hierarchy** that matches how STEM claims become trustworthy. The key design choice: your pipeline should prefer *traceable primary artifacts* over “more chatter.” This is not optional; it’s what turns an attention stream into a corroboration system.

A robust baseline is to structure evidence into tiers:

| Evidence tier | What it is | Why it matters for corroboration | How the pipeline should use it |
|---|---|---|---|
| Primary artifacts | Peer-reviewed papers; preprints; datasets; code; patents/standards; official institutional statements | These are closest to the underlying work and usually include methods, data, or formal accountability | Trace to these first; extract the exact claim supported; record provenance and versioning |
| Credible secondary coverage | Reputable science/tech reporting that cites primary artifacts and adds interpretation | Helps detect misreadings, missing caveats, and external validation | Use as context and triangulation, not as the root of truth |
| Mixed-credibility secondary coverage | Blogs/aggregators with uneven sourcing; influencer summaries | High volume, high variance | Use only to discover leads and alternative phrasings; require step-down to primary artifacts |
| Social dissemination | Posts, threads, quote-tweets, comment chains | Fastest signal; weakest epistemically | Use for detection + claim clustering + “what exactly is being asserted?” |

For STEM specifically, **preprint handling** is crucial. Major preprint servers explicitly note that manuscripts are not certified by peer review and may contain errors; in medicine they often add stronger warnings about not guiding clinical practice. citeturn3search2turn3search6turn3search28turn4search1  
That means your “truth” scoring must be able to produce outcomes like *plausible but unverified* (and still “huge if true”), rather than forcing a binary verdict.

To automate the “trace to primary” step at scale, scholarly metadata infrastructure is extremely useful. **entity["organization","Crossref","doi registration agency"]**’s REST API exposes DOI metadata deposited by publishers and trusted sources, including license information and post-publication updates; it also points to complementary sources such as **entity["organization","Retraction Watch","retraction tracking site"]**. citeturn5view2turn1search7  
This matters because your corroboration pipeline should check not only “is there a paper?” but also “has it been corrected, retracted, or superseded?”

Finally, don’t ignore the “already checked” ecosystem. Structured fact-check markup exists via **entity["organization","Schema.org","structured data initiative"]**’s ClaimReview type, and fact-check search tooling uses that ecosystem even as support shifts in general web search products. citeturn5view3turn3search7turn3search3turn3search23  
This won’t solve frontier STEM claims (often too new), but it can short-circuit recycled hoaxes and “this is back again” narratives.

## LLM-driven discovery and browsing architecture
You want the LLM to do more than a “final check”: you want it to **drive the browsing, tracing, and corroboration**. The right mental model is *agentic retrieval with hard grounding*.

Research and practice strongly support the idea of LLMs alternating between reasoning and tool use (search/navigation actions) rather than operating as a closed-box summarizer. Agent frameworks like ReAct formalize interleaving reasoning traces with actions, and browser-assisted QA work (e.g., WebGPT) highlights that requiring references/evidence improves human evaluation of factual accuracy. citeturn7search0turn7search2  
At the same time, hallucination (fabricated details or overconfident synthesis) is a known failure mode; recent surveys emphasize mitigation and evaluation strategies rather than assuming it away. citeturn7search11turn7search3turn7search15

A high-level architecture that fits your “desktop-driven agents in containers” intention:

**Orchestrator (scheduler + queue):**  
Runs periodic jobs per category (science/tech/engineering/math), triggers “lead intake” for each platform/channel, and enforces budgets (time, pages visited, network domain allowlists).

**Browser workers (containerized headless sessions):**  
Use headless browser automation for site navigation, rendering JS-heavy pages, and capturing the exact text the model is allowed to reason over. Playwright is explicitly designed for running in Docker, and its official guidance calls out security choices (e.g., avoid running as root/sandbox disabled; use separate users and hardening when crawling). citeturn5view0turn5view1  
Notably, Playwright’s own Docker documentation warns the image is intended for testing/development and is not recommended for visiting untrusted websites—this is a concrete operational risk you must design around (sandboxing, egress rules, strict download handling). citeturn5view0

**LLM agent (policy + controller):**  
Given a lead, it decides:
- what query to run,
- which result to open,
- what counts as “the originating artifact,”
- what additional independent sources are required,
- when to stop and emit a report with explicit uncertainty.

**Extractor + ground-truth store:**  
Everything the LLM concludes must be traceable to captured artifacts: HTML snapshots, extracted text, PDFs (with hashes), timestamps, and canonical URLs/DOIs. This is where you prevent “I read it somewhere” drift.

In short: LLMs can be the *pilot*, but your system must be built so the pilot can only fly using instrument panels you record.

## Corroboration workflow from social lead to evidence packet
Your intent (“start with the linked article; then journals/industry info; then credible coverage”) maps cleanly to a deterministic corroboration loop. A strong baseline is to implement it as a **trace-first, broaden-second** procedure:

**Lead normalization and claim extraction**  
The agent converts a post/thread into one or more *atomic claims* (e.g., “Group X achieved Y metric under Z conditions,” not “Breakthrough!”). This aligns with automated fact-checking pipelines that separate claim identification from evidence retrieval and verdicting. citeturn11search3turn11search0

**Trace to the originating artifact**  
If the post links to an article, the agent opens it and extracts:
- the *core assertion(s)*,
- the cited source(s): DOI, preprint link, dataset URL, press release, standards doc, etc.,
- whether the article is itself a rewrite of another piece.

This “trace to original context” is also the core of practical lateral reading frameworks such as SIFT (Stop, Investigate the source, Find better coverage, Trace claims). citeturn11search11turn11search1

**Primary-source verification pass**  
Once a primary source is identified, the agent checks:
- what the primary source *actually claims* (pull exact abstract/claims; capture figures/tables if needed),
- publication status (preprint vs peer-reviewed),
- versioning and post-publication signals.

For preprints: use explicit server disclaimers to downgrade certainty unless there is additional corroboration. citeturn3search2turn3search28turn4search1  
For published work: DOI metadata infrastructure can help validate bibliographic reality and detect updates/corrections. citeturn5view2turn1search3turn1search7

**Independent corroboration search**  
Only after the primary source is pinned does the agent broaden outward. Here, “independent corroboration” should mean at least one of:
- another lab/group reporting similar results (rare early; high value),
- a credible secondary analysis referencing the same primary artifact,
- an official statement from a relevant institution,
- data/code artifacts enabling partial reproduction (field-dependent).

Rumour verification research emphasizes incorporating “news updates” and evolving context over time; operationally, this suggests your agent should revisit high-impact claims on a schedule (e.g., 24h/72h/1w) to catch corrections and follow-on reporting. citeturn10view2turn10view0

**Evidence packet assembly**  
Instead of outputting “true/false,” the pipeline outputs a packet:
- atomic claim(s),
- provenance chain (post → linked article → primary source → independent coverage),
- extracted supporting/refuting snippets with citations,
- computed scores (huge/true/confidence),
- explicit gaps (“no primary source found,” “only one outlet repeating press release,” etc.).

This packet concept is not just UX—it’s how you keep the system auditable and improve it over time.

## Scoring “huge” and “true” without fooling yourself
Your framing implies two orthogonal dimensions:
- **H (hugeness / impact)**: “If verified, would this materially change an area of STEM, enable major capability, or shift accepted limits?”
- **T (truth / evidential support)**: “Given current evidence, how supported is the claim?”

A pragmatic baseline is to compute **separate scores** and only report items that clear thresholds (e.g., H high and T above a minimum), while still allowing a “H high / T low” queue for watchlisting.

For the *truth* side, the automated fact-checking literature commonly uses multi-class outcomes such as supported/refuted/insufficient information, exemplified by FEVER’s supported/refuted/not-enough-info framing. citeturn1search1turn1search13  
That tri-state structure is especially appropriate for frontier STEM, where “not enough info yet” is often the honest answer.

For the *process quality* side, you should weight:
- **evidence tier** (primary > secondary > social),
- **independence** (distinct sources vs copies),
- **specificity** (quantified claims with conditions > vague hype),
- **replicability hooks** (data/code/method detail),
- **update sensitivity** (retractions/corrections materially change T).

On explainability: studies of fact-checkers’ requirements stress that evidence assessment and primary evidence matter, and that explanations should reference specific evidence and surface uncertainty and information gaps—reinforcing the “evidence packet” approach. citeturn11search5turn9search3

A strong opinionated guardrail: **if your system can’t show the primary artifact and the exact sentence/figure that allegedly supports the claim, it should not label it “true.”** It can label it “unverified (but potentially huge).”

## Operational constraints, platform policies, and provenance discipline
Your preferred mechanics (“LLM-driven headless browsing in containers”) collide with a reality: some platforms explicitly prohibit non-API automation.

**X (Twitter/X) constraints**  
X’s developer guidance is unusually direct: non-API automation (scraping, browser automation, scripting the website) is described as leading to permanent suspension, and X Help likewise warns that non-API automation techniques (e.g., scripting the X website) may result in permanent suspension. citeturn2view0turn2view1  
If you want durability, ingestion from X should be designed around official/authorized access patterns, with the LLM still controlling *what to look for* and *how to corroborate it elsewhere*, rather than driving a headless browser against X itself.

**Reddit constraints**  
Reddit’s Data API Terms reserve broad discretion to impose and enforce API limits, restrict abusive usage/circumvention, and potentially charge for use beyond permitted rate limits or commercial/research use cases; Reddit communications around API changes include explicit free-tier rate limits (e.g., queries per minute) and paid tiers. citeturn2view2turn2view3  
Net: for Reddit, an API-first intake strategy is usually more stable than browsing automation, while headless browsing remains useful downstream for external web sources.

**Robots.txt and site access expectations**  
Even when automation is technically possible, the web’s Robots Exclusion Protocol (RFC 9309) defines crawler-facing rules and explicitly notes these rules are *not* access authorization. citeturn8search3turn8search11  
In practice: you still need to comply with site Terms, rate limits, and legal constraints (plus your own ethical/privacy standards), not just robots.txt.

**Provenance as a first-class requirement**  
To make your system correctable and trustworthy, provenance must be captured in a structured way. The W3C provenance model (PROV-DM) defines provenance as information about entities/activities/people involved in producing data, used to assess quality/reliability/trustworthiness—exactly your use case. citeturn8search0turn8search4  
This is the backbone that enables:
- reproducible reruns (“what did the agent see on April 10, 2026?”),
- regression testing of scoring changes,
- post-mortems when the system is wrong,
- human trust (you can inspect the chain).

**Optional: reducing live crawling surface area**  
If you want to minimize live browsing risk and ToS friction for the *open web*, datasets like entity["organization","Common Crawl Foundation","web crawl nonprofit, us"] provide large-scale crawled data under published terms—useful for some corroboration tasks, though it won’t solve “today’s breaking story” and doesn’t grant rights to the underlying page contents. citeturn8search2turn8search6

The takeaway is blunt but important: **LLM-driven browsing is powerful, but durability depends on aligning “how you fetch” with platform rules, and aligning “what you claim” with provenance-backed evidence packets.**