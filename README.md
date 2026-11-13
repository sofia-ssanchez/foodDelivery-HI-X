# foodDelivery

To get backend running cd into backend then run

To set up virtual environment:
python3 -m venv venv

To activate virtual environment:
source venv/bin/activate

To install requiremnts:
python -m pip install -r requirements.txt

To apply migrations:
python3 manage.py migrate

To start the backend:
python3 manage.py runserver



To start the frontend:
cd frontend
npm run dev
### Testing multiple accounts locally

Run the frontend on separate ports (`npm run dev`, `npm run dev:second`,
`npm run dev:third`) and sign in separately at `http://localhost:3000`,
`http://localhost:3001`, and `http://localhost:3002`.
In Django DEBUG mode, trusted localhost origins use separate HttpOnly access
and refresh cookie names. Logging in, refreshing, or logging out on one port
leaves the other ports' sessions intact. Tabs on the same port share a login.
After upgrading from the shared-cookie setup, sign in once on each port.
The CSRF cookie remains host-wide and contains no account identity.
