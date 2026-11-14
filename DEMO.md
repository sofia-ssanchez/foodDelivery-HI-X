# Local demo

All demo accounts use the password `12345678`.

| Username | Role / restaurant |
| --- | --- |
| customer1–customer6 | Customer |
| courier1, courier2 | Courier |
| restaurant1 | Green Garden owner |
| restaurant2 | Vegan Corner owner |
| restaurant3 | Plateau Pizza owner |
| restaurant4 | Verdun Bowl owner |
| restaurant5 | Rosemont Tacos owner |
| restaurant6 | Lachine Bistro owner |
| operator1 | Operator |

The baseline has six Montreal restaurants (five open and Lachine Bistro paused),
eight menu items each, and 51 sample orders: 11 placed, 8 accepted, 6 preparing,
7 ready, 1 picked up, and 18 delivered. Six ready orders wait in the dispatch
queue; `courier1` has one offer and `courier2` is carrying the seeded picked-up
order. This makes the waiting queue, active offer, and carrying state visible
immediately after reset. Delivered orders have billing entries and completed
delivery history. Orders have saved customer addresses, coordinates, and status history.
Customers select a delivery address at checkout. Address search and map tiles
require internet access.

The API console appears at the bottom right, stores the last 100 requests per
browser tab, and can be collapsed. Expand an entry to see its response. Enable
**Show GET requests** to include successful reads and polling. Account response
bodies are hidden.

Click **Reset database** as `operator1` to restore the baseline. Reset removes
activity and extra accounts, then restores the accounts, menus, coordinates,
courier states, and orders listed above. Baseline account IDs are preserved so
existing logins remain usable. Refresh other open dashboard tabs after a reset.

To initialize the demo locally on another checkout, run from `backend`:

```sh
python manage.py migrate
python manage.py setup_demo
```

`setup_demo` backs up the local SQLite database to a timestamped file in `/tmp`
before replacing its data. It creates the ignored `backend/.demo-enabled` marker.
Reset requires Django DEBUG mode, that marker, and an operator account. Remove
the marker to disable reset.


## Running the delivery demo

Use separate localhost ports for separate accounts in the same browser. The
frontend supports ports **3000–3007**, each with isolated login cookies. See the
[README commands](README.md#testing-multiple-accounts-locally). Tabs on the same
port share a login; all ports use the same backend database.

### Happy Path Order

1. Sign in as `operator1` and choose **Reset database**.
2. The reset state already shows ready orders waiting, an offer for `courier1`,
   and a picked-up order with `courier2`. Accept the `courier1` offer, confirm
   pickup, and deliver it; then confirm delivery for `courier2`'s order. These
   actions also trigger retries for the oldest waiting ready orders.
3. To run a new order through placement and restaurant preparation, sign in as
   `customer1`, choose an open restaurant, add an available item, select a
   delivery address, and place the order. The restaurant accepts, prepares, and
   marks it ready. The dispatcher preserves oldest-ready-first queue order, so
   earlier seeded ready orders must be processed before this newer order is
   offered.
4. After its offer arrives, the courier accepts, confirms pickup, and confirms
   delivery. Return to the customer account and open the summary. The total uses
   the pricing values in the Phase III report.

### No Courier Available

1. Reset again as `operator1`. The reset has six ready orders waiting, one offer
   assigned to `courier1`, and `courier2` carrying an order. No courier is free
   for another offer.
2. Confirm delivery of `courier2`'s order. The courier becomes idle and dispatch
   retries the queue, offering its oldest ready order.
3. Decline an offer to return it to dispatch, or accept, pick up, and deliver it
   to continue draining the queue.

The Reset button is operator-only. It restores the seeded state, not the
pre-setup database backup, and does not create a new backup. Going offline before
pickup leaves an accepted assignment in place for operator reassignment; going
offline while carrying an order is blocked. Declining an offer returns it to
dispatch without assigning that order to the declining courier.

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
