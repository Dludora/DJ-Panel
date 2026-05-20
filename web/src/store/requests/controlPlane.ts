import { API_URL } from '../../globals'
import {
  Recipe,
  RecipeList,
  RecipeVersionList,
  RunSubmission,
  RunSubmissionList,
  Task,
  TaskArtifactList,
  TaskList,
  TaskLogList,
  WorkerList,
  Workspace,
  WorkspaceList,
  WorkspaceMember,
  WorkspaceMemberList,
} from '../../types/controlPlane'
import { genericFetchWrapper } from './index'

const jsonHeaders = {
  'Content-Type': 'application/json',
}

export const getWorkspaces = async () => {
  return genericFetchWrapper(`${API_URL}/workspaces`, { method: 'GET' }, 'getWorkspaces').then(
    (payload: WorkspaceList) => payload.workspaces
  )
}

export const createWorkspace = async (payload: {
  slug: string
  name: string
  description: string
  ownerName: string
}) => {
  return genericFetchWrapper(
    `${API_URL}/workspaces`,
    { method: 'POST', headers: jsonHeaders, body: JSON.stringify(payload) },
    'createWorkspace'
  ).then((workspace: Workspace) => workspace)
}

export const getWorkspaceMembers = async (workspace: string) => {
  const encodedWorkspace = encodeURIComponent(workspace)
  return genericFetchWrapper(
    `${API_URL}/workspaces/${encodedWorkspace}/members`,
    { method: 'GET' },
    'getWorkspaceMembers'
  ).then((payload: WorkspaceMemberList) => payload.members)
}

export const addWorkspaceMember = async (
  workspace: string,
  payload: { userName: string; role: string }
) => {
  const encodedWorkspace = encodeURIComponent(workspace)
  return genericFetchWrapper(
    `${API_URL}/workspaces/${encodedWorkspace}/members`,
    { method: 'POST', headers: jsonHeaders, body: JSON.stringify(payload) },
    'addWorkspaceMember'
  ).then((member: WorkspaceMember) => member)
}

export const getRecipes = async (workspace: string) => {
  const encodedWorkspace = encodeURIComponent(workspace)
  return genericFetchWrapper(
    `${API_URL}/workspaces/${encodedWorkspace}/recipes`,
    { method: 'GET' },
    'getRecipes'
  ).then((payload: RecipeList) => payload.recipes)
}

export const createRecipe = async (
  workspace: string,
  payload: {
    name: string
    description: string
    ownerName: string
    recipeBody: Record<string, unknown>
    command: string
    scriptPath: string
    parameterSchema: Record<string, unknown>
    envTemplate: Record<string, unknown>
    executionSpec: Record<string, unknown>
    timeoutSeconds: number
  }
) => {
  const encodedWorkspace = encodeURIComponent(workspace)
  return genericFetchWrapper(
    `${API_URL}/workspaces/${encodedWorkspace}/recipes`,
    { method: 'POST', headers: jsonHeaders, body: JSON.stringify(payload) },
    'createRecipe'
  ).then((recipe: Recipe) => recipe)
}

export const getRecipeVersions = async (recipeId: string) => {
  const encodedRecipeId = encodeURIComponent(recipeId)
  return genericFetchWrapper(
    `${API_URL}/recipes/${encodedRecipeId}/versions`,
    { method: 'GET' },
    'getRecipeVersions'
  ).then((payload: RecipeVersionList) => payload.versions)
}

export const getRunSubmissions = async (workspace: string) => {
  const encodedWorkspace = encodeURIComponent(workspace)
  return genericFetchWrapper(
    `${API_URL}/workspaces/${encodedWorkspace}/run-submissions`,
    { method: 'GET' },
    'getRunSubmissions'
  ).then((payload: RunSubmissionList) => payload.submissions)
}

export const createRunSubmission = async (
  workspace: string,
  payload: {
    recipeVersionId: string
    requestedBy: string
    submissionKind: string
    parameters: Record<string, unknown>
    inputs: unknown[]
    outputs: unknown[]
  }
) => {
  const encodedWorkspace = encodeURIComponent(workspace)
  return genericFetchWrapper(
    `${API_URL}/workspaces/${encodedWorkspace}/run-submissions`,
    { method: 'POST', headers: jsonHeaders, body: JSON.stringify(payload) },
    'createRunSubmission'
  ).then((submission: RunSubmission) => submission)
}

export const getTasks = async (workspace: string) => {
  const encodedWorkspace = encodeURIComponent(workspace)
  return genericFetchWrapper(
    `${API_URL}/workspaces/${encodedWorkspace}/tasks`,
    { method: 'GET' },
    'getTasks'
  ).then((payload: TaskList) => payload.tasks)
}

export const getTask = async (taskId: string) => {
  const encodedTaskId = encodeURIComponent(taskId)
  return genericFetchWrapper(`${API_URL}/tasks/${encodedTaskId}`, { method: 'GET' }, 'getTask').then(
    (task: Task) => task
  )
}

export const getTaskLogs = async (attemptId: string) => {
  const encodedAttemptId = encodeURIComponent(attemptId)
  return genericFetchWrapper(
    `${API_URL}/task-attempts/${encodedAttemptId}/logs`,
    { method: 'GET' },
    'getTaskLogs'
  ).then((payload: TaskLogList) => payload.logs)
}

export const getTaskArtifacts = async (attemptId: string) => {
  const encodedAttemptId = encodeURIComponent(attemptId)
  return genericFetchWrapper(
    `${API_URL}/task-attempts/${encodedAttemptId}/artifacts`,
    { method: 'GET' },
    'getTaskArtifacts'
  ).then((payload: TaskArtifactList) => payload.artifacts)
}

export const getWorkers = async (workspace: string) => {
  const encodedWorkspace = encodeURIComponent(workspace)
  return genericFetchWrapper(
    `${API_URL}/workspaces/${encodedWorkspace}/workers`,
    { method: 'GET' },
    'getWorkers'
  ).then((payload: WorkerList) => payload.workers)
}
