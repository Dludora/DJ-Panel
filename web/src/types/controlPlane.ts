export interface Workspace {
  id: string
  slug: string
  name: string
  description: string
  createdAt: string
  updatedAt: string
}

export interface WorkspaceList {
  workspaces: Workspace[]
}

export interface WorkspaceMember {
  id: string
  workspaceId: string
  userName: string
  role: string
  createdAt: string
}

export interface WorkspaceMemberList {
  members: WorkspaceMember[]
}

export interface RecipeVersion {
  id: string
  recipeId: string
  versionNumber: number
  recipeBody: Record<string, unknown>
  command: string
  scriptPath: string
  parameterSchema: Record<string, unknown>
  envTemplate: Record<string, unknown>
  executionSpec: Record<string, unknown>
  timeoutSeconds: number
  createdBy: string
  createdAt: string
}

export interface Recipe {
  id: string
  workspaceId: string
  name: string
  description: string
  ownerName: string
  currentVersionId: string | null
  createdAt: string
  updatedAt: string
  currentVersion: RecipeVersion | null
}

export interface RecipeList {
  recipes: Recipe[]
}

export interface RecipeVersionList {
  versions: RecipeVersion[]
}

export interface RunSubmission {
  id: string
  workspaceId: string
  recipeId: string
  recipeVersionId: string
  requestedBy: string
  submissionKind: string
  status: string
  parameters: Record<string, unknown>
  rootLineageNodeId: string | null
  createdAt: string
  startedAt: string | null
  endedAt: string | null
  failureReason: string | null
}

export interface RunSubmissionList {
  submissions: RunSubmission[]
}

export interface Worker {
  id: string
  workspaceId: string
  displayName: string
  status: string
  labels: Record<string, unknown>
  capabilities: Record<string, unknown>
  maxConcurrency: number
  lastHeartbeatAt: string | null
  createdAt: string
  updatedAt: string
}

export interface WorkerList {
  workers: Worker[]
}

export interface TaskAttempt {
  id: string
  taskId: string
  workerId: string
  attemptNumber: number
  status: string
  leaseToken: string
  openlineageRunId: string | null
  startedAt: string | null
  endedAt: string | null
  lastHeartbeatAt: string | null
  failureReason: string | null
  createdAt: string
  updatedAt: string
}

export interface Task {
  id: string
  workspaceId: string
  runSubmissionId: string
  recipeVersionId: string
  taskKind: string
  status: string
  assignedWorkerId: string | null
  currentAttemptId: string | null
  leaseToken: string | null
  leaseExpiresAt: string | null
  attemptCount: number
  command: string
  scriptPath: string
  envVars: Record<string, unknown>
  executionSpec: Record<string, unknown>
  timeoutSeconds: number
  createdAt: string
  startedAt: string | null
  endedAt: string | null
  failureReason: string | null
  currentAttempt: TaskAttempt | null
}

export interface TaskList {
  tasks: Task[]
}

export interface TaskLog {
  id: string
  attemptId: string
  stream: string
  message: string
  sequence: number
  loggedAt: string
}

export interface TaskLogList {
  logs: TaskLog[]
}

export interface TaskArtifact {
  id: string
  attemptId: string
  kind: string
  name: string
  uri: string
  metadata: Record<string, unknown>
  datasetId: string | null
  datasetVersionId: string | null
  modelUri: string | null
  createdAt: string
}

export interface TaskArtifactList {
  artifacts: TaskArtifact[]
}
