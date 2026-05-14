# Documentation Map

This directory contains the planning and reference documents for `dj-panel-backend`.

The documents are intentionally split by concern. The most common source of confusion
was that several files were all describing "the system", but from different levels:

- current submission shape
- current API contract
- worker execution contract
- current implementation status

This file is the boundary map for those documents.

## Reading Order

If you are new to the project, read in this order:

1. [CURRENT_PROJECT.md](./CURRENT_PROJECT.md)
   Start here for what the backend currently is, what it already implements, and how to run it.
2. [CLI_REFERENCE.md](./CLI_REFERENCE.md)
   Use this when working on `dj-panel` commands, CLI defaults, or operator workflows.
3. [RUN_SUBMISSION_SPEC.md](./run/RUN_SUBMISSION_SPEC.md)
   Use this when working on `run submit`, especially the processing spec-first path.
4. [openapi.yaml](./api/openapi.yaml)
   Use this when working on frontend-backend contracts or current route shapes.
5. [SFT_MLFLOW_LINEAGE_DESIGN.md](./worker/train_eval/SFT_MLFLOW_LINEAGE_DESIGN.md)
   Use this when planning MLflow-based SFT train/eval lineage coverage.
6. [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)
   Use this when configuring runtime defaults, deployment environments, or operator startup scripts.
7. [DJ_WORKER_PAYLOAD_AND_SEQUENCE.md](./worker/data-juicer/DJ_WORKER_PAYLOAD_AND_SEQUENCE.md)
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

### [RUN_SUBMISSION_SPEC.md](./run/RUN_SUBMISSION_SPEC.md)

What it covers:

- the current run-submission CLI shape
- the processing spec-first contract
- how `workspace_recipe` and `local_file` processing specs work
- where training/evaluation still differ

Use it when:

- changing `run submit`
- designing new submission kinds
- reviewing processing spec examples

### [openapi.yaml](./api/openapi.yaml)

What it covers:

- the current FastAPI-generated HTTP API contract
- request bodies
- response schemas
- current route and parameter shapes

What it does not cover:

- long-term API redesign ideas
- service/repository internals
- worker-local execution behavior

Use it when:

- aligning frontend and backend payloads
- checking current route names and schemas
- generating clients or API references

### [SFT_MLFLOW_LINEAGE_DESIGN.md](./worker/train_eval/SFT_MLFLOW_LINEAGE_DESIGN.md)

What it covers:

- the target MLflow + OpenLineage coverage for SFT training and evaluation
- what `mlflow-openlineage` already emits automatically
- which dataset/model/report lineage events still need explicit emission
- reference example script locations

Use it when:

- planning LLM training/eval lineage
- reviewing MLflow instrumentation scope
- implementing SFT example scripts

### [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)

What it covers:

- all supported runtime environment variables
- default values and aliases
- which subsystem uses each variable
- precedence between CLI args, local CLI config, and environment

What it does not cover:

- route-by-route API behavior
- deep schema ownership decisions
- worker execution sequence details

Use it when:

- preparing local `.env` files
- deploying backend or workers
- removing hardcoded defaults from code

### [DJ_WORKER_PAYLOAD_AND_SEQUENCE.md](./worker/data-juicer/DJ_WORKER_PAYLOAD_AND_SEQUENCE.md)

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
3. [openapi.yaml](./api/openapi.yaml) for current HTTP route and schema shape
4. [RUN_SUBMISSION_SPEC.md](./run/RUN_SUBMISSION_SPEC.md) for current submission-spec behavior
5. [README.md](./README.md) to find the right current document when the others are too narrow

If code and docs diverge, the fix should be one of:

- update the code to match the intended design
- update the affected document to reflect reality
- add a note in [CURRENT_PROJECT.md](./CURRENT_PROJECT.md) if the mismatch is temporary
