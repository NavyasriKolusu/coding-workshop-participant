import PropTypes from 'prop-types'
import { Box, Container, Typography } from '@mui/material'
import './App.css'
import ProjectsPage from './pages/ProjectsPage.jsx'

/** Render the ACME project workspace. */
function App() {
  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          ACME Inc. Projects
        </Typography>
        <ProjectsPage />
      </Box>
    </Container>
  )
}

App.propTypes = {}

export default App
