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
