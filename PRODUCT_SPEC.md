# Lease Review Tool Prototype Specification

Date: 2026-04-03

Status: Refined draft for implementation alignment

## 1. Product Summary

This project is a backend-first AI-powered lease review gadget focused on residential California leases.

The system will:

- ingest a small reference knowledge base of lease templates,
- convert those reference documents into a searchable and analyzable clause-level knowledge base,
- analyze a user-provided lease against that knowledge base,
- return structured observations about unusual or potentially important clauses,
- support UI highlighting by returning the relevant clause text and page number.

The prototype is intentionally backend-focused. Frontend design is out of scope for now.

Note: Frontend requirements will be defined later and are subject to change.

## 2. Core Product Behavior

### 2.1 LLM Interaction Model

The end user will not directly chat with the LLM.

The LLM is an internal analysis engine only. It must produce structured outputs to:

- identify unusual patterns,
- break down the contract internally,
- generate observations tied to specific clauses,
- support knowledge-base population,
- support debugging and tuning.

The LLM should not be exposed as an open-ended conversational assistant in this prototype.

### 2.2 User-Facing Experience

The user-facing experience should focus on flagged items only, not a full clause-by-clause walkthrough.

The intended UX is:

- highlight problematic or notable clauses in the original document,
- show the original clause text,
- show the AI-generated observation beside it,
- avoid making the user read an exhaustive legal breakdown.

Note: The choice to show flagged items only is a prototype scope decision and may change later.

### 2.3 Recommendation Policy

The system should make observations only.

It should not make negotiation advice, legal recommendations, or action recommendations at this stage.

Examples of acceptable output:

- "This late-fee clause appears more aggressive than the small California reference set."
- "This clause contains an unusual repair obligation shift."

Examples of unacceptable output for this prototype:

- "You should negotiate this clause."
- "You should not sign this lease."

Note: Recommendation behavior is intentionally disabled at this stage and may change later.

## 3. Prototype Scope

### 3.1 Lease Type

The prototype is limited to residential leases only.

### 3.2 Jurisdiction

The prototype is limited to California only.

### 3.3 Input Formats

The prototype must support:

- PDF
- DOCX

Assume early inputs are digitally readable and well-formed.

Do not prioritize OCR or messy document recovery in this phase.

Note: Additional file types and OCR support may be added later.

### 3.4 Reference Knowledge Base Size

At the very beginning, the knowledge base will contain only 2 lease templates.

This is acceptable for the prototype even though it limits the strength of baseline comparisons.

The system must be designed to ingest additional reference files later without wiping the database or rebuilding the project from scratch.

Note: The initial reference set size is temporary and will expand later.

### 3.5 Temporary Interpretation of "Unusual"

Because the prototype starts with only 2 reference templates, "unusual" will initially mean "different from the current known reference set" rather than "statistically rare across a robust market-wide benchmark."

This limitation should be reflected in system design and internal reasoning.

Note: This interpretation is expected to evolve later as the corpus grows.

## 4. High-Level System Stages

The prototype should be organized into separate backend stages so ingestion and analysis can be run independently.

### 4.1 Stage A: Ingestion and Knowledge-Base Population

This stage should:

- read reference lease files,
- parse and segment them into clauses,
- classify and normalize clauses,
- extract structured fields,
- generate embeddings,
- generate human-readable rule/red-flag artifacts,
- store all queryable knowledge-base records,
- recompute baselines automatically after new reference material is added.

Ingestion and knowledge-base population may be implemented as a single stage in the prototype.

### 4.2 Stage B: Lease Analysis and Flag Generation

This stage should:

- accept a user lease,
- parse and segment it,
- analyze it against the current knowledge base,
- produce structured flagged observations,
- return only the top 10 strongest observations,
- include enough information for future UI highlighting and debugging.

Lease analysis and flag generation may be implemented as a single stage in the prototype.

## 5. Knowledge Base Design

### 5.1 KB Philosophy

The knowledge base must combine three layers:

- semantic retrieval,
- structured extracted fields,
- comparative logic for unusualness detection.

The product should not rely on a generic "dump everything into RAG" approach.

### 5.2 Clause-Level Storage

The knowledge base should be built around clauses, not whole leases.

