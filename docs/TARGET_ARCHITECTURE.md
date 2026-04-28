# Target Architecture for the DJ Panel Internal Team Tool

## 1. Goal

DJ Panel should be a shared internal team tool for:

- dataset processing with Data-Juicer
- model training and experiment tracking with MLflow
- lineage collection through OpenLineage
- collaborative orchestration through one central backend

The system is designed for teams that repeatedly iterate on data recipes, dataset versions, training inputs, and model outputs.

## 2. Core Decision

**OpenLineage is the runtime fact backbone.**

Data-Juicer and MLflow already emit OpenLineage events through plugins. Because of that, the tool should not create a second runtime truth model for jobs, runs, inputs, and outputs.

The tool should instead:

- ingest OpenLineage events
- persist raw events
- project them into queryable tables
- enrich them with internal-tool metadata
- orchestrate workers and task dispatch
- expose a user-facing API for collaboration

This leads to a clean split:

- OpenLineage tells us what definitions and executions exist
- the tool tells us how team members submit work and how workers execute it

## 3. Mental Model

There are five key concepts.

- `Job`
  A logical executable definition from OpenLineage, identified by `job.namespace + job.name`.
- `Run`
  An observed OpenLineage execution of one job.
- `RunSubmission`
  A tool-side request created by a user to launch a processing or training execution.
- `Task`
  A claimable dispatch unit produced by the master so a worker can execute submitted work.
- `TaskAttempt`
  One concrete worker attempt for a task.

In short:

- `job` = definition
- `run` = observed execution fact
- `run_submission` = user intent
- `task` = dispatch
- `task_attempt` = worker attempt

## 4. Why `Job` and `Task` Both Exist

They solve different problems.

### 4.1 Job

`Job` is a lineage object.

It answers:

- what executable definition is this
- what is its stable identity
- what metadata and facets define it
- what inputs and outputs are associated with its projected versions

Examples:

- a Data-Juicer processing pipeline
- a Data-Juicer operator-level executable
- a training executable reported by MLflow lineage integration

### 4.2 Task

`Task` is a dispatch object.

It answers:

- what work is currently available for workers to claim
- which worker claimed it
- what state it is in
- how many attempts were made
- where logs and registered artifacts live

OpenLineage does not solve worker claiming, leases, retries, or dispatch state. That is why `Task` must exist even when `Job` and `Run` already exist.

## 5. Why `RunSubmission` Exists

`RunSubmission` is not a second run fact table.

It exists because the tool needs to remember:

- who submitted a launch request
- which recipe version or entrypoint they chose
- which input versions they selected
- which output location or namespace they expected
- which tasks were created from that request

This is user intent and orchestration context, not lineage runtime truth.

## 6. System Planes

The target internal tool has four planes.

### 6.1 Control Plane

Responsibilities:

- workspace organization
- recipe management
- run submission lifecycle
- worker registration and heartbeat
- task creation and claiming
- aggregation APIs for the frontend

### 6.2 Lineage Fact Plane

Responsibilities:

- receive OpenLineage events from DJ and MLflow
- persist raw events
- project jobs, runs, datasets, versions, and facets
- support lineage and metadata queries

### 6.3 Metadata and Authoring Plane

Responsibilities:

- recipe authoring and storage
- recipe versioning
- operator-level static metadata
- workspace-facing labels, ownership, and descriptions

### 6.4 Execution Plane

Responsibilities:

- worker polling
- worker claiming
- launching DJ or training commands
- streaming logs and artifacts
- relying on plugins to emit lineage automatically

## 7. Tool Modules

### 7.1 Dataset Hub

- browse datasets and dataset versions
- inspect schema, stats, tags, and lineage
- compare versions

### 7.2 Recipe Workstation

- import recipes from local or hub sources
- persist recipe versions
- inspect operator lists and DAGs
- compare recipe revisions

### 7.3 Processing Center

- choose input dataset versions
- choose a recipe version
- submit a run request
- track dispatch state, worker state, and observed pipeline runs

### 7.4 Training Center

- choose train and eval datasets
- launch training requests
- inspect metrics, checkpoints, model outputs, and lineage

### 7.5 Lineage Explorer

- traverse dataset-to-job-to-run relationships
- trace model provenance back to datasets and recipes
- inspect pipeline-level and operator-level executions

### 7.6 Worker Operations

- worker health
- queue and claim state
- attempt failures
- retry and lease diagnostics

## 8. Domain Model

### 8.1 Core Objects

- `Workspace`
- `Dataset`
- `DatasetVersion`
- `Job`
- `JobVersion`
- `Recipe`
- `RecipeVersion`
- `RunSubmission`
- `Run`
- `ModelVersion`

### 8.2 Execution Objects

- `Worker`
- `Task`
- `TaskAttempt`
- `TaskLog`
- `TaskArtifact`

### 8.3 Recipe Objects

Recipe objects remain first-class because OpenLineage does not replace authoring.

- `Recipe`
  Human-facing logical recipe identity
- `RecipeVersion`
  Immutable DJ snapshot with YAML, hash, normalized DAG, and code metadata
- `RecipeVersionOperator`
  Static operator-level expansion for workstation and diff features

