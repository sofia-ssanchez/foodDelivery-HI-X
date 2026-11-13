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
restaurant and eight orders: two placed, two preparing, one ready, one picked
up, and two delivered. Courier1 has an offer to accept; courier2 is carrying an
order. Delivered orders have billing entries and completed delivery history.
All orders have customer accounts, saved addresses, coordinates, and status history. Customers select their delivery address
at checkout. Address search and map tiles require internet access.
| restaurant3 | Plateau Pizza owner |
| restaurant4 | Verdun Bowl owner |
| restaurant5 | Rosemont Tacos owner |
| restaurant6 | Lachine Bistro owner |
| operator1 | Operator |

The baseline has six Montreal restaurants (five open and Lachine Bistro paused),
eight available menu items per restaurant, and 51 orders. Placed, accepted,
preparing, and ready counts vary by restaurant; each has three delivered orders.
Vegan Corner also has one picked-up order. Six ready orders start in the waiting queue. `courier1`
has an offer to accept; `courier2` is carrying an order. Delivered orders have billing entries and completed delivery history.
All orders have customer accounts, saved addresses, coordinates, and status
history. Each customer account has a repeatably randomized sample Montreal address.
Customers must select their delivery address at checkout; it is saved on their account and order. Address search and map tiles require internet access.

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
5. Click **Reset database** on any dashboard to restore all 51 seeded orders and
   the original courier assignments. Refresh the other open dashboards.

The reset button restores the seed data, not the pre-setup database backup, and
does not create a new backup. If there are no available couriers, ready orders
remain queued until the next dispatch trigger.

Going offline before pickup releases any accepted delivery assignment. The order
stays ready and returns to dispatch for another available courier; if none is
available, it waits in the queue. The old assignment remains in history as
cancelled. Going offline while carrying food is blocked until delivery is confirmed.

## Restaurant map queues

On any dashboard map, click a restaurant marker (or its entry under **Locations**)
to open its details panel. **Queued** counts placed plus accepted orders;
preparing and ready orders have separate counts. Marker colors use the queued
count: green for 0–2, amber for 3–5, red for 6+. Paused restaurants are always red.
The baseline shows all three marker colors, including a paused override:

| Restaurant | Status | Placed | Accepted | Queued total | Marker |
| --- | --- | --- | --- | --- | --- |
| Green Garden | Open | 1 | 1 | 2 | Green |
| Vegan Corner | Open | 2 | 2 | 4 | Amber |
| Plateau Pizza | Open | 4 | 3 | 7 | Red |
| Verdun Bowl | Open | 0 | 0 | 0 | Green |
| Rosemont Tacos | Open | 3 | 2 | 5 | Amber |
| Lachine Bistro | Paused | 1 | 0 | 1 | Red (paused override) |

Log in as `restaurant6` and resume Lachine Bistro to change its red marker to
green. Reset restores the paused state. Existing orders remain visible while
paused, but customers cannot place new orders there.
Customer active-order restaurants retain a purple outline around the queue color.
Enable **Restaurant labels** to show names and queued counts on the map.

Owners can accept/reject the first placed order, start the first accepted order,
mark preparing orders ready, and pause/resume their restaurant from the panel.
Couriers can confirm pickup/delivery for their accepted assignment. Customers
see only their own active orders; operators see all active orders for the selected
restaurant. Counts reflect the whole restaurant. Menus are available in the panel.
Map data and the selected panel refresh every 15 seconds and after quick actions.
