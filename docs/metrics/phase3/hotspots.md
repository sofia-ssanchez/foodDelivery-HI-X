# Phase III hotspot analysis — PROMO

## Scope and measurement method

The analyzed source is Git tag `phase3`, which resolves to `e52ee101250eea29831c1bab1bfa957a3fc5c025`. All code evidence and line numbers below refer to that tagged source. No Phase IV source is used as baseline evidence.

The primary measurements remain the committed SonarQube Cloud baseline in [`file_metrics.json`](file_metrics.json), produced with PySonar `1.11.0.6012` and the configuration in [`sonar-project.properties`](sonar-project.properties). The export contains project and file components, not class components. Its `ncloc`, `complexity`, and `cognitive_complexity` values are therefore **file-level**. The `issues.json` file reports issues by component/file and line; it does not assign code smells to classes.

To supply reproducible class-level LOC and cyclomatic values without changing the Sonar baseline or adding dependencies, [`../class_metrics.py`](../class_metrics.py) reads source directly from a Git ref via `git show` and Python's standard-library AST. Its Phase III output is [`class_metrics.json`](class_metrics.json), covering every Python class found under the configured source roots at `phase3` (166 classes). There are no TypeScript class declarations in `frontend/src` at that tag; the React components there are functions.

The supplementary LOC counts nonblank, non-comment physical lines from each class's AST span. The supplementary class cyclomatic value is the sum of McCabe scores for direct methods: each method starts at 1, with decision points counted for `if`, `for`/`async for`, `while`, conditional expressions, exception handlers, additional boolean operands, comprehension generators/filters, and match alternatives. Nested functions and nested classes are separate scopes. This is a transparent, reproducible McCabe measure, **not a reproduction of SonarQube's metric implementation**. Use this same script and algorithm for all snapshots; retain SonarQube's same version/configuration and file exports for the primary comparison. Class cognitive complexity is not produced by the committed Sonar export or this script and remains unavailable. No class-level cognitive values are estimated.

Reproduce the supplementary metrics from the repository root without changing branches:

```bash
python3 docs/metrics/class_metrics.py --ref phase3 --all-source \
  --output docs/metrics/phase3/class_metrics.json
python3 docs/metrics/class_metrics.py --ref phase4-refactored --all-source \
  --output docs/metrics/phase4-refactored/class_metrics.json
python3 docs/metrics/class_metrics.py --ref phase4 --all-source \
  --output docs/metrics/phase4/class_metrics.json
```

The script excludes migrations, caches, virtual environments, `node_modules`, and `.next`, consistent with the relevant source exclusions. `--all-source` measures all Python classes under `backend/` and `frontend/src/`, including tests just as the current Sonar source configuration does. If a tag is not present locally, fetch it before running the script. These commands do not run SonarQube or alter application source.

### Assignment status

Section 5.2 asks for metrics for every class, manual coupling for the five hotspots, and five classes with a lecture-named smell and an explanation of which optional module each makes harder to add. The five selected classes below have source-supported smells and concrete, though not equally direct, PROMO relationships. Three have indirect billing/refund relationships; that distinction is called out. The supplementary JSON supplies class LOC and a reproducible class-aggregate McCabe measure for Phase III Python classes. Class cognitive complexity remains unavailable at class granularity.

## Candidate comparison

Sonar values use `file ncloc / file cyclomatic / file cognitive`. These are file context and are not class values. Class LOC and class McCabe values below come from the supplementary JSON. Class cognitive complexity is unavailable.

