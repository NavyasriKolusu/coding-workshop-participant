import { useCallback, useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  LinearProgress,
  ListItemText,
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

const emptyDeliverable = {
  project_id: '',
  name: '',
  description: '',
  status: 'not_started',
  progress: 0,
  due_date: '',
  assigned_to: '',
  depends_on: [],
}

const deliverableShape = PropTypes.shape({
  id: PropTypes.number.isRequired,
  project_id: PropTypes.number.isRequired,
  project_name: PropTypes.string.isRequired,
  project_department: PropTypes.string,
  name: PropTypes.string.isRequired,
  description: PropTypes.string,
  status: PropTypes.string.isRequired,
  progress: PropTypes.number.isRequired,
  due_date: PropTypes.string,
  assigned_to: PropTypes.number,
  assigned_member_name: PropTypes.string,
  depends_on_ids: PropTypes.arrayOf(PropTypes.number),
  dependency_names: PropTypes.arrayOf(PropTypes.string),
})

/** Manage project deliverables and their dependency chain. */
function DeliverablesPage() {
  const isMobile = useMediaQuery({ maxWidth: 700 })
  const [deliverables, setDeliverables] = useState([])
  const [allDeliverables, setAllDeliverables] = useState([])
  const [projects, setProjects] = useState([])
  const [members, setMembers] = useState([])
  const [filters, setFilters] = useState({ search: '', status: '', department: '' })
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingDeliverable, setEditingDeliverable] = useState(null)
  const [form, setForm] = useState(emptyDeliverable)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadData = useCallback(async () => {
    try {
      const filtersQuery = queryString(filters)
      const [deliverableData, allData, projectData, memberData] = await Promise.all([
        apiRequest('deliverables', filtersQuery),
        apiRequest('deliverables'),
        apiRequest('projects'),
        apiRequest('team_members', '?status=active'),
      ])
      setDeliverables(deliverableData)
      setAllDeliverables(allData)
      setProjects(projectData)
      setMembers(memberData)
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    let active = true
    const fetchData = async () => {
      try {
        const filtersQuery = queryString(filters)
        const [deliverableData, allData, projectData, memberData] = await Promise.all([
          apiRequest('deliverables', filtersQuery),
          apiRequest('deliverables'),
          apiRequest('projects'),
          apiRequest('team_members', '?status=active'),
        ])
        if (active) {
          setDeliverables(deliverableData)
          setAllDeliverables(allData)
          setProjects(projectData)
          setMembers(memberData)
          setError('')
        }
      } catch (requestError) {
        if (active) setError(requestError.message)
      } finally {
        if (active) setLoading(false)
      }
    }
    fetchData()
    return () => {
      active = false
    }
  }, [filters])

  const openForm = (deliverable = null) => {
    setEditingDeliverable(deliverable)
    setForm(deliverable
      ? {
        project_id: deliverable.project_id,
        name: deliverable.name,
        description: deliverable.description || '',
        status: deliverable.status,
        progress: deliverable.progress,
        due_date: deliverable.due_date || '',
        assigned_to: deliverable.assigned_to || '',
        depends_on: deliverable.depends_on_ids || [],
      }
      : emptyDeliverable)
    setDialogOpen(true)
  }

  const saveDeliverable = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await apiRequest(
        'deliverables',
        editingDeliverable ? `/${editingDeliverable.id}` : '',
        {
          method: editingDeliverable ? 'PUT' : 'POST',
          body: {
            ...form,
            project_id: Number(form.project_id),
            progress: Number(form.progress),
            assigned_to: form.assigned_to ? Number(form.assigned_to) : null,
            depends_on: form.depends_on.map(Number),
          },
        },
      )
      setDialogOpen(false)
      setMessage(editingDeliverable ? 'Deliverable updated.' : 'Deliverable created.')
      await loadData()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  const deleteDeliverable = async (deliverable) => {
    try {
      await apiRequest('deliverables', `/${deliverable.id}`, { method: 'DELETE' })
      setMessage('Deliverable deleted.')
      await loadData()
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField
          label="Search deliverables"
          value={filters.search}
          onChange={(event) => setFilters({ ...filters, search: event.target.value })}
          fullWidth
        />
        <FormControl sx={{ minWidth: 170 }}>
          <InputLabel id="deliverable-status-label">Status</InputLabel>
          <Select
            labelId="deliverable-status-label"
            label="Status"
            value={filters.status}
            onChange={(event) => setFilters({ ...filters, status: event.target.value })}
          >
            <MenuItem value="">All statuses</MenuItem>
            {['not_started', 'in_progress', 'completed'].map((status) => (
              <MenuItem key={status} value={status}>{status.replace('_', ' ')}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          label="Department"
          value={filters.department}
          onChange={(event) => setFilters({ ...filters, department: event.target.value })}
          sx={{ minWidth: 170 }}
        />
        <Button variant="contained" onClick={() => openForm()} sx={{ minWidth: 155 }}>
          Add deliverable
        </Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {loading && <Typography role="status">Loading deliverables...</Typography>}
      {!loading && deliverables.length === 0 && (
        <Alert severity="info">No deliverables match these filters.</Alert>
      )}
      {!loading && deliverables.length > 0 && (isMobile ? (
        <Stack spacing={1}>
          {deliverables.map((deliverable) => (
            <DeliverableCard
              key={deliverable.id}
              deliverable={deliverable}
              onEdit={() => openForm(deliverable)}
              onDelete={() => deleteDeliverable(deliverable)}
            />
          ))}
        </Stack>
      ) : (
        <TableContainer component={Card}>
          <Table aria-label="Deliverables">
            <TableHead>
              <TableRow>
                <TableCell>Deliverable</TableCell>
                <TableCell>Project</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Progress</TableCell>
                <TableCell>Due date</TableCell>
                <TableCell>Depends on</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {deliverables.map((deliverable) => (
                <TableRow key={deliverable.id}>
                  <TableCell>
                    <Typography fontWeight={600}>{deliverable.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {deliverable.assigned_member_name || 'Unassigned'}
                    </Typography>
                  </TableCell>
                  <TableCell>{deliverable.project_name}</TableCell>
                  <TableCell>{deliverable.status.replace('_', ' ')}</TableCell>
                  <TableCell sx={{ minWidth: 130 }}>
                    <Typography variant="body2">{deliverable.progress}%</Typography>
                    <LinearProgress variant="determinate" value={deliverable.progress} />
                  </TableCell>
                  <TableCell>{deliverable.due_date || '-'}</TableCell>
                  <TableCell>{(deliverable.dependency_names || []).join(', ') || '-'}</TableCell>
                  <TableCell align="right">
                    <Button onClick={() => openForm(deliverable)}>Edit</Button>
                    <Button color="error" onClick={() => deleteDeliverable(deliverable)}>Delete</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ))}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <Box component="form" onSubmit={saveDeliverable}>
          <DialogTitle>{editingDeliverable ? 'Edit deliverable' : 'Add deliverable'}</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <FormControl required>
                <InputLabel id="deliverable-project-label">Project</InputLabel>
                <Select
                  labelId="deliverable-project-label"
                  label="Project"
                  value={form.project_id}
                  onChange={(event) => setForm({ ...form, project_id: event.target.value })}
                >
                  {projects.map((project) => (
                    <MenuItem key={project.id} value={project.id}>{project.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField label="Name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required autoFocus />
              <TextField label="Description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} multiline minRows={2} />
              <FormControl>
                <InputLabel id="deliverable-form-status-label">Status</InputLabel>
                <Select
                  labelId="deliverable-form-status-label"
                  label="Status"
                  value={form.status}
                  onChange={(event) => setForm({ ...form, status: event.target.value })}
                >
                  {['not_started', 'in_progress', 'completed'].map((status) => (
                    <MenuItem key={status} value={status}>{status.replace('_', ' ')}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                label="Progress percent"
                type="number"
                value={form.progress}
                onChange={(event) => setForm({ ...form, progress: event.target.value })}
                inputProps={{ min: 0, max: 100, step: 1 }}
              />
              <TextField
                label="Due date"
                type="date"
                value={form.due_date}
                onChange={(event) => setForm({ ...form, due_date: event.target.value })}
                slotProps={{ inputLabel: { shrink: true } }}
              />
              <FormControl>
                <InputLabel id="deliverable-member-label">Assigned member</InputLabel>
                <Select
                  labelId="deliverable-member-label"
                  label="Assigned member"
                  value={form.assigned_to}
                  onChange={(event) => setForm({ ...form, assigned_to: event.target.value })}
                >
                  <MenuItem value="">Unassigned</MenuItem>
                  {members.map((member) => (
                    <MenuItem key={member.id} value={member.id}>{member.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl>
                <InputLabel id="deliverable-dependencies-label">Depends on</InputLabel>
                <Select
                  multiple
                  labelId="deliverable-dependencies-label"
                  label="Depends on"
                  value={form.depends_on}
                  onChange={(event) => setForm({ ...form, depends_on: event.target.value })}
                  renderValue={(selected) => selected
                    .map((id) => allDeliverables.find((item) => item.id === Number(id))?.name || `#${id}`)
                    .join(', ')}
                >
                  {allDeliverables
                    .filter((item) => item.id !== editingDeliverable?.id)
                    .map((item) => (
                      <MenuItem key={item.id} value={item.id}>
                        <Checkbox checked={form.depends_on.map(Number).includes(item.id)} />
                        <ListItemText primary={item.name} secondary={item.project_name} />
                      </MenuItem>
                    ))}
                </Select>
              </FormControl>
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

function DeliverableCard({ deliverable, onEdit, onDelete }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">{deliverable.name}</Typography>
        <Typography color="text.secondary">{deliverable.project_name}</Typography>
        <Typography>Status: {deliverable.status.replace('_', ' ')}</Typography>
        <Typography>Due: {deliverable.due_date || '-'}</Typography>
        <Typography>Assigned: {deliverable.assigned_member_name || 'Unassigned'}</Typography>
        <Typography>Depends on: {(deliverable.dependency_names || []).join(', ') || 'None'}</Typography>
        <Typography sx={{ mt: 1 }}>{deliverable.progress}% complete</Typography>
        <LinearProgress variant="determinate" value={deliverable.progress} />
      </CardContent>
      <CardActions>
        <Button onClick={onEdit}>Edit</Button>
        <Button color="error" onClick={onDelete}>Delete</Button>
      </CardActions>
    </Card>
  )
}

DeliverableCard.propTypes = {
  deliverable: deliverableShape.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
}
DeliverablesPage.propTypes = {}

export default DeliverablesPage
