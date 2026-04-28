# V1 API Draft in OpenAPI Style

## 1. What This Means

This document rewrites the V1 API draft in an OpenAPI-style format.

It is not a full machine-valid OpenAPI YAML file yet, but it uses the same mental model:

- `paths`
- `parameters`
- `requestBody`
- `responses`
- `schemas`

This format is easier to turn into a real OpenAPI spec later.

## 2. API Info

```yaml
openapi: 3.1.0
info:
  title: DJ Panel V1 API
  version: 0.1.0
  description: >
    Internal team tool API for Data-Juicer recipe management, processing
    submissions, DJ worker execution, and lineage-backed dataset visibility.
    Future model management should reuse the same lineage-derived asset backbone.
servers:
  - url: http://127.0.0.1:8000
```

## 3. Tags

```yaml
tags:
  - name: system
  - name: workspaces
  - name: recipes
  - name: datasets
  - name: run-submissions
  - name: workers
  - name: tasks
  - name: lineage
```

## 4. Component Schemas

```yaml
components:
  schemas:
    ErrorResponse:
      type: object
      required: [error]
      properties:
        error:
          type: object
          required: [code, message]
          properties:
            code:
              type: string
            message:
              type: string

    Workspace:
      type: object
      required: [id, slug, name]
      properties:
        id:
          type: string
          format: uuid
        slug:
          type: string
        name:
          type: string
        description:
          type: string

    Recipe:
      type: object
      required: [id, name, slug]
      properties:
        id:
          type: string
          format: uuid
        workspaceSlug:
          type: string
        name:
          type: string
        slug:
          type: string
        description:
          type: string
        currentVersionId:
          type: string
          format: uuid

    RecipeVersion:
      type: object
      required: [id, recipeId, version, rawYaml]
      properties:
        id:
          type: string
          format: uuid
        recipeId:
          type: string
          format: uuid
        version:
          type: integer
        rawYaml:
          type: string
        recipeHash:
          type: string
        projectName:
          type: string
        executorType:
          type: string
        operatorNames:
          type: array
          items:
            type: string
        pipelineJobNamespace:
          type: string
        pipelineJobName:
          type: string

    NamespaceName:
      type: object
      required: [namespace, name]
      properties:
        namespace:
          type: string
        name:
          type: string

    VersionedNamespaceName:
      allOf:
        - $ref: '#/components/schemas/NamespaceName'
        - type: object
          required: [version]
          properties:
            version:
              type: string

    FieldModel:
      type: object
      required: [name]
      properties:
        name:
          type: string
        type:
          type: string
          nullable: true
        tags:
          type: array
          items: {}
        description:
          type: string

    Dataset:
      type: object
      required: [id, type, name, physicalName, createdAt, updatedAt, namespace, sourceName, fields, tags, lastModifiedAt, description, facets, deleted]
      properties:
        id:
          $ref: '#/components/schemas/NamespaceName'
        type:
          type: string
        namespace:
          type: string
        name:
          type: string
        physicalName:
          type: string
        createdAt:
          type: string
          format: date-time
        updatedAt:
          type: string
          format: date-time
        sourceName:
          type: string
        fields:
          type: array
          items:
            $ref: '#/components/schemas/FieldModel'
        tags:
          type: array
          items: {}
        lastModifiedAt:
          type: string
          format: date-time
        description:
          type: string
        facets:
          type: object
          additionalProperties: true
        deleted:
          type: boolean
        columnLineage:
          nullable: true

    DatasetVersion:
      type: object
      required: [id, type, name, physicalName, createdAt, version, namespace, sourceName, fields, tags, lastModifiedAt, description, lifecycleState, facets]
      properties:
        id:
          $ref: '#/components/schemas/VersionedNamespaceName'
        type:
          type: string
        createdByRun:
          nullable: true
          type: object
          additionalProperties: true
        name:
          type: string
        physicalName:
          type: string
        createdAt:
          type: string
          format: date-time
        version:
          type: string
        namespace:
          type: string
        sourceName:
          type: string
        fields:
          type: array
          items:
            $ref: '#/components/schemas/FieldModel'
        tags:
          type: array
          items: {}
        lastModifiedAt:
          type: string
          format: date-time
        description:
          type: string
        lifecycleState:
          type: string
        facets:
          type: object
          additionalProperties: true

    Model:
      allOf:
        - $ref: '#/components/schemas/Dataset'
      description: >
        Reserved future view over lineage-derived assets classified as models.

    ModelVersion:
      allOf:
        - $ref: '#/components/schemas/DatasetVersion'
      description: >
        Reserved future view over lineage-derived asset versions classified as model versions.

    RunSubmissionInput:
      type: object
      required: [datasetVersionId]
      properties:
        datasetVersionId:
          type: string
          format: uuid
        role:
          type: string

    RunSubmissionOutput:
      type: object
      required: [datasetNamespace, datasetName]
      properties:
        datasetNamespace:
          type: string
        datasetName:
          type: string
        declaredVersion:
          type: string
        storageUri:
          type: string
        role:
          type: string

    RunSubmission:
      type: object
      required: [id, workspaceSlug, submissionKind, status]
      properties:
        id:
          type: string
          format: uuid
        workspaceSlug:
          type: string
        submissionKind:
          type: string
          enum: [processing_pipeline]
        status:
          type: string
          enum: [PENDING, DISPATCHED, RUNNING, SUCCEEDED, FAILED, CANCELLED]
        recipeVersionId:
          type: string
          format: uuid
        requestedBy:
          type: string
        parameters:
          type: object
          additionalProperties: true
        inputs:
          type: array
          items:
            $ref: '#/components/schemas/RunSubmissionInput'
        outputs:
          type: array
          items:
            $ref: '#/components/schemas/RunSubmissionOutput'
        createdTaskIds:
          type: array
          items:
            type: string
            format: uuid

    Worker:
      type: object
      required: [workerId]
      properties:
        workerId:
          type: string
        workerType:
          type: string
          enum: [dj]
        displayName:
          type: string
        labels:
          type: object
          additionalProperties: true
        capabilities:
          type: object
          additionalProperties: true
        maxConcurrency:
          type: integer

    Task:
      type: object
      required: [taskId, taskKind, status]
      properties:
        taskId:
          type: string
          format: uuid
        taskKind:
          type: string
          enum: [dj_recipe]
        status:
          type: string
          enum: [PENDING, CLAIMED, RUNNING, SUCCEEDED, FAILED, CANCELLED]
        attemptId:
          type: string
          format: uuid
        leaseToken:
          type: string

    TaskLog:
      type: object
      required: [stream, message, sequence]
      properties:
        stream:
          type: string
          enum: [STDOUT, STDERR]
        message:
          type: string
        sequence:
          type: integer

    TaskArtifact:
      type: object
      required: [artifactType, name, uri]
      properties:
        artifactType:
          type: string
        name:
          type: string
        uri:
          type: string
        metadata:
          type: object
          additionalProperties: true
```