Each reference lease should be segmented into clause-like units that can be independently:

- classified,
- embedded,
- compared,
- flagged,
- cited later in analysis.

### 5.3 Clause Taxonomy

There is no pre-existing clause taxonomy.

The prototype should start with a practical high-value taxonomy including categories such as:

- late fees
- security deposit
- entry rights
- repair obligations
- utilities
- subletting
- early termination
- auto-renewal
- attorney fees
- arbitration
- default and remedies
- rent escalation
- move-out charges
- notice requirements
- guest limits
- pet restrictions

Note: The taxonomy is intentionally provisional and may change later.

### 5.4 Metadata Policy

For the prototype, do not rely heavily on rich metadata.

The system should largely ignore advanced metadata dimensions for now beyond what is minimally necessary to support the California residential prototype.

Examples of metadata to defer:

- property type
- lease year
- landlord/template family
- advanced jurisdiction breakdowns

Note: Rich metadata may be added later.

### 5.5 Embeddings

Each clause in the reference knowledge base should have an embedding.

Embeddings exist to support:

- semantic similarity retrieval,
- comparison against conceptually similar clauses even when wording differs,
- weak anomaly detection against the small reference set,
- future clustering and deduplication.

Embeddings should represent clause text or a normalized clause representation, not summary statistics.

### 5.6 Normalized Clause Summaries

The knowledge base should store both:

- raw clause text,
- an LLM-written normalized summary or normalized text representation for each reference clause.

Reason:

- raw text is required for auditability and citation,
- normalized text helps semantic consistency,
- normalized summaries help internal comparison and debugging.

### 5.7 Structured Fields

The knowledge base should store structured extracted fields per clause where applicable.

Examples:

- late fee percentage
- grace period days
- fixed fee amount
- notice period
- renewal window
- repair obligation direction
- deposit amount

Structured fields are required for parameter-based anomaly detection and downstream debugging.

### 5.8 Baseline and Benchmark Recalculation

When new reference leases are ingested, the system should update incrementally and automatically recompute corpus baselines in a smart way.

Desired behavior:

- do not wipe the database,
- do not require a fresh start,
- preserve prior ingested records,
- recalculate relevant comparison artifacts after each incremental KB expansion.

### 5.9 Human-Readable Rule Artifacts

Rule-based red flags should exist in the system even though no lawyer-authored rulebook is available initially.

For the prototype, these rule-like artifacts should be generated during knowledge-base population with LLM assistance and saved in explicit human-readable form.

These artifacts should be inspectable by humans for debugging and tuning.

Examples:

- "Late fee above small-reference median plus tolerance"
- "Broad repair burden shifted to tenant"
- "Entry rights language lacks expected notice wording"

## 6. Analysis Logic

### 6.1 Definition of Flagging Logic

The prototype should use a combination of:

- semantic anomaly detection,
- numeric or parameter anomaly detection,
- LLM-generated rule-based red flags.

The system should not rely on only one of these methods.

### 6.2 Internal Reasoning Visibility

Internal reasoning categories should be surfaced in prototype outputs for debugging and tuning.

Examples:

- semantic anomaly
- parameter anomaly
- rule-derived red flag

Note: This debug visibility is useful at the current stage and may change later.

### 6.3 No Full Contract Breakdown

The analysis result should not return a complete clause-by-clause contract explanation.

Only notable flagged observations should be returned.

Note: This is a prototype UX constraint and may change later.

### 6.4 Observation Count

The prototype should return up to the top 10 strongest observations for a lease.

However, the system should not expose a severity ranking to the user at this stage.

Practical implication:

- the backend may internally choose the strongest 10,
- the returned set does not need user-facing severity labels,
- the future UI may display them in document order rather than ranked order.

## 7. Output Schema

The current target output schema for each flagged item is:

- `title`
- `observation`
- `why_flagged`
- `flag_type`
- `confidence`
- `clause_text`
- `page`
- `source_span`

Additional internal fields may be included if useful for debugging, such as:

- `reasoning_type`
- `matched_reference_clauses`
- `comparison_notes`

Note: The output schema is expected to evolve later. Fields may be added or removed.

### 7.1 Required Output Characteristics

