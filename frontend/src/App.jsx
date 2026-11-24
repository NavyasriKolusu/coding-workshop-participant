import { useState } from 'react'
import { useEffect } from 'react'
import PropTypes from 'prop-types'
import { AppBar, Box, Button, Container, Tab, Tabs, Toolbar, Typography } from '@mui/material'
import { useMediaQuery } from 'react-responsive'
import './App.css'
import { apiRequest } from './services/api.js'
import LoginPage from './pages/LoginPage.jsx'
import ProjectsPage from './pages/ProjectsPage.jsx'
import TeamPage from './pages/TeamPage.jsx'
import DeliverablesPage from './pages/DeliverablesPage.jsx'
import BudgetPage from './pages/BudgetPage.jsx'
import UsersPage from './pages/UsersPage.jsx'

/** Render the ACME project workspace. */
function App() {
  const isMobile = useMediaQuery({ maxWidth: 600 })
  const [user, setUser] = useState(null)
  const [checkingSession, setCheckingSession] = useState(
    () => Boolean(window.localStorage.getItem('acme-token')),
  )
  const [activePage, setActivePage] = useState('projects')

  useEffect(() => {
    let active = true
    const token = window.localStorage.getItem('acme-token')
    if (!token) return undefined

    apiRequest('auth', '/me')
      .then((authenticatedUser) => {
        if (active) setUser(authenticatedUser)
      })
      .catch(() => {
        window.localStorage.removeItem('acme-token')
        window.localStorage.removeItem('acme-user')
      })
      .finally(() => {
        if (active) setCheckingSession(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null)
      setActivePage('projects')
    }
    window.addEventListener('acme:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('acme:unauthorized', handleUnauthorized)
  }, [])

  const handleLogin = async (username, password) => {
    const result = await apiRequest('auth', '/login', {
      method: 'POST',
      body: { username, password },
    })
    window.localStorage.setItem('acme-token', result.token)
    window.localStorage.setItem('acme-user', JSON.stringify(result.user))
    setUser(result.user)
  }

  const handleLogout = () => {
    window.localStorage.removeItem('acme-token')
    window.localStorage.removeItem('acme-user')
    setUser(null)
    setActivePage('projects')
  }

  if (checkingSession) {
    return <Typography role="status" sx={{ p: 4 }}>Checking your session...</Typography>
  }
  if (!user) return <LoginPage onLogin={handleLogin} />

  const canEdit = user.role === 'admin' || user.role === 'manager'
  const pages = [
    { id: 'projects', label: 'Projects' },
    { id: 'team', label: 'Team & allocations' },
    { id: 'deliverables', label: 'Deliverables' },
    { id: 'budget', label: 'Budget' },
  ]
  if (user.role === 'admin') pages.push({ id: 'users', label: 'Users' })

  return (
    <>
      <AppBar position="static">
        <Toolbar sx={{ flexWrap: 'wrap', gap: 1 }}>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, minWidth: 180 }}>
            ACME Inc. Project Management
          </Typography>
          <Typography variant="body2">{user.name} ({user.role})</Typography>
          <Button color="inherit" onClick={handleLogout}>Log out</Button>
          <Tabs
            value={activePage}
            onChange={(_, value) => setActivePage(value)}
            variant={isMobile ? 'scrollable' : 'standard'}
            textColor="inherit"
            indicatorColor="secondary"
            aria-label="Main navigation"
          >
            {pages.map((page) => (
              <Tab key={page.id} value={page.id} label={page.label} />
            ))}
          </Tabs>
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl">
        <Box sx={{ py: 3 }}>
          {activePage === 'projects' && <ProjectsPage canEdit={canEdit} />}
          {activePage === 'team' && <TeamPage canEdit={canEdit} />}
          {activePage === 'deliverables' && <DeliverablesPage canEdit={canEdit} />}
          {activePage === 'budget' && <BudgetPage canEdit={canEdit} />}
          {activePage === 'users' && user.role === 'admin' && <UsersPage currentUser={user} />}
        </Box>
      </Container>
    </>
  )
}

App.propTypes = {}

export default App
