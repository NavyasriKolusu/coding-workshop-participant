# ACME Inc. Project Management

A responsive project portfolio app for tracking project health, deliverables and
dependencies, team allocations, budgets, and user access. It is built on the
Citi Coding Workshop full-stack template.

## Features

- Dashboard with project status, at-risk projects, over-allocated members,
  planned-versus-spent budgets, deliverable progress, and dependency chains.
- Search and filters for project, team, deliverable, and budget lists.
- CRUD for projects, team members, allocations, deliverables, budget entries,
  and (for admins) users.
- Admin, manager, and member roles. Admins can manage users, managers can
  manage project data, and members have read-only access.
- Responsive layouts for mobile and desktop, with loading, success, and error
  feedback.

## Architecture

- **Frontend:** React and Vite, with Material UI and `react-responsive`.
  Service requests are in `frontend/src/services/api.js`; pages are in
  `frontend/src/pages/`.
- **Backend:** Python 3.13 Lambda handlers, one service per folder under
  `backend/`. Each service includes an identical `db.py` helper.
- **Database:** PostgreSQL via `psycopg[binary]==3.2.3`.
- **Authentication:** PBKDF2-HMAC password hashes and signed, expiring HMAC
  tokens. Set `AUTH_SECRET` to a strong secret in deployed environments.

## Run locally

The workshop development script starts the local services, including the
frontend, Lambda API, and PostgreSQL. From the repository root:

```sh
./bin/start-dev.sh
```

Initialize the database once after startup (and again only if you need to
initialize a fresh database):

```sh
curl --fail http://localhost:3001/api/health
curl --fail http://localhost:3001/api/setup
```

Open [http://localhost:3000](http://localhost:3000) and sign in with one of
these local demo accounts:

| Role | Username |
| --- | --- |
| Admin | `admin` |
| Manager | `manager` |
| Member | `member` |

These are local demo accounts. Their development-only passwords are not
documented in this public README; never reuse demo credentials in production.
Configure a strong `AUTH_SECRET` before deployment.

The local database defaults are defined in the service connection helper.
Override them with `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_NAME`,
`POSTGRES_USER`, and `POSTGRES_PASS`. The frontend API base defaults to
`http://localhost:3001`; override it with `VITE_API_URL` when needed.

## API

All endpoints return JSON. Except for health, setup, and login, API requests
require an `Authorization: Bearer <token>` header. The app obtains the token
from `/api/auth/login`. Locally the frontend also supports the workshop proxy's
Authorization-header limitation; deployed requests use the Authorization
header.

| Service | Routes | Access |
| --- | --- | --- |
| `health` | `GET /api/health` | Public |
| `setup` | `GET /api/setup` | Public; creates schema and seeds empty tables |
| `auth` | `POST /api/auth/login`, `GET /api/auth/me` | Login is public; `/me` requires a token |
| `auth` | `GET/POST /api/auth/users`, `PUT/DELETE /api/auth/users/{id}` | Admin |
| `dashboard` | `GET /api/dashboard` | Any signed-in user |
| `projects` | `GET/POST /api/projects`, `GET/PUT/DELETE /api/projects/{id}` | Reads: any signed-in user; writes: admin or manager |
| `team_members` | `GET/POST /api/team_members`, `GET/PUT/DELETE /api/team_members/{id}` | Reads: any signed-in user; writes: admin or manager |
| `allocations` | `GET/POST /api/allocations`, `GET/PUT/DELETE /api/allocations/{id}` | Reads: any signed-in user; writes: admin or manager |
| `deliverables` | `GET/POST /api/deliverables`, `GET/PUT/DELETE /api/deliverables/{id}` | Reads: any signed-in user; writes: admin or manager |
| `budget_entries` | `GET/POST /api/budget_entries`, `GET/PUT/DELETE /api/budget_entries/{id}` | Reads: any signed-in user; writes: admin or manager |

List routes accept relevant `search` (or `name`), `status`, and `department`
query parameters. Deliverables accept dependency IDs in `depends_on`; the
backend rejects missing or cyclic dependencies.

## Tests and checks

Install the backend test tools and run the mocked Lambda handler tests:

```sh
python3 -m pip install -r tests/requirements.txt
python3 -m py_compile backend/*/function.py
python3 -m pytest -q tests/backend --cov=backend --cov-report=term-missing --cov-fail-under=80
```

Run the frontend tests, lint, and production build:

```sh
cd frontend
npm install
npm run test
npm run lint
npm run build
```

Latest verification: 18 backend tests passed with 89.72% coverage; 5 frontend
tests passed; lint and production build succeeded. The build currently emits a
non-fatal warning that the main JavaScript chunk is larger than 500 kB.
Backend unit tests mock database access; they do not replace testing against a
running PostgreSQL instance.

## Deploy to AWS

Configure AWS credentials and the required workshop infrastructure and
database settings, then run these commands from the repository root:

```sh
./bin/deploy-backend.sh
./bin/deploy-frontend.sh
```

After deployment, call `GET <API_BASE_URL>/api/setup` once to initialize the
database. Set `VITE_API_URL` to the deployed API base URL before building the
frontend if the deploy process does not set it automatically. Do not expose
the setup endpoint publicly after initialization unless required.

## Assumptions and known gaps

- A project is considered at risk if it ends within 14 days with deliverable
  progress below 70%, or if it has an overdue deliverable.
- Setup seeds sample data only when the corresponding tables are empty.
- Tokens expire after 12 hours. There is no token refresh, password reset, or
  user self-service; user administration is restricted to admins.
- Automated frontend coverage focuses on the API client and project-page role
  controls. There are no end-to-end browser tests.
- Service requirements pin psycopg to version 3.2.3. The configured package
  mirror used during local verification did not provide that version, so
  verification used psycopg 3.2.13 locally without changing the service
  requirements.

For general workshop guidance, see the [full-stack guide](./docs/full-stack.md)
and [backend guide](./backend/README.md).