Each flagged result should:

- include the clause text,
- include the page number,
- be tied to a specific clause,
- be usable for future UI-side highlighting,
- be observation-only,
- be understandable without showing every clause in the lease.

### 7.2 Source Span Precision

For now, clause text plus page number is enough.

Do not require precise PDF coordinates, bounding boxes, or character offsets in the prototype.

Note: More precise location data may be added later.

## 8. Storage and Persistence

### 8.1 Core Database Choice

Use PostgreSQL as the central data store.

The queryable knowledge base should live in Postgres and include:

- leases metadata for reference documents,
- clause records,
- embeddings,
- structured fields,
- generated rule artifacts,
- benchmark/baseline artifacts.

### 8.2 Vector Support

Use `pgvector` in Postgres for embedding storage and retrieval.

This keeps semantic retrieval and structured querying in one place and aligns well with later AWS deployment.

### 8.3 Reference Source Files

Reference source documents may live on the local filesystem during early development, with file paths stored in the database.

### 8.4 User-Uploaded Lease Storage

Do not permanently store user-uploaded analysis leases in the prototype.

Treat them as transient analysis inputs.

Note: User lease storage may be revisited later.

## 9. LLM and Model Strategy

### 9.1 Provider Direction

Use the ChatGPT/OpenAI model suite for the prototype.

The user will provide API keys later.

### 9.2 Cascade Requirement

The backend should use a cascade structure to save cost.

The intended pattern is:

- cheaper model passes for extraction, normalization, and most structured generation,
- stronger model passes only when deeper reasoning is needed.

### 9.3 Structured Outputs First

The model pipeline should produce structured outputs first and natural-language phrasing second.

The system should prioritize reliable machine-readable intermediate outputs over polished prose.

### 9.4 No Direct User Chat

The backend must not be designed as an open-ended chat interface.

All LLM outputs should be task-bounded and structured.

## 10. Local-First Development Requirements

### 10.1 Local Development Mode

Initial development should remain local-first:

- local PostgreSQL,
- local Python backend,
- local scripts and services,
- remote LLM API calls.

### 10.2 Incremental KB Updates

The ingestion pipeline must support incremental knowledge-base expansion without wiping prior data.

This is a hard requirement.

### 10.3 AWS Alignment

Technology choices should favor simplicity now and an easy AWS migration path later.

The backend should be designed so that a later transition to services such as:

- RDS for PostgreSQL,
- S3 for documents,
- ECS or EC2 for services,
- Secrets Manager for credentials

requires minimal application-level redesign.

## 11. Chosen Technical Direction for the Backend

These are the current engineering choices to guide implementation unless changed later:

- Language: Python
- Web/API framework: FastAPI
- Validation/schema layer: Pydantic
- ORM/database toolkit: SQLAlchemy
- Migrations: Alembic
- Database: PostgreSQL
- Vector extension: pgvector
- Local document storage: filesystem
- Stage execution: explicit ingestion command and explicit analysis command

Reason for these choices:

- simple local development,
- common production patterns,
- strong AWS compatibility,
- clear typing and API contracts,
- good support for staged pipelines.

## 12. Evaluation and Human Review

Formal evaluation is not required yet.

The user will manually judge output quality during the prototype phase.

There is no human-in-the-loop approval step in the product flow.

Note: Evaluation strategy may be formalized later.

## 13. Out of Scope for the Prototype

The following are out of scope for now:

- frontend implementation,
- chat-style user interaction with the LLM,
- lawyer-authored formal rules engine,
- OCR-heavy document recovery,
- robust multi-state support,
- commercial lease support,
- long-term storage of user-uploaded leases,
- fine-grained PDF bounding-box extraction,
- recommendation generation,
- full contract clause-by-clause walkthroughs.

## 14. Summary of Explicitly Flexible Requirements

The following items were explicitly identified as likely to change later:

- frontend requirements,
- flagged-output-only UX,
- recommendation policy,
- supported file handling depth beyond clean PDF and DOCX,
- initial 2-template knowledge-base size,
- meaning of "unusual" as the corpus expands,
- clause taxonomy,
- richer metadata support,
- debug visibility of internal reasoning,
- output schema fields,
- source-location precision beyond page number,
- storage policy for user-uploaded leases,
- formal evaluation strategy.

