import { useState } from 'react'
import PropTypes from 'prop-types'
import { AppBar, Box, Container, Tab, Tabs, Toolbar, Typography } from '@mui/material'
import { useMediaQuery } from 'react-responsive'
import './App.css'
import ProjectsPage from './pages/ProjectsPage.jsx'
import TeamPage from './pages/TeamPage.jsx'
import DeliverablesPage from './pages/DeliverablesPage.jsx'

/** Render the ACME project workspace. */
function App() {
  const isMobile = useMediaQuery({ maxWidth: 600 })
  const [activePage, setActivePage] = useState(0)

  return (
    <>
      <AppBar position="static">
        <Toolbar sx={{ flexWrap: 'wrap', gap: 1 }}>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            ACME Inc. Project Management
          </Typography>
          <Tabs
            value={activePage}
            onChange={(_, value) => setActivePage(value)}
            variant={isMobile ? 'scrollable' : 'standard'}
            textColor="inherit"
            indicatorColor="secondary"
            aria-label="Main navigation"
          >
            <Tab label="Projects" />
            <Tab label="Team & allocations" />
            <Tab label="Deliverables" />
          </Tabs>
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl">
        <Box sx={{ py: 3 }}>
          {activePage === 0 && <ProjectsPage />}
          {activePage === 1 && <TeamPage />}
          {activePage === 2 && <DeliverablesPage />}
        </Box>
      </Container>
    </>
  )
}

App.propTypes = {}

export default App