## 5. Paths

## 5A. Current Implemented Product and Asset Paths

The current backend already implements:

```yaml
  /api/v1/workspaces/{workspace_slug}/run-submissions:
    post:
      summary: Create run submission
    get:
      summary: List run submissions

  /api/v1/run-submissions/{submission_id}:
    get:
      summary: Get run submission

  /api/v1/namespaces/{namespace}/datasets:
    get:
      summary: List datasets in a namespace

  /api/v1/namespaces/{namespace}/datasets/{dataset_name}:
    get:
      summary: Get one dataset

  /api/v1/namespaces/{namespace}/datasets/{dataset_name}/versions:
    get:
      summary: List dataset versions
```

V1 uses `run-submissions` as the product-facing execution request API.

### 5.1 `GET /health`

```yaml
paths:
  /health:
    get:
      tags: [system]
      summary: Health check
      responses:
        '200':
          description: Service health response
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: ok
```

### 5.2 `POST /api/v1/workspaces`

```yaml
  /api/v1/workspaces:
    post:
      tags: [workspaces]
      summary: Create workspace
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [slug, name]
              properties:
                slug:
                  type: string
                name:
                  type: string
                description:
                  type: string
      responses:
        '201':
          description: Workspace created
          content:
            application/json:
              schema:
                type: object
                properties:
                  workspace:
                    $ref: '#/components/schemas/Workspace'
        '409':
          description: Workspace slug already exists
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
```

### 5.3 `GET /api/v1/workspaces`

```yaml
  /api/v1/workspaces:
    get:
      tags: [workspaces]
      summary: List workspaces
      responses:
        '200':
          description: Workspace list
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/Workspace'
```