## 15. Immediate Build Implications

Before any implementation work starts, the system should be treated as a backend with:

- a persistent reference knowledge base,
- staged ingestion and analysis flows,
- clause-level storage and retrieval,
- structured LLM outputs,
- human-readable rule artifacts,
- transient user-lease analysis,
- top-10 flagged observation output,
- no frontend dependency,
- no user-to-LLM direct conversation.

## 16. Product Assumptions and Known Limitations

### 16.1 Small-Corpus Limitation

The prototype begins with only 2 reference lease templates.

This means:

- baseline statistics will be weak,
- "commonness" will be approximate,
- anomaly detection will be more heuristic than authoritative,
- some strong outputs may come more from semantic comparison and generated rule artifacts than from true distributional confidence.

This limitation is acceptable for the prototype and should be made visible in internal design discussions.

Note: This limitation should weaken naturally as the reference corpus grows later.

### 16.2 Confidence Interpretation

Any `confidence` field returned by the prototype should be treated as an internal heuristic signal, not a calibrated probability and not a legal-confidence metric.

It is acceptable for confidence to reflect a blended backend estimate based on factors such as:

- extraction confidence,
- retrieval consistency,
- agreement between analysis methods,
- clarity of clause language,
- strength of anomaly signals.

Note: Confidence semantics are likely to change later.

### 16.3 Legal Reliability Limitation

The current prototype is meant to surface sharp observations, not to certify legal correctness.

The working quality target is:

- approximate the kinds of issues a strong lease lawyer might notice,
- expose those issues with traceable evidence,
- make the output useful enough for iterative tuning.

There is no promise at this stage that the system is legally complete or legally sufficient.

### 16.4 Rule-Bootstrapping Limitation

Because no lawyer-authored rulebook exists yet, the initial rule-based red flags will be LLM-assisted and corpus-derived.

This means they should be treated as:

- inspectable heuristics,
- tunable artifacts,
- a bootstrap mechanism,
- not immutable legal rules.

Note: This rule strategy may change later if lawyer-authored guidance becomes available.

## 17. End-to-End Workflow Specification

### 17.1 Reference Ingestion Workflow

The ingestion workflow should conceptually proceed as follows:

1. Accept a reference lease file from a configured local source.
2. Compute a stable document fingerprint so the system can detect re-ingestion and support idempotency.
3. Parse the source document into text.
4. Segment the document into clause-level units.
5. Classify each clause into the current taxonomy.
6. Extract structured fields from each clause.
7. Generate normalized clause summaries or normalized embedding text.
8. Generate embeddings for the clause representation.
9. Generate human-readable rule/red-flag artifacts using the current corpus.
10. Persist reference documents, clauses, fields, embeddings, artifacts, and run metadata.
11. Recompute benchmark and baseline artifacts for affected clause types.

### 17.2 Lease Analysis Workflow

The lease-analysis workflow should conceptually proceed as follows:

1. Accept a user lease as a transient analysis input.
2. Parse the file into text.
3. Segment the lease into clause-level units.
4. Classify the clauses.
5. Extract structured fields and normalized representations.
6. Retrieve semantically and structurally relevant reference clauses from the knowledge base.
7. Compare uploaded clauses against corpus artifacts and rules.
8. Generate candidate flags.
9. Deduplicate or consolidate overlapping candidate flags.
10. Select the strongest 10 observations.
11. Return a structured analysis response without permanently storing the uploaded lease.

### 17.3 Reference vs Analysis Data Separation

The backend must keep a clear distinction between:

- persistent reference knowledge-base data,
- transient user-lease analysis data.

Reference knowledge-base data should be durable and reusable.

User analysis input should be processed ephemerally in this prototype.

This separation is a hard architectural requirement.

## 18. Ingestion Requirements in More Detail

### 18.1 Idempotency

The ingestion pipeline must be idempotent for the same source file.

If the same reference document is ingested twice without changes, the system should avoid creating duplicate reference records.

Recommended design behavior:

- fingerprint the source file,
- track ingestion runs,
- detect previously ingested document versions,
- support safe reprocessing when the document content or pipeline version changes.

