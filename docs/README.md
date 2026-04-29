# Documentation Map

This directory contains the planning and reference documents for `dj-panel-backend`.

The documents are intentionally split by concern. The most common source of confusion
was that several files were all describing "the system", but from different levels:

- long-term architecture
- V1 product shape
- database target model
- API contract
- worker execution contract
- current implementation status

This file is the boundary map for those documents.

## Reading Order

If you are new to the project, read in this order:

1. [CURRENT_PROJECT.md](./CURRENT_PROJECT.md)
   Start here for what the backend currently is, what it already implements, and how to run it.
2. [TARGET_ARCHITECTURE.md](./TARGET_ARCHITECTURE.md)
   Read this next for the long-term architectural direction.
3. [DJ_PROCESSING_V1_DESIGN.md](./DJ_PROCESSING_V1_DESIGN.md)
   Read this for the scoped V1 Data-Juicer product design.
4. [CLI_REFERENCE.md](./CLI_REFERENCE.md)
   Use this when working on `dj-panel` commands, CLI defaults, or operator workflows.
5. [V1_API_OPENAPI_STYLE.md](./V1_API_OPENAPI_STYLE.md)
   Use this when working on frontend-backend contracts or CLI-facing resource shapes.
6. [DATABASE_SCHEMA_DRAFT.md](./DATABASE_SCHEMA_DRAFT.md)
   Use this when changing persistence or reasoning about data ownership.
7. [DJ_WORKER_PAYLOAD_AND_SEQUENCE.md](./DJ_WORKER_PAYLOAD_AND_SEQUENCE.md)
   Use this when changing worker execution or task claim payloads.

## Document Boundaries

### [CURRENT_PROJECT.md](./CURRENT_PROJECT.md)

What it covers:

- the backend as it exists today
- implemented capabilities
- current CLI commands
- current API groups
- current gaps and known limitations

What it does not cover:

- long-term future-state architecture in depth
- speculative schema ideas not present in the codebase
- full worker payload examples

Use it when:

- onboarding a teammate
- checking whether a feature is already implemented
- explaining the project to someone who needs the current truth quickly

### [TARGET_ARCHITECTURE.md](./TARGET_ARCHITECTURE.md)

What it covers:

- the north-star architecture for the internal tool
- the conceptual model of `Job`, `Run`, `RunSubmission`, `Task`, and `TaskAttempt`
- why orchestration objects and lineage objects both exist
- how control-plane and lineage concerns should stay separated

What it does not cover:

- exact V1 screens or CLI details
- exact request and response payloads
- exact database columns

Use it when:

- judging whether a code change matches the intended architecture
- deciding where a new concept belongs
- resolving conceptual overlap between lineage and orchestration models

### [DJ_PROCESSING_V1_DESIGN.md](./DJ_PROCESSING_V1_DESIGN.md)

What it covers:

- the first product version focused on Data-Juicer processing
- V1 user journey
- V1 user-facing objects
- V1 worker behavior and product boundaries

What it does not cover:

- the full long-term training/evaluation platform vision
- exact SQL schema
- full route-by-route API detail

Use it when:

- deciding whether something belongs in V1
- reasoning about product scope and UX shape
- implementing the DJ-only execution flow

### [CLI_REFERENCE.md](./CLI_REFERENCE.md)

What it covers:

- the current `dj-panel` command tree
- what each command layer is responsible for
- local default resolution for `workspace`, `user`, and `base-url`
- common CLI workflows for backend operators and DJ workers

What it does not cover:

- endpoint-by-endpoint API design rationale
- full SQL ownership and schema design
- long-term architecture beyond the current CLI surface

Use it when:

- onboarding someone to the CLI
- adding or refactoring CLI commands
- checking how a user is expected to operate the backend from the terminal

### [V1_API_OPENAPI_STYLE.md](./V1_API_OPENAPI_STYLE.md)

What it covers:

- the intended V1 API contract in OpenAPI-like form
- resource naming
- payload structure
- response structure

What it does not cover:

- internal service/repository design
- SQL schema details
- worker-local execution mechanics

Use it when:

- aligning backend and frontend payloads
- adding new CLI commands
- reviewing whether route shapes are consistent

### [DATABASE_SCHEMA_DRAFT.md](./DATABASE_SCHEMA_DRAFT.md)

What it covers:

- the target data model by domain
- what tables belong to organization, authoring, lineage, and dispatch
- why lineage runtime facts and orchestration metadata should not be duplicated

What it does not cover:

- exact Alembic migration history
- exact current `app/db/schema.py` implementation details
- endpoint-level behavior

Use it when:

- changing table ownership or adding a new table
- checking whether a concept belongs in lineage projection or tool metadata
- planning future schema evolution

### [DJ_WORKER_PAYLOAD_AND_SEQUENCE.md](./DJ_WORKER_PAYLOAD_AND_SEQUENCE.md)

What it covers:

- the preferred DJ worker startup command
- task claim payload shape
- worker-side execution contract
- end-to-end sequence from submission to lineage ingestion

What it does not cover:

- the whole backend API surface
- broad product positioning
- non-DJ workers

Use it when:

- implementing or debugging `dj-panel worker dj`
- changing task payloads
- checking how `Task`, `RunSubmission`, and OpenLineage interact at execution time

## Source-of-Truth Rules

When documents disagree, use this order:

1. running code and tests
2. [CURRENT_PROJECT.md](./CURRENT_PROJECT.md) for present-state behavior
3. [V1_API_OPENAPI_STYLE.md](./V1_API_OPENAPI_STYLE.md) for intended API shape
4. [DATABASE_SCHEMA_DRAFT.md](./DATABASE_SCHEMA_DRAFT.md) for intended data ownership
5. [DJ_PROCESSING_V1_DESIGN.md](./DJ_PROCESSING_V1_DESIGN.md) for V1 scope decisions
6. [TARGET_ARCHITECTURE.md](./TARGET_ARCHITECTURE.md) for long-term direction

If code and docs diverge, the fix should be one of:

- update the code to match the intended design
- update the affected document to reflect reality
- add a note in [CURRENT_PROJECT.md](./CURRENT_PROJECT.md) if the mismatch is temporary