| Candidate / final hotspot | Class measurements; containing-file Sonar measures | Smell evidence in `phase3` | PROMO relationship and decision |
|---|---|---|---|
| `PlaceOrderCommand` — `backend/orders/commands.py` | Class: **68 LOC / 10 McCabe / cognitive unavailable**. File: **330 / 48 / 32**. | `execute` (lines 32–104) validates customer/address/restaurant/items, builds order lines, persists the order and address, records an event, and saves lines. Manual **Long Method**. | **Select; strong.** PROMO-01/02 require checkout-time code validation, applying the discount, and refusal feedback. This is the backend placement boundary. |
| `OrderSummaryView` — `backend/pricing/views.py` | Class: **39 / 3 / unavailable**. File: **257 / 21 / 15**. | `get` (lines 28–68) combines access/status checks, price calculation, item mapping, and response construction. Manual **Long Method**. | **Select; strong downstream link.** The happy path displays the computed fare and order summary. A clear response-building boundary helps expose the resulting promo-adjusted total. |
| `OperatorLedgerView` — `backend/pricing/views.py` | Class: **62 / 6 / unavailable**. File: **257 / 21 / 15**. | `get` (lines 73–144) checks operator access, loads records, and builds nested item/refund/charge output. Manual **Long Method**. | **Select; moderate.** A promo changes the final charge that the ledger records and presents. PROMO-01/02 do not explicitly require operator ledger display, so this is a financial-consistency extension point rather than a direct acceptance-criteria path. |
| `RestaurantOrderCommand` — `backend/orders/commands.py` | Class: **62 / 13 / unavailable**. File: **330 / 48 / 32**. | `execute` (lines 211–267) combines order transition, status event, ledger recording, offer invalidation, and ready-event scheduling; manual **Long Method**. | **Select; moderate indirect link.** Its final-state path calls ledger recording, which calls pricing. Isolating that side effect makes the order-to-charge integration clearer; the class does not itself validate a promo or calculate its discount. |
| `OperatorRefundRequestListView` — `backend/pricing/views.py` | Class: **49 / 7 / unavailable**. File: **257 / 21 / 15**. | `get` (lines 215–264) combines operator authorization, query setup, refund serialization, and eligibility calculation; manual **Long Method**. | **Select; moderate indirect link.** The displayed eligibility comes from the remaining ledger charge. If promo lowers the original charge, the refundable cap must use that adjusted amount. Refund handling is not explicit in PROMO-01/02, so this is a billing-consistency dependency. |
| `CancelOrderCommand` — `backend/orders/commands.py` | Class: **50 / 11 / unavailable**. File: **330 / 48 / 32**. | `execute` (lines 310–348) combines permission/state checks, courier-assignment checks, transition persistence, event/ledger writes, and offer invalidation; manual **Long Method**. | **Do not select.** The smell is real and the ledger call gives it an indirect billing relationship, but it is a narrower cancellation path than `RestaurantOrderCommand` and does not prepare placement-time validation, fare calculation, or required user feedback. |
| `PlaceOrderView` / `PlaceOrderSerializer` — `backend/orders/views.py` / `backend/orders/serializers.py` | See [`class_metrics.json`](class_metrics.json) for their class measures; containing files: `orders/views.py` **181 / 13 / 4**, `orders/serializers.py` **84 / 3 / 1**. | `PlaceOrderView.create` (views lines 35–59) is a thin authorization/serialization/command orchestration method. `PlaceOrderSerializer` (serializers lines 49–63) declares fields and rejects duplicate menu items. Neither has a defensible class-level smell in this baseline. | **Do not select as hotspots.** Both are direct integration points for carrying promo input, but relevance alone does not establish a refactoring smell. They should be inspected when implementing PROMO. |

The five selected classes are not claimed to be the only useful code units for PROMO. Two particularly direct extension points are **not classes**: `calculate_order_pricing` in `backend/pricing/services.py` (lines 32–64) calculates the subtotal, fees, surcharge, and total; the React function `CustomerDashboard` in `frontend/src/app/dashboard/customer/page.tsx` sends the placement request through `placeOrder` (lines 220–311), where checkout input and refusal feedback belong. The function `OrderSummary` in `frontend/src/app/dashboard/customer/customer-orders.tsx` (lines 94–184) presents the returned total. These are supplementary integration points, not class hotspots.

## Selected hotspot evidence and refactoring options

### 1. `PlaceOrderCommand`

`execute` at `backend/orders/commands.py:32–104` validates the customer at lines 33–38, resolves and validates the restaurant at 40–46, validates every menu item and creates line snapshots at 48–72, creates the order and persists the address snapshot at 74–91, records the initial event at 93–99, then saves each order line at 101–104. The method crosses validation, address, persistence, and event responsibilities: a manual **Long Method** finding. It is not a SonarQube-reported class smell.

**Coupling: 13.** Counting the named superclass, framework/domain/exception classes, nested enums, and generated Django exception classes: `OrderCommand`; `PermissionDenied`; `ValidationError`; customer `Role`; `Restaurant`; `Restaurant.DoesNotExist`; `Restaurant.Status`; `MenuItem`; `MenuItem.DoesNotExist`; `MenuItem.Status`; `Order`; `Order.Status`; `OrderLine`. Modules, functions, primitives, and dependencies hidden in helper calls are not counted; nested enum/generated exception classes are counted separately when named.