### 5.4 `POST /api/v1/workspaces/{workspace_slug}/recipes`

```yaml
  /api/v1/workspaces/{workspace_slug}/recipes:
    post:
      tags: [recipes]
      summary: Create recipe with initial version
      parameters:
        - in: path
          name: workspace_slug
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [name, initialVersion]
              properties:
                name:
                  type: string
                description:
                  type: string
                initialVersion:
                  type: object
                  required: [rawYaml]
                  properties:
                    rawYaml:
                      type: string
                    sourceType:
                      type: string
                    gitRepoUrl:
                      type: string
                    gitCommit:
                      type: string
      responses:
        '201':
          description: Recipe created
          content:
            application/json:
              schema:
                type: object
                properties:
                  recipe:
                    $ref: '#/components/schemas/Recipe'
```

### 5.5 `POST /api/v1/recipes/{recipe_id}/versions`

```yaml
  /api/v1/recipes/{recipe_id}/versions:
    post:
      tags: [recipes]
      summary: Publish recipe version
      parameters:
        - in: path
          name: recipe_id
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [rawYaml]
              properties:
                rawYaml:
                  type: string
                sourceType:
                  type: string
                gitRepoUrl:
                  type: string
                gitCommit:
                  type: string
                notes:
                  type: string
      responses:
        '201':
          description: Recipe version created
          content:
            application/json:
              schema:
                type: object
                properties:
                  recipeVersion:
                    $ref: '#/components/schemas/RecipeVersion'
```

### 5.6 `GET /api/v1/workspaces/{workspace_slug}/datasets`

```yaml
  /api/v1/workspaces/{workspace_slug}/datasets:
    get:
      tags: [datasets]
      summary: List datasets visible in a workspace
      parameters:
        - in: path
          name: workspace_slug
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Dataset list
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/Dataset'
```

Note:

- this is a target aggregation endpoint
- the current backend dataset API is namespace-based rather than workspace-based

### 5.7 `GET /api/v1/dataset-versions/{dataset_version_id}`

```yaml
  /api/v1/dataset-versions/{dataset_version_id}:
    get:
      tags: [datasets]
      summary: Get dataset version detail
      parameters:
        - in: path
          name: dataset_version_id
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Dataset version detail
          content:
            application/json:
              schema:
                type: object
                properties:
                  datasetVersion:
                    $ref: '#/components/schemas/DatasetVersion'
```

## 5A. Current Backend-Compatible Dataset Paths

The current backend already exposes dataset APIs in this shape:

```yaml
  /api/v1/namespaces/{namespace}/datasets:
    get:
      tags: [datasets, lineage]
      summary: List datasets in a namespace

  /api/v1/namespaces/{namespace}/datasets/{dataset_name}:
    get:
      tags: [datasets, lineage]
      summary: Get one dataset

  /api/v1/namespaces/{namespace}/datasets/{dataset_name}/versions:
    get:
      tags: [datasets, lineage]
      summary: List dataset versions
```

Recommended V1 approach:

- keep these namespace-based paths as the implementation base
- keep the current `DatasetModel` and `DatasetVersionModel` response shape
- add workspace-friendly dataset aggregation endpoints later

## 5B. Reserved Future Model Paths

Future model APIs can be introduced as filtered views over the same underlying lineage-derived asset tables:

```yaml
  /api/v1/workspaces/{workspace_slug}/models:
    get:
      summary: List model assets visible in a workspace

  /api/v1/models/{model_id}:
    get:
      summary: Get one model asset

  /api/v1/models/{model_id}/versions:
    get:
      summary: List model versions
```

These routes should not require a second runtime fact pipeline. They should be backed by the same lineage-projected asset records classified through facets.

### 5.8 `POST /api/v1/workspaces/{workspace_slug}/run-submissions`

```yaml
  /api/v1/workspaces/{workspace_slug}/run-submissions:
    post:
      tags: [run-submissions]
      summary: Create processing submission
      parameters:
        - in: path
          name: workspace_slug
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [submissionKind, recipeVersionId, inputs]
              properties:
                submissionKind:
                  type: string
                  enum: [processing_pipeline]
                recipeVersionId:
                  type: string
                  format: uuid
                requestedBy:
                  type: string
                parameters:
                  type: object
                  additionalProperties: true
                inputs:
                  type: array
                  items:
                    $ref: '#/components/schemas/RunSubmissionInput'
                outputs:
                  type: array
                  items:
                    $ref: '#/components/schemas/RunSubmissionOutput'
      responses:
        '201':
          description: Submission created
          content:
            application/json:
              schema:
                type: object
                properties:
                  submission:
                    $ref: '#/components/schemas/RunSubmission'
```

