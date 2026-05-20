import React from 'react'
import yaml from 'js-yaml'
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  InputAdornment,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
} from '@mui/material'
import { Add, Refresh, Visibility } from '@mui/icons-material'
import { HEADER_HEIGHT } from '../../helpers/theme'
import { MqScreenLoad } from '../../components/core/screen-load/MqScreenLoad'
import CircularProgress from '@mui/material/CircularProgress/CircularProgress'
import IconButton from '@mui/material/IconButton'
import MQTooltip from '../../components/core/tooltip/MQTooltip'
import MqEmpty from '../../components/core/empty/MqEmpty'
import MqPaging from '../../components/paging/MqPaging'
import MqText from '../../components/core/text/MqText'
import Stack from '@mui/material/Stack'
import { createRecipe, getRecipes } from '../../store/requests'
import { Recipe } from '../../types/controlPlane'
import { formatUpdatedAt } from '../../helpers'

const STORAGE_WORKSPACE_KEY = 'dj-panel:selected-workspace'
const STORAGE_USER_KEY = 'dj-panel:requested-by'
const PAGE_SIZE = 20
const RECIPE_HEADER_HEIGHT = 64

const parseRecipeName = (recipeBody: Record<string, unknown>, filename: string) => {
  const projectName = recipeBody.project_name
  if (typeof projectName === 'string' && projectName.trim()) {
    return projectName.trim()
  }
  return filename.replace(/\.[^.]+$/, '')
}

const yamlStringify = (recipeBody: Record<string, unknown>) =>
  yaml.dump(recipeBody, {
    noRefs: true,
    lineWidth: 120,
    sortKeys: false,
  })

