import { useCallback, useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import { useMediaQuery } from 'react-responsive'
import { apiRequest, queryString } from '../services/api.js'

const emptyProject = {
  name: '',
  description: '',
  status: 'planning',
  department: '',
  start_date: '',
  end_date: '',
}

const projectShape = PropTypes.shape({
  id: PropTypes.number.isRequired,
  name: PropTypes.string.isRequired,
  description: PropTypes.string,
  status: PropTypes.string.isRequired,
  department: PropTypes.string,
  start_date: PropTypes.string,
  end_date: PropTypes.string,
})

/** Display and manage projects with search and status/department filters. */
function ProjectsPage() {
  const isMobile = useMediaQuery({ maxWidth: 700 })
  const [projects, setProjects] = useState([])
  const [filters, setFilters] = useState({ search: '', status: '', department: '' })
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingProject, setEditingProject] = useState(null)
  const [form, setForm] = useState(emptyProject)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadProjects = useCallback(async () => {
    try {
      const result = await apiRequest('projects', queryString(filters))
      setProjects(result)
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    let active = true
    const fetchProjects = async () => {
      try {
        const result = await apiRequest('projects', queryString(filters))
        if (active) {
          setProjects(result)
          setError('')
        }
      } catch (requestError) {
        if (active) setError(requestError.message)
      } finally {
        if (active) setLoading(false)
      }
    }
    fetchProjects()
    return () => {
      active = false
    }
  }, [filters])

  const openForm = (project = null) => {
    setEditingProject(project)
    setForm(project ? { ...emptyProject, ...project } : emptyProject)
    setDialogOpen(true)
  }

  const saveProject = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await apiRequest(
        'projects',
        editingProject ? `/${editingProject.id}` : '',
        { method: editingProject ? 'PUT' : 'POST', body: form },
      )
      setDialogOpen(false)
      setMessage(editingProject ? 'Project updated.' : 'Project created.')
      await loadProjects()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  const deleteProject = async (project) => {
    setError('')
    try {
      await apiRequest('projects', `/${project.id}`, { method: 'DELETE' })
      setMessage('Project deleted.')
      await loadProjects()
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  const updateForm = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }))
  }

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
        <TextField
          label="Search projects"
          value={filters.search}
          onChange={(event) => setFilters({ ...filters, search: event.target.value })}
          fullWidth
        />
        <FormControl sx={{ minWidth: 160 }}>
          <InputLabel id="project-status-label">Status</InputLabel>
          <Select
            labelId="project-status-label"
            label="Status"
            value={filters.status}
            onChange={(event) => setFilters({ ...filters, status: event.target.value })}
          >
            <MenuItem value="">All statuses</MenuItem>
            {['planning', 'active', 'on_hold', 'completed'].map((status) => (
              <MenuItem key={status} value={status}>{status.replace('_', ' ')}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          label="Department"
          value={filters.department}
          onChange={(event) => setFilters({ ...filters, department: event.target.value })}
          sx={{ minWidth: 160 }}
        />
        <Button variant="contained" onClick={() => openForm()} sx={{ minWidth: 140 }}>
          Add project
        </Button>
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      {loading && <Typography role="status">Loading projects...</Typography>}
      {!loading && !error && projects.length === 0 && (
        <Alert severity="info">No projects match these filters.</Alert>
      )}

      {!loading && projects.length > 0 && (isMobile ? (
        <Stack spacing={1}>
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onEdit={() => openForm(project)}
              onDelete={() => deleteProject(project)}
            />
          ))}
        </Stack>
      ) : (
        <TableContainer component={Card}>
          <Table aria-label="Projects">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Department</TableCell>
                <TableCell>Start date</TableCell>
                <TableCell>End date</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {projects.map((project) => (
                <TableRow key={project.id}>
                  <TableCell>
                    <Typography fontWeight={600}>{project.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {project.description}
                    </Typography>
                  </TableCell>
                  <TableCell>{project.status.replace('_', ' ')}</TableCell>
                  <TableCell>{project.department}</TableCell>
                  <TableCell>{project.start_date || '-'}</TableCell>
                  <TableCell>{project.end_date || '-'}</TableCell>
                  <TableCell align="right">
                    <Button onClick={() => openForm(project)}>Edit</Button>
                    <Button color="error" onClick={() => deleteProject(project)}>Delete</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ))}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <Box component="form" onSubmit={saveProject}>
          <DialogTitle>{editingProject ? 'Edit project' : 'Add project'}</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField label="Name" value={form.name} onChange={updateForm('name')} required autoFocus />
              <TextField
                label="Description"
                value={form.description}
                onChange={updateForm('description')}
                multiline
                minRows={2}
              />
              <FormControl>
                <InputLabel id="project-form-status-label">Status</InputLabel>
                <Select
                  labelId="project-form-status-label"
                  label="Status"
                  value={form.status}
                  onChange={updateForm('status')}
                >
                  {['planning', 'active', 'on_hold', 'completed'].map((status) => (
                    <MenuItem key={status} value={status}>{status.replace('_', ' ')}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField label="Department" value={form.department} onChange={updateForm('department')} />
              <TextField
                label="Start date"
                type="date"
                value={form.start_date || ''}
                onChange={updateForm('start_date')}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <TextField
                label="End date"
                type="date"
                value={form.end_date || ''}
                onChange={updateForm('end_date')}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button type="submit" variant="contained" disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
      <Snackbar open={Boolean(message)} autoHideDuration={3500} onClose={() => setMessage('')}>
        <Alert severity="success" onClose={() => setMessage('')}>{message}</Alert>
      </Snackbar>
    </Stack>
  )
}

/** Render a project card for small screens. */
function ProjectCard({ project, onEdit, onDelete }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">{project.name}</Typography>
        <Typography color="text.secondary">{project.description}</Typography>
        <Typography sx={{ mt: 1 }}>Status: {project.status.replace('_', ' ')}</Typography>
        <Typography>Department: {project.department || '-'}</Typography>
        <Typography>Ends: {project.end_date || '-'}</Typography>
      </CardContent>
      <CardActions>
        <Button onClick={onEdit}>Edit</Button>
        <Button color="error" onClick={onDelete}>Delete</Button>
      </CardActions>
    </Card>
  )
}

ProjectCard.propTypes = {
  project: projectShape.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
}

ProjectsPage.propTypes = {}

export default ProjectsPage