### 5.9 `GET /api/v1/run-submissions/{submission_id}`

```yaml
  /api/v1/run-submissions/{submission_id}:
    get:
      tags: [run-submissions]
      summary: Get submission detail
      parameters:
        - in: path
          name: submission_id
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Submission detail
          content:
            application/json:
              schema:
                type: object
                properties:
                  submission:
                    $ref: '#/components/schemas/RunSubmission'
```

### 5.10 `POST /api/v1/workspaces/{workspace_slug}/workers/register`

```yaml
  /api/v1/workspaces/{workspace_slug}/workers/register:
    post:
      tags: [workers]
      summary: Register DJ worker
      parameters:
        - in: path
          name: workspace_slug
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Worker'
      responses:
        '200':
          description: Worker registered
```

### 5.11 `POST /api/v1/workspaces/{workspace_slug}/tasks/claim`

```yaml
  /api/v1/workspaces/{workspace_slug}/tasks/claim:
    post:
      tags: [tasks]
      summary: Claim one matching task
      parameters:
        - in: path
          name: workspace_slug
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [workerId]
              properties:
                workerId:
                  type: string
                supportedTaskKinds:
                  type: array
                  items:
                    type: string
                    enum: [dj_recipe]
      responses:
        '200':
          description: Claim result
          content:
            application/json:
              schema:
                type: object
                properties:
                  claimed:
                    type: boolean
                  task:
                    $ref: '#/components/schemas/Task'
```

### 5.12 `POST /api/v1/tasks/{task_id}/start`

```yaml
  /api/v1/tasks/{task_id}/start:
    post:
      tags: [tasks]
      summary: Mark task running
      parameters:
        - in: path
          name: task_id
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [attemptId, leaseToken]
              properties:
                attemptId:
                  type: string
                  format: uuid
                leaseToken:
                  type: string
      responses:
        '200':
          description: Task started
```

### 5.13 `POST /api/v1/tasks/{task_id}/complete`

```yaml
  /api/v1/tasks/{task_id}/complete:
    post:
      tags: [tasks]
      summary: Mark task succeeded
      parameters:
        - in: path
          name: task_id
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [attemptId, leaseToken]
              properties:
                attemptId:
                  type: string
                  format: uuid
                leaseToken:
                  type: string
      responses:
        '200':
          description: Task completed
```

### 5.14 `POST /api/v1/tasks/{task_id}/fail`

```yaml
  /api/v1/tasks/{task_id}/fail:
    post:
      tags: [tasks]
      summary: Mark task failed
      parameters:
        - in: path
          name: task_id
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [attemptId, leaseToken, failureReason]
              properties:
                attemptId:
                  type: string
                  format: uuid
                leaseToken:
                  type: string
                failureReason:
                  type: string
      responses:
        '200':
          description: Task failed
```

### 5.15 `POST /api/v1/task-attempts/{attempt_id}/logs`

```yaml
  /api/v1/task-attempts/{attempt_id}/logs:
    post:
      tags: [tasks]
      summary: Append task log line
      parameters:
        - in: path
          name: attempt_id
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TaskLog'
      responses:
        '201':
          description: Log appended
```

### 5.16 `POST /api/v1/task-attempts/{attempt_id}/artifacts`

```yaml
  /api/v1/task-attempts/{attempt_id}/artifacts:
    post:
      tags: [tasks]
      summary: Register task artifact
      parameters:
        - in: path
          name: attempt_id
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TaskArtifact'
      responses:
        '201':
          description: Artifact registered
```

### 5.17 `POST /api/v1/lineage`

```yaml
  /api/v1/lineage:
    post:
      tags: [lineage]
      summary: Ingest OpenLineage event
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              additionalProperties: true
      responses:
        '202':
          description: Lineage event accepted
```

## 6. Recommended Next Step

The next step should be to convert this draft into a real `openapi.yaml` file under the backend repository so it can drive:

- FastAPI schema alignment
- frontend API client generation
- mock server generation
- endpoint review in Swagger UI