### 18.2 Incremental Updates

The ingestion pipeline must support incremental addition of new reference documents.

Adding a new reference lease should:

- preserve all existing reference records,
- preserve all existing embeddings unless re-embedding is explicitly required,
- trigger recalculation of relevant benchmark artifacts,
- not require a database reset.

### 18.3 Version Tracking

The system should track which pipeline version produced each artifact where feasible.

Examples of versioned components:

- extraction prompt version,
- clause taxonomy version,
- embedding model version,
- analysis prompt version,
- rule-artifact generation version.

This is important for traceability and future reprocessing.

### 18.4 Partial Failure Handling

The ingestion system should tolerate partial failure.

For example:

- a document may parse successfully but fail field extraction,
- embeddings may fail while classification succeeds,
- benchmark recomputation may fail after clause persistence succeeds.

The spec should therefore assume run-status tracking such as:

- pending
- processing
- completed
- failed
- partially_completed

Note: Exact status names may change later.

### 18.5 Reprocessing Policy

The system should support reprocessing of existing reference documents without wiping the database.

Examples:

- re-run extraction with a better prompt,
- regenerate embeddings with a new embedding model,
- regenerate rule artifacts after the corpus expands.

Reprocessing should be explicit and controlled, not accidental.

## 19. Analysis Requirements in More Detail

### 19.1 Hybrid Retrieval

Analysis should use hybrid retrieval wherever practical.

At minimum, the system should be designed to combine:

- semantic retrieval from embeddings,
- structured comparison using extracted fields,
- current rule-artifact checks.

Keyword or full-text retrieval should remain available as a useful secondary mechanism if implementation supports it early.

### 19.2 Candidate Flag Consolidation

The system should avoid flooding the output with duplicative flags.

If multiple methods detect the same issue on the same clause, the backend should consolidate them into a single flagged observation when that is clearer.

Examples:

- semantic anomaly plus parameter anomaly on the same late-fee clause,
- multiple overlapping rule triggers describing the same tenant-risk pattern.

### 19.3 Observation Selection Policy

The backend may internally score candidate observations to choose the top 10 strongest items.

However:

- the user-facing result should not present an explicit severity ranking,
- the internal selection logic may be heuristic,
- the final presentation order may be document order or another stable order.

Note: Internal selection logic and ordering are subject to change later.

### 19.4 Clause-Level Anchoring

Every returned observation must anchor to a specific clause.

At minimum, each observation must be traceable to:

- a clause text snippet,
- a page number,
- a source span identifier or equivalent logical span.

### 19.5 Explanation Quality Bar

Each returned observation should be understandable and concrete.

Avoid vague language such as:

- "This clause seems bad."
- "This section may be unusual."

Prefer grounded phrasing such as:

- "This late-fee clause requires payment after a shorter grace period than the current California residential reference set."
- "This repair clause shifts more responsibility to the tenant than similar clauses currently in the knowledge base."

## 20. Data and Artifact Model

### 20.1 Persistent Reference Entities

The persistent knowledge base should conceptually include entities like:

- `reference_documents`
- `reference_clauses`
- `clause_fields`
- `benchmark_profiles`
- `generated_rule_artifacts`
- `ingestion_runs`

Embeddings may live directly on `reference_clauses` or in a tightly related table.

### 20.2 Reference Document Record Expectations

A reference document record should conceptually support fields such as:

- document id,
- source file path,
- file fingerprint,
- source type,
- ingestion status,
- parse status,
- created timestamp,
- updated timestamp.

Note: Exact schema details may change later.

### 20.3 Reference Clause Record Expectations

A reference clause record should conceptually support fields such as:

- clause id,
- document id,
- clause index or clause order,
- page number or page range,
- clause type,
- raw clause text,
- normalized clause text or summary,
- extracted fields payload,
- embedding vector,
- pipeline version metadata.

### 20.4 Benchmark Profile Expectations

A benchmark profile should conceptually describe current corpus expectations for a clause type or clause subgroup.

Examples:

- common variable ranges,
- median values,
- percentile estimates,
- representative wording patterns,
- current corpus size used to build the profile.

### 20.5 Rule Artifact Expectations

