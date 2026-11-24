import { useCallback, useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
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
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import { useMediaQuery } from 'react-responsive'
import { apiRequest, queryString } from '../services/api.js'

const emptyMember = {
  name: '',
  email: '',
  department: '',
  title: '',
  status: 'active',
}
const emptyAllocation = { member_id: '', project_id: '', allocation_percent: '' }

const memberShape = PropTypes.shape({
  id: PropTypes.number.isRequired,
  name: PropTypes.string.isRequired,
  email: PropTypes.string.isRequired,
  department: PropTypes.string.isRequired,
  title: PropTypes.string,
  status: PropTypes.string.isRequired,
  allocation_total: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
})
const allocationShape = PropTypes.shape({
  id: PropTypes.number.isRequired,
  member_id: PropTypes.number.isRequired,
  member_name: PropTypes.string.isRequired,
  project_id: PropTypes.number.isRequired,
  project_name: PropTypes.string.isRequired,
  allocation_percent: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
  member_allocation_total: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
})

/** Manage team members and project allocations. */
function TeamPage() {
  const isMobile = useMediaQuery({ maxWidth: 700 })
  const [members, setMembers] = useState([])
  const [allocations, setAllocations] = useState([])
  const [projects, setProjects] = useState([])
  const [activeTab, setActiveTab] = useState(0)
  const [filters, setFilters] = useState({ search: '', status: '', department: '' })
  const [memberDialogOpen, setMemberDialogOpen] = useState(false)
  const [allocationDialogOpen, setAllocationDialogOpen] = useState(false)
  const [editingMember, setEditingMember] = useState(null)
  const [editingAllocation, setEditingAllocation] = useState(null)
  const [memberForm, setMemberForm] = useState(emptyMember)
  const [allocationForm, setAllocationForm] = useState(emptyAllocation)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const filtersQuery = queryString(filters)
      const [memberData, allocationData, projectData] = await Promise.all([
        apiRequest('team_members', filtersQuery),
        apiRequest('allocations', filtersQuery),
        apiRequest('projects'),
      ])
      setMembers(memberData)
      setAllocations(allocationData)
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
        const [memberData, allocationData, projectData] = await Promise.all([
          apiRequest('team_members', filtersQuery),
          apiRequest('allocations', filtersQuery),
          apiRequest('projects'),
        ])
        if (active) {
          setMembers(memberData)
          setAllocations(allocationData)
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

  const openMemberForm = (member = null) => {
    setEditingMember(member)
    setMemberForm(member ? { ...emptyMember, ...member } : emptyMember)
    setMemberDialogOpen(true)
  }

  const saveMember = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await apiRequest(
        'team_members',
        editingMember ? `/${editingMember.id}` : '',
        { method: editingMember ? 'PUT' : 'POST', body: memberForm },
      )
      setMemberDialogOpen(false)
      setMessage(editingMember ? 'Team member updated.' : 'Team member added.')
      await loadData()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  const deleteMember = async (member) => {
    try {
      await apiRequest('team_members', `/${member.id}`, { method: 'DELETE' })
      setMessage('Team member deleted.')
      await loadData()
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  const openAllocationForm = (allocation = null) => {
    setEditingAllocation(allocation)
    setAllocationForm(allocation
      ? {
        member_id: allocation.member_id,
        project_id: allocation.project_id,
        allocation_percent: allocation.allocation_percent,
      }
      : emptyAllocation)
    setAllocationDialogOpen(true)
  }

  const saveAllocation = async (event) => {
    event.preventDefault()
    setSaving(true)
    try {
      await apiRequest(
        'allocations',
        editingAllocation ? `/${editingAllocation.id}` : '',
        {
          method: editingAllocation ? 'PUT' : 'POST',
          body: {
            ...allocationForm,
            member_id: Number(allocationForm.member_id),
            project_id: Number(allocationForm.project_id),
            allocation_percent: Number(allocationForm.allocation_percent),
          },
        },
      )
      setAllocationDialogOpen(false)
      setMessage(editingAllocation ? 'Allocation updated.' : 'Allocation added.')
      await loadData()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  const deleteAllocation = async (allocation) => {
    try {
      await apiRequest('allocations', `/${allocation.id}`, { method: 'DELETE' })
      setMessage('Allocation deleted.')
      await loadData()
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <Stack spacing={2}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField
          label="Search team and allocations"
          value={filters.search}
          onChange={(event) => setFilters({ ...filters, search: event.target.value })}
          fullWidth
        />
        <FormControl sx={{ minWidth: 160 }}>
          <InputLabel id="team-status-label">Status</InputLabel>
          <Select
            labelId="team-status-label"
            label="Status"
            value={filters.status}
            onChange={(event) => setFilters({ ...filters, status: event.target.value })}
          >
            <MenuItem value="">All statuses</MenuItem>
            {['active', 'inactive', 'planning', 'on_hold', 'completed'].map((status) => (
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
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {loading && <Typography role="status">Loading team data...</Typography>}
      <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)} variant="scrollable">
        <Tab label={`Team members (${members.length})`} />
        <Tab label={`Allocations (${allocations.length})`} />
      </Tabs>
      {activeTab === 0 && (
        <Stack spacing={2}>
          <Box>
            <Button variant="contained" onClick={() => openMemberForm()}>Add team member</Button>
          </Box>
          {members.length === 0 && !loading && <Alert severity="info">No team members match these filters.</Alert>}
          {isMobile ? (
            <Stack spacing={1}>
              {members.map((member) => (
                <MemberCard
                  key={member.id}
                  member={member}
                  onEdit={() => openMemberForm(member)}
                  onDelete={() => deleteMember(member)}
                />
              ))}
            </Stack>
          ) : (
            <TableContainer component={Card}>
              <Table aria-label="Team members">
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Department</TableCell>
                    <TableCell>Title</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Allocation</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {members.map((member) => (
                    <TableRow key={member.id}>
                      <TableCell>
                        <Typography fontWeight={600}>{member.name}</Typography>
                        <Typography variant="body2" color="text.secondary">{member.email}</Typography>
                      </TableCell>
                      <TableCell>{member.department}</TableCell>
                      <TableCell>{member.title}</TableCell>
                      <TableCell>{member.status}</TableCell>
                      <TableCell><AllocationTotal value={member.allocation_total} /></TableCell>
                      <TableCell align="right">
                        <Button onClick={() => openMemberForm(member)}>Edit</Button>
                        <Button color="error" onClick={() => deleteMember(member)}>Delete</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Stack>
      )}
      {activeTab === 1 && (
        <Stack spacing={2}>
          <Box>
            <Button variant="contained" onClick={() => openAllocationForm()}>Add allocation</Button>
          </Box>
          {allocations.length === 0 && !loading && <Alert severity="info">No allocations match these filters.</Alert>}
          {isMobile ? (
            <Stack spacing={1}>
              {allocations.map((allocation) => (
                <AllocationCard
                  key={allocation.id}
                  allocation={allocation}
                  onEdit={() => openAllocationForm(allocation)}
                  onDelete={() => deleteAllocation(allocation)}
                />
              ))}
            </Stack>
          ) : (
            <TableContainer component={Card}>
              <Table aria-label="Project allocations">
                <TableHead>
                  <TableRow>
                    <TableCell>Team member</TableCell>
                    <TableCell>Department</TableCell>
                    <TableCell>Project</TableCell>
                    <TableCell>Project status</TableCell>
                    <TableCell>Allocation</TableCell>
                    <TableCell>Member total</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {allocations.map((allocation) => (
                    <TableRow key={allocation.id}>
                      <TableCell>{allocation.member_name}</TableCell>
                      <TableCell>{allocation.department}</TableCell>
                      <TableCell>{allocation.project_name}</TableCell>
                      <TableCell>{allocation.project_status.replace('_', ' ')}</TableCell>
                      <TableCell>{allocation.allocation_percent}%</TableCell>
                      <TableCell><AllocationTotal value={allocation.member_allocation_total} /></TableCell>
                      <TableCell align="right">
                        <Button onClick={() => openAllocationForm(allocation)}>Edit</Button>
                        <Button color="error" onClick={() => deleteAllocation(allocation)}>Delete</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Stack>
      )}

      <Dialog open={memberDialogOpen} onClose={() => setMemberDialogOpen(false)} fullWidth maxWidth="sm">
        <Box component="form" onSubmit={saveMember}>
          <DialogTitle>{editingMember ? 'Edit team member' : 'Add team member'}</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField label="Name" value={memberForm.name} onChange={(event) => setMemberForm({ ...memberForm, name: event.target.value })} required autoFocus />
              <TextField label="Email" type="email" value={memberForm.email} onChange={(event) => setMemberForm({ ...memberForm, email: event.target.value })} required />
              <TextField label="Department" value={memberForm.department} onChange={(event) => setMemberForm({ ...memberForm, department: event.target.value })} required />
              <TextField label="Title" value={memberForm.title} onChange={(event) => setMemberForm({ ...memberForm, title: event.target.value })} />
              <FormControl>
                <InputLabel id="member-status-form-label">Status</InputLabel>
                <Select
                  labelId="member-status-form-label"
                  label="Status"
                  value={memberForm.status}
                  onChange={(event) => setMemberForm({ ...memberForm, status: event.target.value })}
                >
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="inactive">Inactive</MenuItem>
                </Select>
              </FormControl>
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setMemberDialogOpen(false)}>Cancel</Button>
            <Button type="submit" variant="contained" disabled={saving}>{saving ? 'Saving...' : 'Save'}</Button>
          </DialogActions>
        </Box>
      </Dialog>

      <Dialog open={allocationDialogOpen} onClose={() => setAllocationDialogOpen(false)} fullWidth maxWidth="sm">
        <Box component="form" onSubmit={saveAllocation}>
          <DialogTitle>{editingAllocation ? 'Edit allocation' : 'Add allocation'}</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <FormControl required>
                <InputLabel id="allocation-member-label">Team member</InputLabel>
                <Select
                  labelId="allocation-member-label"
                  label="Team member"
                  value={allocationForm.member_id}
                  onChange={(event) => setAllocationForm({ ...allocationForm, member_id: event.target.value })}
                >
                  {members.map((member) => (
                    <MenuItem key={member.id} value={member.id}>{member.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl required>
                <InputLabel id="allocation-project-label">Project</InputLabel>
                <Select
                  labelId="allocation-project-label"
                  label="Project"
                  value={allocationForm.project_id}
                  onChange={(event) => setAllocationForm({ ...allocationForm, project_id: event.target.value })}
                >
                  {projects.map((project) => (
                    <MenuItem key={project.id} value={project.id}>{project.name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                label="Allocation percent"
                type="number"
                value={allocationForm.allocation_percent}
                onChange={(event) => setAllocationForm({ ...allocationForm, allocation_percent: event.target.value })}
                inputProps={{ min: 1, max: 100, step: 1 }}
                required
              />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setAllocationDialogOpen(false)}>Cancel</Button>
            <Button type="submit" variant="contained" disabled={saving}>{saving ? 'Saving...' : 'Save'}</Button>
          </DialogActions>
        </Box>
      </Dialog>
      <Snackbar open={Boolean(message)} autoHideDuration={3500} onClose={() => setMessage('')}>
        <Alert severity="success" onClose={() => setMessage('')}>{message}</Alert>
      </Snackbar>
    </Stack>
  )
}

/** Display the combined allocation and flag totals above 100 percent. */
function AllocationTotal({ value }) {
  const total = Number(value || 0)
  return (
    <Chip
      label={`${total}%`}
      color={total > 100 ? 'error' : 'default'}
      aria-label={total > 100 ? `Over-allocated: ${total}%` : `Allocated: ${total}%`}
    />
  )
}

function MemberCard({ member, onEdit, onDelete }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">{member.name}</Typography>
        <Typography color="text.secondary">{member.email}</Typography>
        <Typography>{member.department} - {member.title}</Typography>
        <Typography>Status: {member.status}</Typography>
        <AllocationTotal value={member.allocation_total} />
      </CardContent>
      <CardActions>
        <Button onClick={onEdit}>Edit</Button>
        <Button color="error" onClick={onDelete}>Delete</Button>
      </CardActions>
    </Card>
  )
}

function AllocationCard({ allocation, onEdit, onDelete }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">{allocation.member_name}</Typography>
        <Typography color="text.secondary">{allocation.project_name}</Typography>
        <Typography>Allocation: {allocation.allocation_percent}%</Typography>
        <Typography>Member total: {allocation.member_allocation_total}%</Typography>
        <AllocationTotal value={allocation.member_allocation_total} />
      </CardContent>
      <CardActions>
        <Button onClick={onEdit}>Edit</Button>
        <Button color="error" onClick={onDelete}>Delete</Button>
      </CardActions>
    </Card>
  )
}

AllocationTotal.propTypes = { value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]) }
MemberCard.propTypes = { member: memberShape.isRequired, onEdit: PropTypes.func.isRequired, onDelete: PropTypes.func.isRequired }
AllocationCard.propTypes = { allocation: allocationShape.isRequired, onEdit: PropTypes.func.isRequired, onDelete: PropTypes.func.isRequired }
TeamPage.propTypes = {}

export default TeamPage