const Recipes: React.FC = () => {
  const [page, setPage] = React.useState(0)
  const [workspace, setWorkspace] = React.useState(
    window.localStorage.getItem(STORAGE_WORKSPACE_KEY) || ''
  )
  const [owner, setOwner] = React.useState(window.localStorage.getItem(STORAGE_USER_KEY) || '')
  const [recipes, setRecipes] = React.useState<Recipe[]>([])
  const [selectedRecipe, setSelectedRecipe] = React.useState<Recipe | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [uploading, setUploading] = React.useState(false)
  const [error, setError] = React.useState('')
  const [notice, setNotice] = React.useState('')
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [uploadDialogOpen, setUploadDialogOpen] = React.useState(false)
  const [draftName, setDraftName] = React.useState('')
  const [draftDescription, setDraftDescription] = React.useState('')
  const [draftFileName, setDraftFileName] = React.useState('')
  const [draftYamlText, setDraftYamlText] = React.useState('')
  const [draftBody, setDraftBody] = React.useState<Record<string, unknown> | null>(null)

  const loadRecipes = React.useCallback(async () => {
    if (!workspace) {
      setRecipes([])
      setSelectedRecipe(null)
      return
    }
    setLoading(true)
    setError('')
    try {
      const payload = await getRecipes(workspace)
      setRecipes(payload)
      setPage(0)
      setSelectedRecipe((current) => {
        if (!current) {
          return payload[0] || null
        }
        return payload.find((recipe) => recipe.id === current.id) || payload[0] || null
      })
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setLoading(false)
    }
  }, [workspace])

  React.useEffect(() => {
    void loadRecipes()
  }, [loadRecipes])

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    setError('')
    setNotice('')
    try {
      const text = await file.text()
      const payload = yaml.load(text)
      if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
        throw new Error('Recipe YAML must be a top-level mapping object.')
      }
      const recipeBody = payload as Record<string, unknown>
      setDraftYamlText(text)
      setDraftBody(recipeBody)
      setDraftFileName(file.name)
      setDraftName(parseRecipeName(recipeBody, file.name))
      setDraftDescription('')
      setUploadDialogOpen(true)
    } catch (exc) {
      setDraftBody(null)
      setDraftYamlText('')
      setDraftFileName('')
      setError(exc instanceof Error ? exc.message : 'Failed to read YAML file.')
    } finally {
      event.target.value = ''
    }
  }

  const handleUpload = async () => {
    if (!workspace) {
      setError('Workspace is required.')
      return
    }
    if (!owner) {
      setError('Owner is required.')
      return
    }
    if (!draftBody || !draftName) {
      setError('Choose a recipe YAML file first.')
      return
    }
    setUploading(true)
    setError('')
    setNotice('')
    try {
      const recipe = await createRecipe(workspace, {
        name: draftName,
        description: draftDescription,
        ownerName: owner,
        recipeBody: draftBody,
        command: 'dj-process --config recipe.yaml',
        scriptPath: draftFileName || draftName,
        parameterSchema: {},
        envTemplate: {},
        executionSpec: {
          taskKind: 'dj_recipe',
          executor: 'dj-process',
          configMode: 'materialize_local_config',
        },
        timeoutSeconds: 7200,
      })
      window.localStorage.setItem(STORAGE_USER_KEY, owner)
      setNotice(`Recipe uploaded: ${recipe.name}`)
      setDraftName('')
      setDraftDescription('')
      setDraftFileName('')
      setDraftYamlText('')
      setDraftBody(null)
      setUploadDialogOpen(false)
      await loadRecipes()
      setSelectedRecipe(recipe)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setUploading(false)
    }
  }

  const resetUploadDraft = () => {
    setDraftName('')
    setDraftDescription('')
    setDraftFileName('')
    setDraftYamlText('')
    setDraftBody(null)
  }

  const handleClickPage = (direction: 'prev' | 'next') => {
    const directionPage = direction === 'next' ? page + 1 : page - 1
    window.scrollTo(0, 0)
    setPage(directionPage)
  }

  const currentYaml =
    selectedRecipe?.currentVersion?.recipeBody &&
    typeof selectedRecipe.currentVersion.recipeBody === 'object'
      ? yamlStringify(selectedRecipe.currentVersion.recipeBody)
      : ''

  const pagedRecipes = recipes.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)

  return (
    <Container maxWidth={'lg'} disableGutters>
      <Box p={2} display={'flex'} justifyContent={'space-between'} alignItems={'center'}>
        <Box display={'flex'}>
          <MqText heading>Recipes</MqText>
          {!loading && (
            <Chip
              size={'small'}
              variant={'outlined'}
              color={'primary'}
              sx={{ marginLeft: 1 }}
              label={recipes.length + ' total'}
            />
          )}
        </Box>
        <Box display={'flex'} alignItems={'center'}>
          {loading && <CircularProgress size={16} />}
          <Select
            size='small'
            displayEmpty
            value={workspace}
            onChange={(event) => {
              const nextWorkspace = event.target.value as string
              setWorkspace(nextWorkspace)
              window.localStorage.setItem(STORAGE_WORKSPACE_KEY, nextWorkspace)
            }}
            sx={{ minWidth: 200, ml: 2 }}
            startAdornment={
              <InputAdornment position='start'>
                <MqText subdued small>
                  ws
                </MqText>
              </InputAdornment>
            }
          >
            {workspace ? <MenuItem value={workspace}>{workspace}</MenuItem> : null}
            {!workspace ? <MenuItem value=''>No workspace</MenuItem> : null}
          </Select>
          <TextField
            size='small'
            label='Owner'
            value={owner}
            onChange={(event) => setOwner(event.target.value)}
            sx={{ minWidth: 160, ml: 2 }}
          />
          <Button variant='outlined' component='label' startIcon={<Add />} sx={{ ml: 2 }}>
            Upload YAML
            <input hidden type='file' accept='.yaml,.yml' onChange={handleFileSelect} />
          </Button>
          <MQTooltip title={'Refresh'}>
            <IconButton
              sx={{ ml: 2 }}
              color={'primary'}
              size={'small'}
              onClick={() => void loadRecipes()}
            >
              <Refresh fontSize={'small'} />
            </IconButton>
          </MQTooltip>
        </Box>
      </Box>

      {error ? (
        <Box px={2} pb={2}>
          <Alert severity='error'>{error}</Alert>
        </Box>
      ) : null}
      {notice ? (
        <Box px={2} pb={2}>
          <Alert severity='success'>{notice}</Alert>
        </Box>
      ) : null}

      <MqScreenLoad
        loading={loading}
        customHeight={`calc(100vh - ${HEADER_HEIGHT}px - ${RECIPE_HEADER_HEIGHT}px)`}
      >
        <>
          {recipes.length === 0 ? (
            <Box p={2}>
              <MqEmpty title='No recipes yet'>
                <>
                  <MqText subdued>
                    Upload a Data-Juicer YAML recipe to create the first reusable processing definition.
                  </MqText>
                  <Button color={'primary'} size={'small'} onClick={() => void loadRecipes()}>
                    Refresh
                  </Button>
                </>
              </MqEmpty>
            </Box>
          ) : (
            <>
              <Table size='small'>
                <TableHead>
                  <TableRow>
                    <TableCell align='left'>
                      <MqText subheading>Name</MqText>
                    </TableCell>
                    <TableCell align='left'>
                      <MqText subheading>Owner</MqText>
                    </TableCell>
                    <TableCell align='left'>
                      <MqText subheading>Lineage Job</MqText>
                    </TableCell>
                    <TableCell align='left'>
                      <MqText subheading>Updated</MqText>
                    </TableCell>
                    <TableCell align='left'>
                      <MqText subheading>Current Version</MqText>
                    </TableCell>
                    <TableCell align='left'>
                      <MqText subheading>YAML</MqText>
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {pagedRecipes.map((recipe) => (
                    <TableRow key={recipe.id}>
                      <TableCell align='left'>
                        <MqText
                          color={'#71ddbf'}
                          onClick={() => {
                            setSelectedRecipe(recipe)
                            setDialogOpen(true)
                          }}
                          sx={{ cursor: 'pointer' }}
                        >
                          {recipe.name}
                        </MqText>
                      </TableCell>
                      <TableCell align='left'>
                        <MqText>{recipe.ownerName}</MqText>
                      </TableCell>
                    <TableCell align='left'>
                      <MqText>{recipe.currentVersion?.scriptPath || 'N/A'}</MqText>
                    </TableCell>
                      <TableCell align='left'>
                        <MqText>{formatUpdatedAt(recipe.updatedAt)}</MqText>
                      </TableCell>
                      <TableCell align='left'>
                        <MqText>
                          {recipe.currentVersion ? `v${recipe.currentVersion.versionNumber}` : 'N/A'}
                        </MqText>
                      </TableCell>
                      <TableCell align='left'>
                        <Button
                          color={'primary'}
                          size={'small'}
                          startIcon={<Visibility />}
                          onClick={() => {
                            setSelectedRecipe(recipe)
                            setDialogOpen(true)
                          }}
                          disabled={!recipe.currentVersion}
                        >
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <MqPaging
                pageSize={PAGE_SIZE}
                currentPage={page}
                totalCount={recipes.length}
                incrementPage={() => handleClickPage('next')}
                decrementPage={() => handleClickPage('prev')}
              />
            </>
          )}
        </>
      </MqScreenLoad>

      <Dialog
        open={uploadDialogOpen}
        onClose={() => {
          if (uploading) {
            return
          }
          setUploadDialogOpen(false)
          resetUploadDraft()
        }}
        maxWidth='md'
        fullWidth
      >
        <DialogTitle>Upload Recipe YAML</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2}>
            <Box
              sx={{
                border: '1px dashed rgba(113,221,191,0.28)',
                borderRadius: 2,
                p: 2,
                backgroundColor: 'rgba(255,255,255,0.03)',
              }}
            >
              <MqText subdued>
                {draftFileName
                  ? `Selected file: ${draftFileName}`
                  : 'Choose a YAML file from the page header to start a new upload.'}
              </MqText>
            </Box>
            <TextField
              size='small'
              label='Recipe Name'
              value={draftName}
              onChange={(event) => setDraftName(event.target.value)}
              disabled={!draftBody}
            />
            <TextField
              size='small'
              label='Description'
              value={draftDescription}
              onChange={(event) => setDraftDescription(event.target.value)}
              disabled={!draftBody}
            />
            {draftYamlText ? (
              <Box
                component='pre'
                sx={{
                  m: 0,
                  p: 2,
                  minHeight: 260,
                  maxHeight: 420,
                  overflow: 'auto',
                  borderRadius: 2,
                  backgroundColor: 'rgba(6,10,12,0.8)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  color: '#d9ffee',
                  fontFamily: '"Source Code Pro", monospace',
                  fontSize: 12,
                  lineHeight: 1.6,
                }}
              >
                {draftYamlText}
              </Box>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button
            onClick={() => {
              setUploadDialogOpen(false)
              resetUploadDraft()
            }}
            disabled={uploading}
          >
            Cancel
          </Button>
          <Button
            variant='contained'
            onClick={() => void handleUpload()}
            disabled={uploading || !draftBody}
          >
            {uploading ? 'Uploading...' : 'Create Recipe'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth='md' fullWidth>
        <DialogTitle>{selectedRecipe?.name || 'Recipe YAML'}</DialogTitle>
        <DialogContent dividers>
          {selectedRecipe?.currentVersion ? (
            <Box mb={2}>
              <MqText small subdued block>
                owner: {selectedRecipe.ownerName}
              </MqText>
              <MqText small subdued block>
                script path: {selectedRecipe.currentVersion.scriptPath}
              </MqText>
              <MqText small subdued block>
                updated {formatUpdatedAt(selectedRecipe.updatedAt)}
              </MqText>
            </Box>
          ) : null}
          <Box
            component='pre'
            sx={{
              m: 0,
              p: 2,
              borderRadius: 2,
              overflow: 'auto',
              backgroundColor: '#081014',
              color: '#dcfff2',
              fontFamily: '"Source Code Pro", monospace',
              fontSize: 13,
              lineHeight: 1.65,
            }}
          >
            {currentYaml || 'No YAML available.'}
          </Box>
        </DialogContent>
      </Dialog>
    </Container>
  )
}

export default Recipes
