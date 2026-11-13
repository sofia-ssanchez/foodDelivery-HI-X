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

Run up to eight frontend servers in separate terminals from `frontend`, with
one shared backend on port 8000:

| Command | URL |
| --- | --- |
| `npm run dev` | http://localhost:3000 |
| `npm run dev:second` | http://localhost:3001 |
| `npm run dev:third` | http://localhost:3002 |
| `npm run dev:fourth` | http://localhost:3003 |
| `npm run dev:fifth` | http://localhost:3004 |
| `npm run dev:sixth` | http://localhost:3005 |
| `npm run dev:seventh` | http://localhost:3006 |
| `npm run dev:eighth` | http://localhost:3007 |

Each server uses a separate Next.js output directory. Sign in to a different
account on each port in the same browser. Restart the backend after pulling
these settings changes.
In Django DEBUG mode, trusted localhost origins use separate HttpOnly access
and refresh cookie names. Logging in, refreshing, or logging out on one port
leaves the other ports' sessions intact. Tabs on the same port share a login.
After upgrading from the shared-cookie setup, sign in once on each port.
The CSRF cookie remains host-wide and contains no account identity.

## Demo accounts

All demo accounts use the password **`12345678`**.

| Username | Password | Role / restaurant |
| --- | --- | --- |
| `customer1` | `12345678` | Customer |
| `customer2` | `12345678` | Customer |
| `customer3` | `12345678` | Customer |
| `customer4` | `12345678` | Customer |
| `customer5` | `12345678` | Customer |
| `customer6` | `12345678` | Customer |
| `courier1` | `12345678` | Courier — starts with an offer to accept |
| `courier2` | `12345678` | Courier — starts carrying an order |
| `restaurant1` | `12345678` | Green Garden owner |
| `restaurant2` | `12345678` | Vegan Corner owner |
| `operator1` | `12345678` | Operator |

To initialize the demo on a new checkout, run these commands from `backend`
with the virtual environment activated:

```sh
python manage.py migrate
python manage.py setup_demo
```

`setup_demo` replaces the current database contents with the demo dataset.
Before doing so, it saves a timestamped SQLite backup in `/tmp` and prints its
location. These credentials are for local demonstrations only.

## Resetting the demo database

Click **Reset database** next to **Log out** on any of the four dashboards,
then confirm. Any signed-in demo account can use this button.

Reset replaces current activity with the original demo dataset:

- The eleven accounts above, with passwords restored to `12345678`.
- Two open restaurants with saved Montreal coordinates and eight available menu items each.
- Two couriers with saved locations: `courier1` has an offer; `courier2` is carrying an order.
- Eight orders: two placed, two preparing, one ready for pickup, one picked up, and two delivered.
- Customer delivery addresses, coordinates, order status history, and billing entries for the delivered orders.

Orders, deliveries, refunds, extra accounts, and menu changes made during the
demo are removed. Reset restores the seeded dataset, **not** the database backup
from before demo setup. The reset button does not create a new backup.

The current dashboard reloads automatically. Refresh other open dashboard tabs
after resetting to discard stale forms or carts. Existing demo account IDs are
preserved, so those accounts can stay logged in.

Reset requires Django `DEBUG` mode and the local `backend/.demo-enabled` file
created by `setup_demo`. This file is ignored by Git; run setup on each new
checkout. Removing the file disables database reset.
