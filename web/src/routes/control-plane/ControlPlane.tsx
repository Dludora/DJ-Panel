import React, { ReactElement, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import {
  addWorkspaceMember,
  createRunSubmission,
  createWorkspace,
  getRecipeVersions,
  getRecipes,
  getRunSubmissions,
  getTask,
  getTaskArtifacts,
  getTaskLogs,
  getTasks,
  getWorkers,
  getWorkspaceMembers,
  getWorkspaces,
} from '../../store/requests'
import {
  Recipe,
  RecipeVersion,
  RunSubmission,
  Task,
  TaskArtifact,
  TaskLog,
  Worker,
  Workspace,
  WorkspaceMember,
} from '../../types/controlPlane'

const STORAGE_WORKSPACE_KEY = 'dj-panel:selected-workspace'
const STORAGE_USER_KEY = 'dj-panel:requested-by'

const JsonBlock = ({ value }: { value: unknown }) => {
  return (
    <Box
      component='pre'
      sx={{
        m: 0,
        p: 2,
        borderRadius: 1,
        overflowX: 'auto',
        backgroundColor: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        fontSize: 12,
      }}
    >
      {JSON.stringify(value, null, 2)}
    </Box>
  )
}

const formatTime = (value: string | null | undefined) => {
  if (!value) {
    return '-'
  }
  return new Date(value).toLocaleString()
}

const statusColor = (
  status: string
): 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info' => {
  if (status === 'SUCCEEDED' || status === 'COMPLETED' || status === 'ACTIVE') {
    return 'success'
  }
  if (status === 'FAILED') {
    return 'error'
  }
  if (status === 'RUNNING' || status === 'CLAIMED') {
    return 'info'
  }
  if (status === 'SUBMITTED' || status === 'PENDING') {
    return 'warning'
  }
  return 'default'
}

const SectionTitle = ({
  title,
  action,
}: {
  title: string
  action?: React.ReactNode
}) => {
  return (
    <Stack direction='row' justifyContent='space-between' alignItems='center' mb={2}>
      <Typography variant='h6'>{title}</Typography>
      {action}
    </Stack>
  )
}

