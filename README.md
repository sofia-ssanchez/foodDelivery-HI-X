# Five Leaf Clover Food Delivery

## Run with Docker Compose

Requirements: Docker Desktop (or Docker Engine with the Compose plugin) and an
internet connection for the first image build. The app runs with a private
SQLite database in a Docker named volume; it does not use `backend/db.sqlite3`
or a local Python virtual environment.

From the repository root:

```bash
cp .env.example .env
docker compose up --build
```

Compose builds the backend and frontend images, applies Django migrations,
loads the repeatable demo seed data, and starts both services. Open
<http://localhost:3000>. The backend API is available at
<http://localhost:8000>.

Seeded demo accounts use the password `password`:

| Role | Username |
|---|---|
| Customer | `testCustomer1` or `testCustomer2` |
| Restaurant | `testRestaurant1`, `testRestaurant2`, or `testRestaurant3` |
| Courier | `testCourier1` |
| Operator | `testOperator1` |

The frontend API address defaults to `http://localhost:8000`. To use a
different browser-visible backend address, set `NEXT_PUBLIC_API_BASE` in `.env`
and rebuild the frontend with `docker compose up --build`. It is a browser URL;
the Compose-only hostname `backend` cannot be resolved by the browser.

## Run the frontend locally

```bash
cd frontend
npm run dev
```

### Testing multiple accounts locally

Run the frontend on separate ports (`npm run dev`, `npm run dev:second`,
`npm run dev:third`) and sign in separately at `http://localhost:3000`,
`http://localhost:3001`, and `http://localhost:3002`.
In Django DEBUG mode, trusted localhost origins use separate HttpOnly access
and refresh cookie names. Logging in, refreshing, or logging out on one port
leaves the other ports' sessions intact. Tabs on the same port share a login.
After upgrading from the shared-cookie setup, sign in once on each port.
The CSRF cookie remains host-wide and contains no account identity.

## Stop and resume

Stop the containers while preserving the database:

```bash
docker compose down
```

Start them again with the same database and seeded records:

```bash
docker compose up
```

The database volume persists across normal stops and container recreation.
Migrations and the idempotent seed command run at each backend start.

## Reset demo data

To restore the initial demo state, remove the SQLite volume and recreate the
stack:

```bash
docker compose down --volumes
docker compose up --build
```

This deletes all data stored in the Compose database volume, including changes
made during the demo. The next startup creates a fresh database, applies all
migrations, and reloads the seed data.

## Build images without starting services

```bash
docker compose build
```

Compose creates locally buildable images from the Dockerfiles and lockfiles;
separate image exports are unnecessary when the repository is available and
Docker can build it.