## 9. Canonical Relationships

- one `Workspace` contains recipes, submissions, workers, and assets
- one `Recipe` has many `RecipeVersion`
- one `RecipeVersion` maps to one primary pipeline-level `JobVersion`
- one `RecipeVersion` may also correspond to many operator-level `JobVersion`
- one `RunSubmission` creates one or more `Task`
- one `Task` has one or more `TaskAttempt`
- one `TaskAttempt` may correlate to zero, one, or many observed `Run`
- one observed `Run` belongs to one projected `Job`
- observed `Run` records consume and produce `DatasetVersion`
- training-oriented runs may produce a `ModelVersion`

## 10. Data-Juicer Specific Mapping

The current Data-Juicer OpenLineage builder implies two runtime layers:

- a pipeline-level job and run
- operator-level jobs and runs linked through parent facets

That means the platform should not invent a second processing-definition model parallel to OpenLineage `jobs`.

Instead:

- treat pipeline-level and operator-level objects as valid OpenLineage jobs
- distinguish them with projected metadata such as `job_kind`
- keep recipe tables for authoring and diff, not for duplicating runtime job truth

Recommended projected `job_kind` values:

- `processing_pipeline`
- `processing_operator`
- `training`
- `evaluation`

## 11. Service Boundaries

### 11.1 Master

The master should expose one API surface for:

- workspaces
- recipes
- run submissions
- workers and tasks
- lineage ingestion
- metadata and graph queries

### 11.2 Workers

Recommended worker types:

- `dj-worker`
- `train-worker`
- `eval-worker`

Shared worker primitives:

- register
- heartbeat
- claim
- start
- complete
- fail
- log upload
- artifact registration

### 11.3 Workstation

The workstation is a UI and authoring layer. It should talk only to the master API.

## 12. Frontend Information Architecture

The frontend should not center the tool around raw tasks.

Recommended navigation:

- `Datasets`
- `Recipes`
- `Submissions`
- `Runs`
- `Models`
- `Lineage`
- `Workers`

Interpretation:

- `Submissions` show user intent and dispatch progress
- `Runs` show observed OpenLineage execution facts
- `Workers` show operational fleet state

## 13. Team Usage Model

This section describes how a small internal team would use the tool in practice.

### 13.1 Typical Roles

- data engineer
  authors and iterates on Data-Juicer recipes
- research engineer
  chooses dataset versions and launches training
- reviewer or lead
  compares outputs, checks lineage, and decides which dataset or model version becomes the next baseline
- infra owner
  keeps workers healthy and watches dispatch failures

### 13.2 Typical Processing Workflow

1. A team member imports or creates a recipe in the recipe workstation.
2. They save a new `RecipeVersion` with updated YAML, operator parameters, and code references.
3. They choose one or more input `DatasetVersion` records from the dataset hub.
4. They create a `RunSubmission` for a processing pipeline execution.
5. The tool creates one or more `Task` records for available workers.
6. A `dj-worker` claims the task and runs Data-Juicer.
7. DJ emits pipeline-level and operator-level OpenLineage events automatically.
8. The backend projects observed `Job`, `Run`, input, output, and facet data.
9. The team reviews the new output dataset versions, lineage, and run details.

### 13.3 Typical Training Workflow

1. A team member chooses train and eval dataset versions from the dataset hub.
2. They submit a training request through the training center.
3. The tool creates a `RunSubmission` and one or more `Task` records.
4. A `train-worker` claims the task and launches training.
5. MLflow and the lineage plugin emit OpenLineage events.
6. The backend projects the observed training `Job` and `Run`.
7. The team inspects metrics, model outputs, checkpoints, and dataset-to-model lineage.

### 13.4 What Team Members Actually Look At

- recipe pages to compare recipe versions
- dataset pages to compare dataset versions and provenance
- submission pages to see what was requested
- run pages to see what actually happened
- worker pages only when execution troubleshooting is needed

### 13.5 Why This Shape Fits an Internal Tool

The team does not need a large multi-tenant external platform. It needs one shared internal system that:

- preserves authoring history
- preserves runtime lineage truth
- makes dispatch and worker state observable
- lets several people collaborate on the same data and training lifecycle

## 14. Recommended Evolution

### Keep

- OpenLineage ingestion and projection
- worker claiming model
- recipe registry
- task attempts, logs, and artifacts

### Remove from the target model

- standalone `processing_runs`
- standalone `processing_run_inputs`
- standalone `processing_run_outputs`
- standalone `training_runs`
- standalone `training_run_inputs`
- standalone `training_run_outputs`

Those concepts overlap too heavily with projected OpenLineage `runs`, `run_inputs`, and `run_outputs`.

### Add or formalize

- `run_submissions`
- `run_submission_inputs`
- `run_submission_outputs`
- mapping tables from task attempts to observed lineage runs
- mapping tables from submissions to observed lineage runs

## 15. Final Recommendation

The best target architecture is:

- OpenLineage for definition and runtime facts
- recipes for authoring and versioning
- run submissions for user intent
- tasks for dispatch
- task attempts for worker execution history

That model is the cleanest fit for your current DJ and MLflow lineage integration strategy.
