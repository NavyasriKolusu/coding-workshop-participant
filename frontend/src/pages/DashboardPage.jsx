import { useCallback, useEffect, useState } from 'react'
import PropTypes from 'prop-types'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  LinearProgress,
  Stack,
  Typography,
} from '@mui/material'
import { useMediaQuery } from 'react-responsive'
import { apiRequest } from '../services/api.js'

const emptyDashboard = {
  status_overview: [],
  projects: [],
  at_risk_projects: [],
  overallocated_members: [],
  budgets: [],
  deliverable_completion: [],
  dependency_chain: [],
}

/** Show portfolio risk, utilization, budget, deliverable and dependency summaries. */
function DashboardPage() {
  const isMobile = useMediaQuery({ maxWidth: 700 })
  const [dashboard, setDashboard] = useState(emptyDashboard)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    try {
      const result = await apiRequest('dashboard')
      setDashboard(result)
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    const fetchDashboard = async () => {
      try {
        const result = await apiRequest('dashboard')
        if (active) {
          setDashboard(result)
          setError('')
        }
      } catch (requestError) {
        if (active) setError(requestError.message)
      } finally {
        if (active) setLoading(false)
      }
    }
    fetchDashboard()
    return () => {
      active = false
    }
  }, [])

  const formatCurrency = (amount) => new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(Number(amount || 0))

  const projectProgress = (project) => Math.round(Number(project.deliverable_progress || 0))

  return (
    <Stack spacing={2}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h5" component="h1">Portfolio overview</Typography>
        <Button onClick={loadDashboard} disabled={loading}>Refresh</Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {loading && <Typography role="status">Loading dashboard...</Typography>}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, minmax(0, 1fr))',
          gap: 2,
        }}
      >
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Project status</Typography>
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
              {dashboard.status_overview.map((item) => (
                <Chip
                  key={item.status}
                  label={`${item.status.replace('_', ' ')}: ${item.project_count}`}
                  color={item.status === 'active' ? 'primary' : 'default'}
                />
              ))}
              {dashboard.status_overview.length === 0 && <Typography>No projects yet.</Typography>}
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Projects at risk</Typography>
            {dashboard.at_risk_projects.length === 0 ? (
              <Typography color="text.secondary">No projects currently meet the risk criteria.</Typography>
            ) : (
              <Stack spacing={1}>
                {dashboard.at_risk_projects.map((project) => (
                  <Box key={project.id}>
                    <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between' }}>
                      <Typography fontWeight={600}>{project.name}</Typography>
                      <Chip size="small" color="error" label="At risk" />
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      Due {project.end_date || 'date not set'} - {projectProgress(project)}% deliverable progress
                      {Number(project.overdue_deliverables) > 0
                        ? ` - ${project.overdue_deliverables} overdue deliverable(s)`
                        : ''}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Over-allocated team members</Typography>
            {dashboard.overallocated_members.length === 0 ? (
              <Typography color="text.secondary">No members are allocated above 100%.</Typography>
            ) : (
              <Stack spacing={1}>
                {dashboard.overallocated_members.map((member) => (
                  <Stack key={member.id} direction="row" spacing={1} sx={{ justifyContent: 'space-between' }}>
                    <Box>
                      <Typography fontWeight={600}>{member.name}</Typography>
                      <Typography variant="body2" color="text.secondary">{member.department}</Typography>
                    </Box>
                    <Chip color="error" label={`${Number(member.allocation_total)}%`} />
                  </Stack>
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Budget spent vs planned</Typography>
            <Stack spacing={1.5}>
              {dashboard.budgets.map((budget) => {
                const planned = Number(budget.planned)
                const spent = Number(budget.spent)
                const percentage = planned > 0 ? Math.min((spent / planned) * 100, 100) : 0
                return (
                  <Box key={budget.project_id}>
                    <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between' }}>
                      <Typography fontWeight={600}>{budget.project_name}</Typography>
                      <Typography variant="body2">{formatCurrency(spent)} / {formatCurrency(planned)}</Typography>
                    </Stack>
                    <LinearProgress variant="determinate" value={percentage} color={spent > planned ? 'error' : 'primary'} />
                  </Box>
                )
              })}
              {dashboard.budgets.length === 0 && <Typography>No budget entries yet.</Typography>}
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Deliverable completion</Typography>
            <Stack spacing={1.5}>
              {dashboard.deliverable_completion.map((project) => (
                <Box key={project.id}>
                  <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between' }}>
                    <Typography fontWeight={600}>{project.name}</Typography>
                    <Typography variant="body2">
                      {project.deliverable_completed}/{project.deliverable_total} complete
                    </Typography>
                  </Stack>
                  <LinearProgress variant="determinate" value={projectProgress(project)} />
                </Box>
              ))}
              {dashboard.deliverable_completion.length === 0 && <Typography>No deliverables yet.</Typography>}
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Dependency chain</Typography>
            {dashboard.dependency_chain.length === 0 ? (
              <Typography color="text.secondary">No deliverables are defined.</Typography>
            ) : (
              <Stack spacing={1}>
                {dashboard.dependency_chain.map((item) => (
                  <Box key={item.deliverable_id}>
                    <Typography fontWeight={600}>{item.deliverable_name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {item.project_name}
                      {item.depends_on.length ? ` - depends on: ${item.depends_on.join(', ')}` : ' - no dependencies'}
                    </Typography>
                    <Divider sx={{ mt: 1 }} />
                  </Box>
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>
      </Box>
    </Stack>
  )
}

DashboardPage.propTypes = {}

export default DashboardPage