A generated rule artifact should be human-readable and inspectable.

It should ideally capture:

- rule id,
- clause type,
- short name,
- natural-language description,
- trigger logic summary,
- rationale,
- counterexample notes if available,
- model version,
- corpus size used when generated.

Note: Rule artifact format is subject to change later.

### 20.6 On-Disk Artifact Guidance

The local project should eventually maintain a clean artifact structure for development convenience.

A reasonable direction is:

- raw reference files,
- parsed text artifacts,
- extracted JSON artifacts,
- generated rule-artifact files,
- batch or processing logs.

The exact directory layout is not yet fixed.

Note: The local artifact layout is subject to change later.

## 21. Output Contract Refinement

### 21.1 Response Envelope

The final analysis response should not just be a bare array of flags.

It should conceptually include an envelope with fields such as:

- analysis timestamp,
- analysis mode,
- knowledge-base snapshot or version reference,
- limitations note,
- flagged observations array.

This will help debugging and future UI integration.

### 21.2 Flag Item Contract

Each flagged observation should conceptually include:

- `title`
- `observation`
- `why_flagged`
- `flag_type`
- `confidence`
- `clause_text`
- `page`
- `source_span`

Recommended optional fields for debugging:

- `reasoning_type`
- `matched_reference_clauses`
- `comparison_notes`
- `rule_artifact_ids`

### 21.3 Example Response Shape

```json
{
  "analysis_mode": "prototype_structured_observations",
  "kb_snapshot": "kb_v1",
  "limitations_note": "Prototype built on a small California residential reference set.",
  "flags": [
    {
      "title": "Aggressive late-fee clause",
      "observation": "This clause imposes a shorter grace period and a higher fee than the current small reference set.",
      "why_flagged": "Detected by parameter comparison and reinforced by semantic mismatch from the closest reference clauses.",
      "flag_type": "late_fee",
      "confidence": 0.78,
      "clause_text": "If rent is not received within 3 days, tenant shall pay an 8% late fee...",
      "page": 4,
      "source_span": "clause_12",
      "reasoning_type": [
        "parameter_anomaly",
        "semantic_anomaly"
      ]
    }
  ]
}
```

Note: Example response shape is illustrative and subject to change later.

## 22. Operational and Configuration Guidance

### 22.1 Local Runtime Expectations

The local development environment should expect configuration values such as:

- database connection URL,
- OpenAI API key,
- chosen extraction model,
- chosen reasoning model,
- chosen embedding model,
- reference document directory path.

Exact environment variable names do not need to be finalized in this spec.

### 22.2 Explicit Stage Execution

The prototype should be operable in explicit stages rather than one opaque command.

At minimum, implementation should support the concept of:

- running reference ingestion independently,
- running lease analysis independently.

This is required so knowledge-base population and lease analysis can be developed and debugged separately.

### 22.3 Background Processing Expectations

The initial prototype does not need a complex distributed job system.

A local synchronous or lightly staged approach is acceptable so long as the design leaves room for later migration to:

- background jobs,
- queues,
- containerized services,
- scheduled refresh tasks.

Note: Processing architecture may change later.

## 23. MVP Acceptance Criteria

The refined spec should be considered satisfied in an initial backend build if the system can do all of the following:

1. Ingest 2 California residential reference leases from local files.
2. Re-run ingestion safely without creating duplicate reference records for unchanged source files.
3. Add another reference document later without wiping the database.
4. Recompute benchmark and rule artifacts after incremental KB expansion.
5. Analyze a transient user lease without permanently storing that lease.
6. Return no more than 10 flagged observations.
7. Include clause text and page number for every returned observation.
8. Expose internal reasoning categories for debugging.
9. Keep the product observation-only rather than recommendation-driven.
10. Keep ingestion and analysis as separable stages.

## 24. Refinement Outcome

This refined spec should now be treated as the working contract for backend implementation planning.

It is more specific than the original draft in the following ways:

- clarifies persistent vs transient data boundaries,
- defines idempotent and incremental ingestion behavior,
- defines reprocessing and version-tracking expectations,
- defines candidate-flag consolidation expectations,
- defines a response envelope rather than only per-flag fields,
- defines acceptance criteria for the MVP.