**PROMO impact and possible refactoring.** Adding code validation and discount application directly to this multi-step method would mix a new pricing policy into placement mechanics. **Extract Method** to separate current customer/restaurant/menu validation from order persistence, preserving the transaction, exceptions, address snapshot, event, and line values. That provides a smaller placement path where a later PROMO call can be inserted. Keep the refactoring commit behavior-preserving; add PROMO only afterward.

### 2. `OrderSummaryView`

`get` at `backend/pricing/views.py:28–68` loads the customer-owned order at 29–33, gates the response by order state at 35–43, calls `calculate_order_pricing` at 45, maps item lines at 47–55, and creates the pricing response at 57–68. The mixed loading, policy, mapping, and response assembly is a manual **Long Method** finding, not a SonarQube finding.

**Coupling: 5.** `APIView`; `RequireCustomer`; `Order`; `Order.Status`; `Response`. `status` is a module of constants and `get_object_or_404`/`calculate_order_pricing` are functions, so they are excluded.

**PROMO impact and possible refactoring.** This is the order-summary route used to show final fare; its response needs to remain consistent with the discounted calculation. **Extract Method** or introduce a serializer for item and price response construction while preserving the current status gate, response keys, decimal strings, and 409 behavior. A later PROMO addition can then expose a discount field/adjusted total in one response boundary.

### 3. `OperatorLedgerView`

`get` at `backend/pricing/views.py:73–144` authorizes the operator at 74–80, loads ledger/refund/item relations at 82–91, then assembles refund and item detail, total refunded, net charge, and ledger fields at 95–144. The method combines query orchestration with multiple nested response transformations: a manual **Long Method** finding, not a SonarQube class smell.

**Coupling: 6.** `APIView`; `RequireAuth`; `PermissionDenied`; operator `Role`; `OrderLedger`; `Response`. `status` is a module and `get_total_refunded`/`money` are functions, not classes.

**PROMO impact and possible refactoring.** This view is downstream of the charge: if the PROMO design requires the discounted charge or discount breakdown to be visible to operators, the response needs to represent it consistently. **Extract Method** to create one ledger response row, preserving ordering, refunds, charge values, and response shape. The promo relationship is moderate because operator visibility is not explicit in PROMO-01/02.

### 4. `RestaurantOrderCommand`

`execute` at `backend/orders/commands.py:211–267` performs restaurant authorization and locks the order (212–224), validates and persists the transition (226–239), records the status event (241–247), and then performs final-state ledger recording, cancellation-offer invalidation, or ready-event publication (249–265). The transaction method therefore mixes state-transition mechanics with several outcome-specific side effects: a manual **Long Method** finding supported by distinct work blocks and conditional branches. It is not a SonarQube-reported class smell.

**Coupling: 8.** `OrderCommand`; actor `Role`; `Order`; `Order.Status`; `OrderConflict`; `PermissionDenied`; `ValidationError`; `ValueError`. The actor role is accessed as `self.actor.Role`. Functions (`record_order_status_event`, `record_order_ledger`) and the `events` module are not classes and are not counted.

**PROMO impact and possible refactoring.** At lines 249–255 this shared order-finalization path calls `record_order_ledger(order)` for delivered, rejected, or cancelled orders. In the Phase III source, `record_order_ledger` calls `calculate_order_pricing(order)` (`backend/pricing/services.py:70–75`) and stores its returned charge values. Therefore the promo-adjusted fare must flow correctly through this existing finalization-to-pricing path. The connection is indirect: a promo can be implemented inside pricing without modifying this command, but the long method makes it harder to see and characterize which final-state side effects persist the charge. **Extract Method** for the final-state ledger write (preserving its status predicate and transaction timing) to make that billing boundary explicit before integrating PROMO.

### 5. `OperatorRefundRequestListView`

`get` at `backend/pricing/views.py:215–264` checks operator authorization (216–222), loads refund requests with related objects (224–228), builds each response record and calls `evaluate_refund_eligibility(refund)` inside that mapping (230–262), then returns the response (264). Authorization, query construction, formatting, and policy-result assembly are combined in one endpoint method: a manual **Long Method** finding, not a SonarQube class smell.

**Coupling: 6.** `APIView`; `RequireAuth`; operator `Role`; `PermissionDenied`; `RefundRequest`; `Response`. `evaluate_refund_eligibility` is a function and `status` is a module, so neither is counted.

