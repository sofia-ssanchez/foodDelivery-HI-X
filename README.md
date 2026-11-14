# Five Leaf Clover Food Delivery

This project has a Django backend and a Next.js frontend. You can run them
locally in two terminals or run both together with Docker Compose.

## Getting started with Docker
This is the easiest way to start the complete application. You need Docker
Desktop (or Docker Engine with the Compose plugin) and an internet connection
the first time you build the images.

Docker uses its own persistent SQLite database volume. It does not use your
local `backend/db.sqlite3` file or your local Python virtual environment.

Open a terminal at the repository root (the folder containing `compose.yaml`)
and run:

```bash
cp .env.example .env
docker compose up --build
```

The first command copies the example settings into a local `.env` file. If you
already have a `.env` file, keep it and do not overwrite it. The second command
builds the backend and frontend images, starts both services, applies Django
migrations, and loads the initial data the first time the Docker database is
created. Later starts keep the existing database and demo activity.

When the services are ready, open:

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000>
- Django admin: <http://localhost:8000/admin/>

The frontend calls the backend using the browser-visible address
`http://localhost:8000`. Inside Compose, the backend service is named `backend`,
but a browser cannot resolve that name. If you change the address, set
`NEXT_PUBLIC_API_BASE` in `.env` to the address your browser can reach, then
rebuild the frontend image as described in
[Build and update Docker images](#build-and-update-docker-images).

The command runs in the foreground and shows service logs. Press **Ctrl+C** to
stop it, then run `docker compose down` to stop and remove the containers while
keeping the database. To run Compose in the background instead, use:

```bash
docker compose up --build -d
```

To see the logs from background services:

```bash
docker compose logs -f
```

Press **Ctrl+C** to stop following the logs. The services will continue to
run in the background until you stop them with `docker compose down`.

## Demo accounts and seeded data

### The `seed_data` management command

The backend includes a custom Django management command named `seed_data`.
On a fresh Docker volume, Compose runs migrations, runs `seed_data`, and then
loads the repeatable Phase III demo state with `setup_demo`. This happens only
for a new database; normal restarts keep seeded data and later demo activity.

The Phase III demo accounts use the password `12345678`. For example, sign in
as `operator1` to access reset and operator actions, `customer1` to place an
order, `restaurant1` to prepare it, or `courier1` to accept and deliver it.

The demo reset action is available to operator accounts only. After signing in
as an operator, choose **Reset database** to restore the six-restaurant Phase
III demo scenario data. It includes six unassigned ready orders in the dispatch
queue, one offered order, and one courier carrying an order, so the TA can
inspect both waiting and active delivery states immediately. Reset also
supports the Happy Path, No Courier Available, and Sold Out/Paused use cases
without deleting the Docker volume.

If you run the backend locally, run the command from the `backend` folder:

```bash
python manage.py seed_data
```

To restore the standard restaurant settings and seeded menu item prices and
availability, pass the special `--restore-baseline` option:

```bash
python manage.py seed_data --restore-baseline
```

This option does not erase the database or delete orders and other records. To
restore a completely fresh Docker demo database, use the full reset steps
below.

To run either command in a running Docker backend container, use:

```bash
docker compose exec backend python manage.py seed_data
docker compose exec backend python manage.py seed_data --restore-baseline
```

For a local backend, run `python manage.py seed_data` and then
`python manage.py setup_demo` after migrations if you want the same Phase III
demo accounts and operator reset action. `setup_demo` backs up the current
local SQLite database before replacing its data with the demo baseline.

## Run the backend locally

You need Python 3.13 or a compatible Python version supported by the packages
in `backend/requirements.txt`.

1. Open a terminal at the repository root and create a virtual environment:

   ```bash
   cd backend
   python3 -m venv .venv
   ```

2. Activate it.

   macOS or Linux:

   ```bash
   source .venv/bin/activate
   ```

   Windows PowerShell:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

3. Install the backend dependencies and initialize the database:

   ```bash
   python -m pip install -r requirements.txt
   python manage.py migrate
   python manage.py seed_data
   ```

   `migrate` creates or updates the local SQLite database. `seed_data` adds
   the demo accounts and example records.

4. Start Django:

   ```bash
   python manage.py runserver
   ```

   The API is available at <http://localhost:8000>. Keep this terminal open
   while using the application.

## Run the frontend locally

Open a **second terminal** at the repository root. Install Node.js 22 and npm,
then run:

```bash
cd frontend
npm ci
npm run dev
```

`npm ci` installs the exact frontend dependencies recorded in
`frontend/package-lock.json`. When Next.js says it is ready, open
<http://localhost:3000>. Keep both the backend and frontend terminals running.

The frontend API address defaults to `http://localhost:8000`. To use a
different backend address during local development, create
`frontend/.env.local` and add:

```dotenv
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

Replace the value with the browser-visible backend address if it is different.
Restart the frontend development server after changing this setting.

## Build and update Docker images

To build the images without starting the application, run this at the
repository root:

```bash
docker compose build
```

The images are built from the Dockerfiles in `backend/` and `frontend/` using
the dependencies in `backend/requirements.txt` and `frontend/package-lock.json`.

Docker images contain a snapshot of the source files from build time. Making a
Git commit by itself does not update an image. After changing application code,
build and start/recreate the services with:

```bash
docker compose up --build
```

If the change only affects the backend, you can rebuild and restart that
service with:

```bash
docker compose up --build -d backend
```

If the change affects the frontend, use:

```bash
docker compose up --build -d frontend
```

## Stop, resume, and reset Docker

Stop the containers but keep the database and demo changes:

```bash
docker compose down
```

Start them again with the same database and records:

```bash
docker compose up
```

The database volume persists across normal stops and container recreation.
Migrations run at each backend start; initial data is seeded only when the
volume has not been initialized yet.

To restore the initial demo state, remove the database volume and recreate the
stack:

```bash
docker compose down --volumes
docker compose up --build
```

This deletes all data stored in the Compose database volume, including changes
made during the demo. The next startup creates a fresh database, applies all
migrations, runs the seed command, and restores the Phase III demo baseline.
This is the reliable full-reset procedure.

## Testing and linting

Run backend tests from the `backend` folder with the virtual environment
activated:

```bash
python manage.py test
```

Run frontend linting from the `frontend` folder:

```bash
npm run lint
```

