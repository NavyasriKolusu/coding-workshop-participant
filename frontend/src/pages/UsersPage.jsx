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

const emptyUser = { username: '', name: '', role: 'member', password: '' }
const userShape = PropTypes.shape({
  id: PropTypes.number.isRequired,
  username: PropTypes.string.isRequired,
  name: PropTypes.string.isRequired,
  role: PropTypes.string.isRequired,
  created_at: PropTypes.string,
})

/** Allow administrators to create and manage application accounts. */
function UsersPage({ currentUser }) {
  const isMobile = useMediaQuery({ maxWidth: 700 })
  const [users, setUsers] = useState([])
  const [filters, setFilters] = useState({ search: '', status: '' })
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [form, setForm] = useState(emptyUser)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadUsers = useCallback(async () => {
    try {
      const usersData = await apiRequest('auth', `/users${queryString(filters)}`)
      setUsers(usersData)
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    let active = true
    const fetchUsers = async () => {
      try {
        const usersData = await apiRequest('auth', `/users${queryString(filters)}`)
        if (active) {
          setUsers(usersData)
          setError('')
        }
      } catch (requestError) {
        if (active) setError(requestError.message)
      } finally {
        if (active) setLoading(false)
      }
    }
    fetchUsers()
    return () => {
      active = false
    }
  }, [filters])

  const openForm = (user = null) => {
    setEditingUser(user)
    setForm(user
      ? { username: user.username, name: user.name, role: user.role, password: '' }
      : emptyUser)
    setDialogOpen(true)
  }

  const saveUser = async (event) => {
    event.preventDefault()
    setSaving(true)
    const body = { ...form }
    if (editingUser && !body.password) delete body.password
    try {
      await apiRequest(
        'auth',
        editingUser ? `/users/${editingUser.id}` : '/users',
        { method: editingUser ? 'PUT' : 'POST', body },
      )
      setDialogOpen(false)
      setMessage(editingUser ? 'User updated.' : 'User created.')
      await loadUsers()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  const deleteUser = async (user) => {
    try {
      await apiRequest('auth', `/users/${user.id}`, { method: 'DELETE' })
      setMessage('User deleted.')
      await loadUsers()
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <Stack spacing={2}>
      <Typography variant="h5" component="h1">User management</Typography>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <TextField
          label="Search users"
          value={filters.search}
          onChange={(event) => setFilters({ ...filters, search: event.target.value })}
          fullWidth
        />
        <FormControl sx={{ minWidth: 160 }}>
          <InputLabel id="user-role-filter-label">Role</InputLabel>
          <Select
            labelId="user-role-filter-label"
            label="Role"
            value={filters.status}
            onChange={(event) => setFilters({ ...filters, status: event.target.value })}
          >
            <MenuItem value="">All roles</MenuItem>
            {['admin', 'manager', 'member'].map((role) => (
              <MenuItem key={role} value={role}>{role}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button variant="contained" onClick={() => openForm()} sx={{ minWidth: 135 }}>
          Add user
        </Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {loading && <Typography role="status">Loading users...</Typography>}
      {!loading && users.length === 0 && <Alert severity="info">No users match these filters.</Alert>}
      {!loading && users.length > 0 && (isMobile ? (
        <Stack spacing={1}>
          {users.map((user) => (
            <UserCard
              key={user.id}
              user={user}
              isCurrentUser={user.id === currentUser.id}
              onEdit={() => openForm(user)}
              onDelete={() => deleteUser(user)}
            />
          ))}
        </Stack>
      ) : (
        <TableContainer component={Card}>
          <Table aria-label="User accounts">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Username</TableCell>
                <TableCell>Role</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>{user.name}</TableCell>
                  <TableCell>{user.username}</TableCell>
                  <TableCell>{user.role}</TableCell>
                  <TableCell align="right">
                    <Button onClick={() => openForm(user)}>Edit</Button>
                    <Button
                      color="error"
                      disabled={user.id === currentUser.id}
                      onClick={() => deleteUser(user)}
                    >
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ))}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <Box component="form" onSubmit={saveUser}>
          <DialogTitle>{editingUser ? 'Edit user' : 'Add user'}</DialogTitle>
          <DialogContent>
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField
                label="Username"
                value={form.username}
                onChange={(event) => setForm({ ...form, username: event.target.value })}
                required
              />
              <TextField
                label="Full name"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
              />
              <FormControl>
                <InputLabel id="user-role-form-label">Role</InputLabel>
                <Select
                  labelId="user-role-form-label"
                  label="Role"
                  value={form.role}
                  onChange={(event) => setForm({ ...form, role: event.target.value })}
                >
                  {['admin', 'manager', 'member'].map((role) => (
                    <MenuItem key={role} value={role}>{role}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                label={editingUser ? 'New password (optional)' : 'Password'}
                type="password"
                value={form.password}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
                required={!editingUser}
                helperText={editingUser ? 'Leave blank to keep the current password.' : 'Use at least 8 characters.'}
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

function UserCard({ user, isCurrentUser, onEdit, onDelete }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">{user.name}</Typography>
        <Typography color="text.secondary">{user.username}</Typography>
        <Typography>Role: {user.role}</Typography>
      </CardContent>
      <CardActions>
        <Button onClick={onEdit}>Edit</Button>
        <Button color="error" disabled={isCurrentUser} onClick={onDelete}>Delete</Button>
      </CardActions>
    </Card>
  )
}

UserCard.propTypes = {
  user: userShape.isRequired,
  isCurrentUser: PropTypes.bool.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
}
UsersPage.propTypes = {
  currentUser: PropTypes.shape({ id: PropTypes.number.isRequired }).isRequired,
}

export default UsersPage
