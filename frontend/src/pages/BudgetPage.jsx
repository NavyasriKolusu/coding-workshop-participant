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

const emptyEntry = {
  project_id: '',
  category: '',
  description: '',
  entry_type: 'planned',
  amount: '',
  entry_date: '',
}

const entryShape = PropTypes.shape({
  id: PropTypes.number.isRequired,
  project_id: PropTypes.number.isRequired,
  project_name: PropTypes.string.isRequired,
  department: PropTypes.string,
  category: PropTypes.string.isRequired,
  description: PropTypes.string,
  entry_type: PropTypes.string.isRequired,
  amount: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
  entry_date: PropTypes.string,
})

/** Create and maintain planned and spent project budget entries. */
function BudgetPage() {
  const isMobile = useMediaQuery({ maxWidth: 700 })
  const [entries, setEntries] = useState([])
  const [projects, setProjects] = useState([])
  const [filters, setFilters] = useState({ search: '', status: '', department: '' })
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingEntry, setEditingEntry] = useState(null)
  const [form, setForm] = useState(emptyEntry)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadData = useCallback(async () => {
    try {
      const filtersQuery = queryString(filters)
      const [entryData, projectData] = await Promise.all([
        apiRequest('budget_entries', filtersQuery),
        apiRequest('projects'),
      ])
      setEntries(entryData)
      setProjects(projectData)
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
        const [entryData, projectData] = await Promise.all([
          apiRequest('budget_entries', filtersQuery),
          apiRequest('projects'),
        ])
        if (active) {
          setEntries(entryData)
          setProjects(projectData)
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

  const openForm = (entry = null) => {
    setEditingEntry(entry)
    setForm(entry
      ? {
        project_id: entry.project_id,
        category: entry.category,
        description: entry.description || '',
        entry_type: entry.entry_type,
        amount: entry.amount,
        entry_date: entry.entry_date || '',
      }
      : emptyEntry)
    setDialogOpen(true)
  }

  const saveEntry = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await apiRequest(
        'budget_entries',
        editingEntry ? `/${editingEntry.id}` : '',
        {
          method: editingEntry ? 'PUT' : 'POST',
          body: {
            ...form,
            project_id: Number(form.project_id),
            amount: Number(form.amount),
          },
        },
      )
      setDialogOpen(false)
      setMessage(editingEntry ? 'Budget entry updated.' : 'Budget entry added.')
      await loadData()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  const deleteEntry = async (entry) => {
    try {
      await apiRequest('budget_entries', `/${entry.id}`, { method: 'DELETE' })
      setMessage('Budget entry deleted.')
      await loadData()
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  const formatAmount = (value) => new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(Number(value))

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField
          label="Search budgets"
          value={filters.search}
          onChange={(event) => setFilters({ ...filters, search: event.target.value })}
          fullWidth
        />
        <FormControl sx={{ minWidth: 160 }}>
          <InputLabel id="budget-status-label">Type</InputLabel>
          <Select
            labelId="budget-status-label"
            label="Type"
            value={filters.status}
            onChange={(event) => setFilters({ ...filters, status: event.target.value })}
          >
            <MenuItem value="">Planned and spent</MenuItem>
            <MenuItem value="planned">Planned</MenuItem>
            <MenuItem value="spent">Spent</MenuItem>
          </Select>
        </FormControl>
        <TextField
          label="Department"
          value={filters.department}
          onChange={(event) => setFilters({ ...filters, department: event.target.value })}
          sx={{ minWidth: 170 }}
        />
        <Button variant="contained" onClick={() => openForm()} sx={{ minWidth: 150 }}>
          Add budget entry
        </Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {loading && <Typography role="status">Loading budget entries...</Typography>}
      {!loading && entries.length === 0 && <Alert severity="info">No budget entries match these filters.</Alert>}
      {!loading && entries.length > 0 && (isMobile ? (
        <Stack spacing={1}>
          {entries.map((entry) => (
            <BudgetCard
              key={entry.id}
              entry={entry}
              formatAmount={formatAmount}
              onEdit={() => openForm(entry)}
              onDelete={() => deleteEntry(entry)}
            />
          ))}
        </Stack>
      ) : (
        <TableContainer component={Card}>
          <Table aria-label="Budget entries">
            <TableHead>
              <TableRow>
                <TableCell>Project</TableCell>
                <TableCell>Category</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Amount</TableCell>
                <TableCell>Date</TableCell>
                <TableCell>Department</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entries.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell>
                    <Typography fontWeight={600}>{entry.project_name}</Typography>
                    <Typography variant="body2" color="text.secondary">{entry.description}</Typography>
                  </TableCell>
                  <TableCell>{entry.category}</TableCell>
                  <TableCell>{entry.entry_type}</TableCell>
                  <TableCell>{formatAmount(entry.amount)}</TableCell>
                  <TableCell>{entry.entry_date || '-'}</TableCell>
                  <TableCell>{entry.department}</TableCell>
                  <TableCell align="right">
                    <Button onClick={() => openForm(entry)}>Edit</Button>
                    <Button color="error" onClick={() => deleteEntry(entry)}>Delete</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ))}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <Box component="form" onSubmit={saveEntry}>
          <DialogTitle>{editingEntry ? 'Edit budget entry' : 'Add budget entry'}</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <FormControl required>
                <InputLabel id="budget-project-label">Project</InputLabel>
                <Select
                  labelId="budget-project-label"
                  label="Project"
                  value={form.project_id}
                  onChange={(event) => setForm({ ...form, project_id: event.target.value })}
                >
                  {projects.map((project) => (
                    <MenuItem key={project.id} value={project.id}>{project.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField label="Category" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} required />
              <TextField label="Description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} multiline minRows={2} />
              <FormControl>
                <InputLabel id="budget-entry-type-label">Type</InputLabel>
                <Select
                  labelId="budget-entry-type-label"
                  label="Type"
                  value={form.entry_type}
                  onChange={(event) => setForm({ ...form, entry_type: event.target.value })}
                >
                  <MenuItem value="planned">Planned</MenuItem>
                  <MenuItem value="spent">Spent</MenuItem>
                </Select>
              </FormControl>
              <TextField
                label="Amount (USD)"
                type="number"
                value={form.amount}
                onChange={(event) => setForm({ ...form, amount: event.target.value })}
                inputProps={{ min: 0, step: 0.01 }}
                required
              />
              <TextField
                label="Date"
                type="date"
                value={form.entry_date}
                onChange={(event) => setForm({ ...form, entry_date: event.target.value })}
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

function BudgetCard({ entry, formatAmount, onEdit, onDelete }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">{entry.project_name}</Typography>
        <Typography color="text.secondary">{entry.category} - {entry.entry_type}</Typography>
        <Typography variant="h5" sx={{ mt: 1 }}>{formatAmount(entry.amount)}</Typography>
        <Typography>{entry.department} - {entry.entry_date || 'No date'}</Typography>
        <Typography>{entry.description}</Typography>
      </CardContent>
      <CardActions>
        <Button onClick={onEdit}>Edit</Button>
        <Button color="error" onClick={onDelete}>Delete</Button>
      </CardActions>
    </Card>
  )
}

BudgetCard.propTypes = {
  entry: entryShape.isRequired,
  formatAmount: PropTypes.func.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
}
BudgetPage.propTypes = {}

export default BudgetPage
