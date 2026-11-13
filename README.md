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
| `restaurant3` | `12345678` | Plateau Pizza owner |
| `restaurant4` | `12345678` | Verdun Bowl owner |
| `restaurant5` | `12345678` | Rosemont Tacos owner |
| `restaurant6` | `12345678` | Lachine Bistro owner |
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

- The fifteen accounts above, with passwords restored to `12345678`.
- Six restaurants (five open, Lachine Bistro paused) with saved Montreal coordinates and eight available menu items each.
- Two couriers with saved locations: `courier1` has an offer; `courier2` is carrying an order.
- 51 orders with varied workloads and three delivered orders per restaurant. Placed + accepted queues: Green Garden 2 (green), Vegan Corner 4 (amber), Plateau Pizza 7 (red), Verdun Bowl 0 (green), Rosemont Tacos 5 (amber), and Lachine Bistro 1 (red because paused). Vegan Corner also has one picked-up order.
- Each customer receives a randomly assigned sample Montreal address and matching coordinates (repeatable on reset), also saved on their seeded orders. Checkout requires finding and selecting a delivery address; placing an order saves it on the customer account and snapshots it on the order.
- Order status history and billing entries for the 18 delivered orders. Six ready orders wait in the delivery queue, plus one offered order; each courier still has at most one active offer or delivery.

Orders, deliveries, refunds, extra accounts, and menu changes made during the
demo are removed. Reset restores the seeded dataset, **not** the database backup
from before demo setup. The reset button does not create a new backup.

The current dashboard reloads automatically. Refresh other open dashboard tabs
after resetting to discard stale forms or carts. Existing demo account IDs are
preserved, so those accounts can stay logged in.

Reset requires Django `DEBUG` mode and the local `backend/.demo-enabled` file
created by `setup_demo`. This file is ignored by Git; run setup on each new
checkout. Removing the file disables database reset.


## Courier dispatch and delivery flow

Ready orders without an active offer or assignment form the delivery queue,
ordered by ready time (oldest first), then order ID. Dispatch selects the nearest
eligible idle courier to the restaurant. Couriers who are offline, carrying an
order, or already have an active offer or assignment are skipped.

Declining an offer immediately offers that order to the next nearest eligible
courier who has not declined in the current round. Once all currently available
couriers have declined, a new round starts with the nearest available courier.
The declining courier is offered a different queued order, oldest ready first,
before the original order can return to them. If no alternative can be assigned,
the original order may be offered again. Decline history is preserved.
If no courier is available, the order stays queued
until dispatch is triggered by courier availability or another order becoming ready.

After **Confirm delivered**, the courier becomes idle and dispatch immediately
checks the waiting queue. The dashboard switches to **Offers** and refreshes so
the courier can accept their next offer. Nearest-courier selection still applies;
completing a delivery does not bypass that rule. Each courier can have only one
active offer or delivery at a time.

See [DEMO.md](DEMO.md) for a short walkthrough using the seeded orders.

Going offline before pickup releases any accepted delivery assignment. The order
stays ready and returns to dispatch for another available courier; if none is
available, it waits in the queue. The old assignment remains in history as
cancelled. Going offline while carrying food is blocked until delivery is confirmed.

## Dashboard map queues

Restaurant markers show queued workload (placed + accepted orders): green for
0–2, amber for 3–5, red for 6+, and always red when paused. Click a marker for
queued/preparing/ready counts, active order states, the menu, and permitted quick
actions. Optional labels show restaurant names and queue counts. Customer active
orders use a purple marker outline without overriding the queue color.

Owners see and manage their own queues, operators can inspect all restaurant
queues, customers see their own orders, and couriers see their assigned delivery.
See [the map demo instructions](DEMO.md#restaurant-map-queues).


### Seeded restaurant workload

| Restaurant | Status | Placed | Accepted | Queued total | Marker |
| --- | --- | --- | --- | --- | --- |
| Green Garden | Open | 1 | 1 | 2 | Green |
| Vegan Corner | Open | 2 | 2 | 4 | Amber |
| Plateau Pizza | Open | 4 | 3 | 7 | Red |
| Verdun Bowl | Open | 0 | 0 | 0 | Green |
| Rosemont Tacos | Open | 3 | 2 | 5 | Amber |
| Lachine Bistro | Paused | 1 | 0 | 1 | Red (paused override) |

Queued counts are placed + accepted. Resume Lachine Bistro from its owner
dashboard to see its marker change from red to green. Reset restores these counts
and pauses Lachine Bistro again.
