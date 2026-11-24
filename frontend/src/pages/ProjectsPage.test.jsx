import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ProjectsPage from './ProjectsPage.jsx'
import { apiRequest } from '../services/api.js'

vi.mock('react-responsive', () => ({ useMediaQuery: () => false }))
vi.mock('../services/api.js', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, apiRequest: vi.fn() }
})

const projects = [{
  id: 1,
  name: 'Customer Portal',
  description: 'Refresh customer access',
  status: 'active',
  department: 'Product',
  start_date: '2026-01-01',
  end_date: '2026-12-31',
}]

describe('ProjectsPage', () => {
  beforeEach(() => {
    apiRequest.mockResolvedValue(projects)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('hides project editing controls for view-only members', async () => {
    render(<ProjectsPage canEdit={false} />)

    expect(await screen.findByText('Customer Portal')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add project' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
  })

  it('shows project creation and row actions for managers', async () => {
    render(<ProjectsPage canEdit />)

    expect(await screen.findByRole('button', { name: 'Add project' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
  })
})