const ControlPlane = (): ReactElement => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [selectedWorkspace, setSelectedWorkspace] = useState(
    window.localStorage.getItem(STORAGE_WORKSPACE_KEY) || ''
  )
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [selectedRecipeId, setSelectedRecipeId] = useState('')
  const [recipeVersions, setRecipeVersions] = useState<RecipeVersion[]>([])
  const [submissions, setSubmissions] = useState<RunSubmission[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [taskLogs, setTaskLogs] = useState<TaskLog[]>([])
  const [taskArtifacts, setTaskArtifacts] = useState<TaskArtifact[]>([])
  const [workers, setWorkers] = useState<Worker[]>([])
  const [requestedBy, setRequestedBy] = useState(
    window.localStorage.getItem(STORAGE_USER_KEY) || ''
  )
  const [workspaceForm, setWorkspaceForm] = useState({
    slug: '',
    name: '',
    description: '',
    ownerName: '',
  })
  const [memberForm, setMemberForm] = useState({ userName: '', role: 'MEMBER' })
  const [parametersText, setParametersText] = useState('{}')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)

  const selectedRecipe = recipes.find((recipe) => recipe.id === selectedRecipeId) || null

  const loadWorkspaces = async () => {
    const nextWorkspaces = await getWorkspaces()
    setWorkspaces(nextWorkspaces)
    if (!selectedWorkspace && nextWorkspaces.length > 0) {
      const workspace = nextWorkspaces[0].slug
      setSelectedWorkspace(workspace)
      window.localStorage.setItem(STORAGE_WORKSPACE_KEY, workspace)
    }
  }

  const loadWorkspaceData = async (workspaceSlug: string) => {
    if (!workspaceSlug) {
      setMembers([])
      setRecipes([])
      setRecipeVersions([])
      setSubmissions([])
      setTasks([])
      setSelectedTask(null)
      setTaskLogs([])
      setTaskArtifacts([])
      setWorkers([])
      return
    }
    const [nextMembers, nextRecipes, nextSubmissions, nextTasks, nextWorkers] = await Promise.all([
      getWorkspaceMembers(workspaceSlug),
      getRecipes(workspaceSlug),
      getRunSubmissions(workspaceSlug),
      getTasks(workspaceSlug),
      getWorkers(workspaceSlug),
    ])
    setMembers(nextMembers)
    setRecipes(nextRecipes)
    setSubmissions(nextSubmissions)
    setTasks(nextTasks)
    setWorkers(nextWorkers)
    if (!selectedRecipeId && nextRecipes.length > 0) {
      setSelectedRecipeId(nextRecipes[0].id)
    }
    if (!selectedTaskId && nextTasks.length > 0) {
      setSelectedTaskId(nextTasks[0].id)
    }
  }

  const loadSelectedTask = async (taskId: string) => {
    if (!taskId) {
      setSelectedTask(null)
      setTaskLogs([])
      setTaskArtifacts([])
      return
    }
    const task = await getTask(taskId)
    setSelectedTask(task)
    const attemptId = task.currentAttemptId || task.currentAttempt?.id
    if (!attemptId) {
      setTaskLogs([])
      setTaskArtifacts([])
      return
    }
    const [logs, artifacts] = await Promise.all([getTaskLogs(attemptId), getTaskArtifacts(attemptId)])
    setTaskLogs(logs)
    setTaskArtifacts(artifacts)
  }

  const refreshAll = async () => {
    setLoading(true)
    setError('')
    try {
      await loadWorkspaces()
      if (selectedWorkspace) {
        await loadWorkspaceData(selectedWorkspace)
      }
      if (selectedTaskId) {
        await loadSelectedTask(selectedTaskId)
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refreshAll()
  }, [])

  useEffect(() => {
    if (!selectedWorkspace) {
      return
    }
    window.localStorage.setItem(STORAGE_WORKSPACE_KEY, selectedWorkspace)
    setLoading(true)
    setError('')
    void loadWorkspaceData(selectedWorkspace)
      .then(() => setNotice(''))
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)))
      .finally(() => setLoading(false))
  }, [selectedWorkspace])

  useEffect(() => {
    if (!selectedRecipeId) {
      setRecipeVersions([])
      return
    }
    setError('')
    void getRecipeVersions(selectedRecipeId)
      .then((versions) => setRecipeVersions(versions))
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)))
  }, [selectedRecipeId])

  useEffect(() => {
    if (!selectedTaskId) {
      setSelectedTask(null)
      setTaskLogs([])
      setTaskArtifacts([])
      return
    }
    setError('')
    void loadSelectedTask(selectedTaskId).catch((exc) =>
      setError(exc instanceof Error ? exc.message : String(exc))
    )
  }, [selectedTaskId])

  const handleCreateWorkspace = async () => {
    setError('')
    setNotice('')
    try {
      const workspace = await createWorkspace({
        slug: workspaceForm.slug,
        name: workspaceForm.name || workspaceForm.slug,
        description: workspaceForm.description,
        ownerName: workspaceForm.ownerName,
      })
      setNotice(`Workspace created: ${workspace.slug}`)
      setWorkspaceForm({ slug: '', name: '', description: '', ownerName: '' })
      await loadWorkspaces()
      setSelectedWorkspace(workspace.slug)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    }
  }

  const handleAddMember = async () => {
    if (!selectedWorkspace) {
      setError('Please select a workspace first.')
      return
    }
    setError('')
    setNotice('')
    try {
      await addWorkspaceMember(selectedWorkspace, memberForm)
      setNotice(`Member updated: ${memberForm.userName}`)
      setMemberForm({ userName: '', role: 'MEMBER' })
      setMembers(await getWorkspaceMembers(selectedWorkspace))
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    }
  }

  const handleCreateSubmission = async () => {
    if (!selectedWorkspace || !selectedRecipe) {
      setError('Please select a workspace and recipe first.')
      return
    }
    if (!requestedBy) {
      setError('Requested by is required.')
      return
    }
    let parameters: Record<string, unknown> = {}
    try {
      parameters = JSON.parse(parametersText)
    } catch (_exc) {
      setError('Parameters must be valid JSON.')
      return
    }
    if (!selectedRecipe.currentVersion) {
      setError('Selected recipe does not have a current version.')
      return
    }
    setError('')
    setNotice('')
    window.localStorage.setItem(STORAGE_USER_KEY, requestedBy)
    try {
      const submission = await createRunSubmission(selectedWorkspace, {
        recipeVersionId: selectedRecipe.currentVersion.id,
        requestedBy,
        submissionKind: 'processing_pipeline',
        parameters,
        inputs: [],
        outputs: [],
      })
      setNotice(`Run submission created: ${submission.id}`)
      setSubmissions(await getRunSubmissions(selectedWorkspace))
      setTasks(await getTasks(selectedWorkspace))
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    }
  }

  return (
    <Box px={4} py={12}>
      <Stack direction='row' justifyContent='space-between' alignItems='center' mb={3}>
        <Box>
          <Typography variant='h4' mb={1}>
            Control Plane
          </Typography>
          <Typography color='text.secondary'>
            Manage team workspaces, Data-Juicer recipes, run submissions, workers, and task execution.
          </Typography>
        </Box>
        <Button variant='contained' onClick={() => void refreshAll()} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </Button>
      </Stack>

      {error ? <Alert severity='error' sx={{ mb: 2 }}>{error}</Alert> : null}
      {notice ? <Alert severity='success' sx={{ mb: 2 }}>{notice}</Alert> : null}

      <Grid container spacing={2} mb={3}>
        <Grid item xs={12} md={3}>
          <Card><CardContent><Typography variant='overline'>Workspaces</Typography><Typography variant='h4'>{workspaces.length}</Typography></CardContent></Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card><CardContent><Typography variant='overline'>Recipes</Typography><Typography variant='h4'>{recipes.length}</Typography></CardContent></Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card><CardContent><Typography variant='overline'>Run Submissions</Typography><Typography variant='h4'>{submissions.length}</Typography></CardContent></Card>
        </Grid>
        <Grid item xs={12} md={3}>
          <Card><CardContent><Typography variant='overline'>Workers</Typography><Typography variant='h4'>{workers.length}</Typography></CardContent></Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <SectionTitle title='Workspace Context' />
            <Stack spacing={2}>
              <Select
                value={selectedWorkspace}
                displayEmpty
                onChange={(event) => setSelectedWorkspace(event.target.value)}
              >
                <MenuItem value=''>Select workspace</MenuItem>
                {workspaces.map((workspace) => (
                  <MenuItem key={workspace.id} value={workspace.slug}>
                    {workspace.slug}
                  </MenuItem>
                ))}
              </Select>
              <TextField
                label='Requested By'
                value={requestedBy}
                onChange={(event) => setRequestedBy(event.target.value)}
              />
            </Stack>
          </Paper>

          <Paper sx={{ p: 3, mb: 3 }}>
            <SectionTitle title='Create Workspace' />
            <Stack spacing={2}>
              <TextField
                label='Slug'
                value={workspaceForm.slug}
                onChange={(event) => setWorkspaceForm({ ...workspaceForm, slug: event.target.value })}
              />
              <TextField
                label='Name'
                value={workspaceForm.name}
                onChange={(event) => setWorkspaceForm({ ...workspaceForm, name: event.target.value })}
              />
              <TextField
                label='Owner'
                value={workspaceForm.ownerName}
                onChange={(event) =>
                  setWorkspaceForm({ ...workspaceForm, ownerName: event.target.value })
                }
              />
              <TextField
                label='Description'
                multiline
                minRows={2}
                value={workspaceForm.description}
                onChange={(event) =>
                  setWorkspaceForm({ ...workspaceForm, description: event.target.value })
                }
              />
              <Button variant='outlined' onClick={() => void handleCreateWorkspace()}>
                Create Workspace
              </Button>
            </Stack>
          </Paper>

          <Paper sx={{ p: 3 }}>
            <SectionTitle title='Workspace Members' />
            <Stack spacing={2} mb={2}>
              <TextField
                label='User Name'
                value={memberForm.userName}
                onChange={(event) => setMemberForm({ ...memberForm, userName: event.target.value })}
              />
              <Select
                value={memberForm.role}
                onChange={(event) => setMemberForm({ ...memberForm, role: event.target.value })}
              >
                <MenuItem value='OWNER'>OWNER</MenuItem>
                <MenuItem value='MAINTAINER'>MAINTAINER</MenuItem>
                <MenuItem value='MEMBER'>MEMBER</MenuItem>
                <MenuItem value='VIEWER'>VIEWER</MenuItem>
              </Select>
              <Button variant='outlined' onClick={() => void handleAddMember()}>
                Add Member
              </Button>
            </Stack>
            <Divider sx={{ my: 2 }} />
            <Stack spacing={1}>
              {members.map((member) => (
                <Box key={member.id} display='flex' justifyContent='space-between'>
                  <Typography>{member.userName}</Typography>
                  <Chip size='small' label={member.role} />
                </Box>
              ))}
              {members.length === 0 ? <Typography color='text.secondary'>No members yet.</Typography> : null}
            </Stack>
          </Paper>
        </Grid>

        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <SectionTitle title='Recipes and Submission' />
            <Grid container spacing={2}>
              <Grid item xs={12} md={5}>
                <Stack spacing={2}>
                  <Select
                    value={selectedRecipeId}
                    displayEmpty
                    onChange={(event) => setSelectedRecipeId(event.target.value)}
                  >
                    <MenuItem value=''>Select recipe</MenuItem>
                    {recipes.map((recipe) => (
                      <MenuItem key={recipe.id} value={recipe.id}>
                        {recipe.name}
                      </MenuItem>
                    ))}
                  </Select>
                  <TextField
                    label='Submission Parameters JSON'
                    multiline
                    minRows={8}
                    value={parametersText}
                    onChange={(event) => setParametersText(event.target.value)}
                  />
                  <Button variant='contained' onClick={() => void handleCreateSubmission()}>
                    Create Run Submission
                  </Button>
                </Stack>
              </Grid>
              <Grid item xs={12} md={7}>
                {selectedRecipe ? (
                  <Stack spacing={2}>
                    <Box>
                      <Typography variant='subtitle1'>{selectedRecipe.name}</Typography>
                      <Typography color='text.secondary'>{selectedRecipe.description || 'No description'}</Typography>
                    </Box>
                    <Box display='flex' gap={1} flexWrap='wrap'>
                      <Chip size='small' label={`owner: ${selectedRecipe.ownerName}`} />
                      {selectedRecipe.currentVersion ? (
                        <Chip size='small' color='info' label={`v${selectedRecipe.currentVersion.versionNumber}`} />
                      ) : null}
                    </Box>
                    {selectedRecipe.currentVersion ? <JsonBlock value={selectedRecipe.currentVersion.recipeBody} /> : null}
                    <Typography variant='subtitle2'>Recipe Versions</Typography>
                    <Stack direction='row' gap={1} flexWrap='wrap'>
                      {recipeVersions.map((version) => (
                        <Chip
                          key={version.id}
                          label={`v${version.versionNumber} · ${version.createdBy}`}
                          color={selectedRecipe.currentVersionId === version.id ? 'primary' : 'default'}
                        />
                      ))}
                    </Stack>
                  </Stack>
                ) : (
                  <Typography color='text.secondary'>Select a recipe to inspect and submit.</Typography>
                )}
              </Grid>
            </Grid>
          </Paper>

          <Paper sx={{ p: 3, mb: 3 }}>
            <SectionTitle title='Run Submissions' />
            <Table size='small'>
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Requested By</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Lineage Root</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {submissions.map((submission) => (
                  <TableRow key={submission.id}>
                    <TableCell>{submission.id}</TableCell>
                    <TableCell><Chip size='small' color={statusColor(submission.status)} label={submission.status} /></TableCell>
                    <TableCell>{submission.requestedBy}</TableCell>
                    <TableCell>{formatTime(submission.createdAt)}</TableCell>
                    <TableCell>{submission.rootLineageNodeId || '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>

          <Paper sx={{ p: 3, mb: 3 }}>
            <SectionTitle title='Workers' />
            <Table size='small'>
              <TableHead>
                <TableRow>
                  <TableCell>ID</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Display Name</TableCell>
                  <TableCell>Last Heartbeat</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {workers.map((worker) => (
                  <TableRow key={worker.id}>
                    <TableCell>{worker.id}</TableCell>
                    <TableCell><Chip size='small' color={statusColor(worker.status)} label={worker.status} /></TableCell>
                    <TableCell>{worker.displayName}</TableCell>
                    <TableCell>{formatTime(worker.lastHeartbeatAt)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>

          <Paper sx={{ p: 3 }}>
            <SectionTitle title='Tasks' />
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Table size='small'>
                  <TableHead>
                    <TableRow>
                      <TableCell>Task</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Worker</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {tasks.map((task) => (
                      <TableRow
                        key={task.id}
                        hover
                        selected={selectedTaskId === task.id}
                        onClick={() => setSelectedTaskId(task.id)}
                        sx={{ cursor: 'pointer' }}
                      >
                        <TableCell>{task.id}</TableCell>
                        <TableCell><Chip size='small' color={statusColor(task.status)} label={task.status} /></TableCell>
                        <TableCell>{task.assignedWorkerId || '-'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Grid>
              <Grid item xs={12} md={6}>
                {selectedTask ? (
                  <Stack spacing={2}>
                    <Typography variant='subtitle1'>Task Detail</Typography>
                    <JsonBlock
                      value={{
                        id: selectedTask.id,
                        status: selectedTask.status,
                        taskKind: selectedTask.taskKind,
                        command: selectedTask.command,
                        scriptPath: selectedTask.scriptPath,
                        executionSpec: selectedTask.executionSpec,
                        envVars: selectedTask.envVars,
                        currentAttempt: selectedTask.currentAttempt,
                        failureReason: selectedTask.failureReason,
                      }}
                    />
                    <Typography variant='subtitle2'>Logs</Typography>
                    <Box
                      sx={{
                        maxHeight: 220,
                        overflowY: 'auto',
                        p: 2,
                        borderRadius: 1,
                        backgroundColor: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.08)',
                        fontFamily: 'monospace',
                        fontSize: 12,
                      }}
                    >
                      {taskLogs.length === 0
                        ? 'No logs for the current attempt.'
                        : taskLogs.map((log) => `[${log.stream}] ${log.message}`).join('\n')}
                    </Box>
                    <Typography variant='subtitle2'>Artifacts</Typography>
                    {taskArtifacts.length === 0 ? (
                      <Typography color='text.secondary'>No artifacts for the current attempt.</Typography>
                    ) : (
                      taskArtifacts.map((artifact) => (
                        <Paper key={artifact.id} variant='outlined' sx={{ p: 2 }}>
                          <Typography>{artifact.name}</Typography>
                          <Typography variant='body2' color='text.secondary'>
                            {artifact.kind} · {artifact.uri}
                          </Typography>
                          <Box mt={1}>
                            <JsonBlock value={artifact.metadata} />
                          </Box>
                        </Paper>
                      ))
                    )}
                  </Stack>
                ) : (
                  <Typography color='text.secondary'>Select a task to inspect logs and artifacts.</Typography>
                )}
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  )
}

export default ControlPlane
