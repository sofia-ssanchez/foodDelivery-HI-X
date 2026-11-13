# Local demo

All passwords: `12345678`.

| Accounts | Role |
| --- | --- |
| customer1–customer6 | Customer |
| courier1, courier2 | Courier |
| restaurant1 | Green Garden owner |
| restaurant2 | Vegan Corner owner |
| operator1 | Operator |

The baseline has two open Montreal restaurants, eight available menu items per
restaurant and 31 orders. Each restaurant has three placed, three accepted,
three preparing, three ready, and three delivered orders. Vegan Corner also has
one picked-up order. Five ready orders start in the waiting queue. `courier1`
has an offer to accept; `courier2` is carrying an order. Delivered orders have billing entries and completed delivery history.
All orders have customer accounts, saved addresses, coordinates, and status
history. Customers select their delivery address at checkout. Address search and map tiles require internet access.

Run the backend and frontend as usual. The development console appears at the
bottom right, stores the last 100 requests per browser tab, and can be collapsed.
Expand an entry to see its response. Enable **Show GET requests** to include
successful reads and polling. Account response bodies are hidden.

Click **Reset database** next to **Log out** on any dashboard, then confirm.
This removes all activity and extra accounts and restores the baseline, including
menus, coordinates, courier availability, and passwords. Baseline account IDs
are preserved so existing logins remain usable. Refresh other open dashboard
tabs after a reset to discard any in-progress forms or carts.

To initialize the demo on another checkout:

```sh
backend/venv/bin/python backend/manage.py migrate
backend/venv/bin/python backend/manage.py setup_demo
```

`setup_demo` backs up the local SQLite database to a timestamped file in `/tmp`
before replacing its data. It creates the ignored `backend/.demo-enabled` marker.
Reset requires that marker, Django DEBUG mode, an authenticated user, and
normal cookie authentication/CSRF checks. Remove the marker to disable reset.
The console is not rendered in production frontend builds.


## Running the delivery demo

Use separate localhost ports for separate accounts in the same browser. The
frontend supports ports **3000–3007**, each with isolated login cookies. See the
[README commands](README.md#testing-multiple-accounts-locally). Tabs on the same
port share a login; all ports use the same backend database.

1. Sign in as `courier2` and confirm delivery of the picked-up order. This frees
   that courier and triggers dispatch for the oldest waiting ready orders.
   The dashboard switches to **Offers** and refreshes.
2. Sign in as `courier1` to accept its seeded offer, confirm pickup, then confirm
   delivery. Each completion triggers dispatch again.
3. To demonstrate reassignment, keep the other courier online and without an
   active offer or delivery. Decline an offer: it goes immediately to the next
   nearest eligible courier. If all available couriers decline, dispatch starts
   another round from the nearest available courier. With only one available
   courier, that courier receives a different queued order first. The same order
   returns only if no alternative can be assigned. Declining switches the
   dashboard to **Offers** to show the next offer.
4. Use a restaurant dashboard to accept placed orders, start preparation, and
   mark them ready. Waiting orders are processed oldest-ready first; offers go
   to the nearest eligible idle courier. A courier may have only one active
   offer or delivery at a time.
5. Click **Reset database** on any dashboard to restore all 31 seeded orders and
   the original courier assignments. Refresh the other open dashboards.

The reset button restores the seed data, not the pre-setup database backup, and
does not create a new backup. If there are no available couriers, ready orders
remain queued until the next dispatch trigger.

Going offline before pickup releases any accepted delivery assignment. The order
stays ready and returns to dispatch for another available courier; if none is
available, it waits in the queue. The old assignment remains in history as
cancelled. Going offline while carrying food is blocked until delivery is confirmed.