**PROMO impact and possible refactoring.** At line 251 the response embeds refund eligibility. In `backend/pricing/services.py:389–405`, that policy reads the order's `OrderLedger.total_charge`, subtracts prior refunds, and exposes the remaining refundable amount. A promo-adjusted original charge therefore changes the refund cap that this endpoint presents. This is a moderate, indirect billing dependency; PROMO-01/02 do not themselves specify refund behavior. **Extract Method** or introduce a dedicated response serializer for the refund row, preserving existing response fields and eligibility output while making future pricing-related fields easier to add without growing the query/policy method.

## SonarQube issues versus manual smells

The five selected class smells above are manual source-review findings. The Phase III issue export contains ten records: three `CODE_SMELL` issues (`typescript:S6853`) in `frontend/src/app/dashboard/customer/customer-orders.tsx` at lines 363, 381, and 393; six vulnerabilities; and one bug (`typescript:S9383`) in `frontend/src/app/dashboard/customer/page.tsx` at line 94. None is a Sonar-reported smell for the five selected backend classes. Do not describe the frontend issues as findings on `OrderSummary` or as class-level smell measurements.

## Coupling method and metric caveats

For selected class coupling, count the distinct class objects explicitly named in the declaration/body, including the superclass, framework/model/exception classes, and named nested enums. Do not count modules, functions, attributes that are not classes, primitive values, or indirect dependencies inside helper functions. The complete counts and lists for all five selected classes appear above. This manual lexical method is declared so the count can be reviewed; another convention might treat nested enum classes differently.

The script's supplementary Python class metrics provide LOC and method-summed McCabe complexity for every Python class at each ref. These values can be compared consistently across tags with the same script; they are not Sonar-equivalent metrics. Class-level Sonar cognitive complexity is unavailable from the existing analysis and no supported query can create class measures that were not stored as class components. Keep the original Sonar exports unchanged and show file-level cognitive complexity separately. If the instructor requires Sonar's exact cognitive complexity per class, that requirement remains unresolved and needs clarification.

## Refactoring recommendations

These are exactly three behavior-preserving refactorings supported by source evidence and meaningful PROMO integration. Characterization tests should be written and pass before and after each refactoring, as Section 5.3 requires. No refactoring or tests are claimed complete.

1. **`PlaceOrderCommand` — Extract Method.** Characterize customer/restaurant/menu validation failures, address snapshot, order and line values, initial status event, transaction rollback, and successful return. PROMO extension: insertion point for placement-time validation without enlarging `execute` further.
2. **`OrderSummaryView` — Extract Method / introduce a response serializer.** Characterize ownership checks, non-final-order 409 response, item fields, decimal-string formatting, fee/surcharge values, and total. PROMO extension: one stable place to present adjusted fare and, if required, discount detail.
3. **`OperatorLedgerView` — Extract Method for one ledger row.** Characterize operator authorization, ledger ordering, item/refund fields, total-refunded and net-charge arithmetic, and output structure. PROMO extension: keep any required discounted-charge information local to ledger serialization.

The first target is in `orders/commands.py`; the latter two are separate classes in `pricing/views.py`. Their behavior/test targets are distinct, but edits to the shared views file should be coordinated or merged sequentially. If the team requires three changes in separate files, there is no equally strong third PROMO-related class hotspot in this Phase III baseline; ask the instructor whether a non-class function/component may be used for one refactoring.

## Unresolved requirements and decisions

- **PROMO scope interpretation:** the table now has five class hotspots with code evidence. `PlaceOrderCommand` is directly connected to placement; `OrderSummaryView` presents the resulting fare. `OperatorLedgerView`, `RestaurantOrderCommand`, and `OperatorRefundRequestListView` are downstream billing/refund paths. Confirm with the team or instructor that these indirect relationships count as meaningful PROMO relevance when the stated acceptance criteria focus on placement-time validation, fare calculation, and refusal messages.
- **Class cognitive complexity:** unavailable at class granularity in the committed SonarQube export and not reproduced by the supplementary script. Do not substitute the file cognitive score. Ask the instructor whether file-level Sonar cognitive complexity plus the reproducible class LOC/McCabe supplement is acceptable.
- **Class LOC/cyclomatic tool interpretation:** values are reproducibly generated by the documented stdlib script, in addition to unchanged Sonar file metrics. If the instructor interprets Section 5.2 as requiring all class metrics from only SonarQube or Lizard, confirm acceptance of this supplement before relying on it.
- **Sonar code smells:** the exported issue list is file/line-level; the manually reviewed class smells are not Sonar-reported findings.
