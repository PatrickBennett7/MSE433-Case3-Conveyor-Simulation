# Order Sequence Notebook — README

This document describes **`order_sequence.ipynb`**: what it does, the assumptions it uses, and how each of the four belt-assignment algorithms works in relation to **minimizing average order completion time**.

---

## What the Notebook Does

The notebook:

1. **Loads and structures order data** from three CSVs in the `Data/` folder:
   - `order_itemtypes.csv` — which item type (shape) each line belongs to  
   - `order_quantities.csv` — quantity per line  
   - `orders_totes.csv` — which tote each line comes from  

   From these it builds:
   - **Orders:** For each order, which item types it needs, in what quantities, and from which totes.
   - **Totes:** For each tote, which item types and quantities it contains.

2. **Runs four different algorithms** that assign orders to the four conveyor belts. Each algorithm uses a different rule to decide which orders go on which belt (and in what order on that belt).

3. **Exports one CSV per algorithm** with the same format:
   - Columns: `conv_num`, `circle`, `pentagon`, `trapezoid`, `triangle`, `star`, `moon`, `heart`, `cross`
   - Each row is one order; multiple orders on the same conveyor appear as consecutive rows with the same `conv_num`.
   - Item type mapping: circle=0, pentagon=1, trapezoid=2, triangle=3, star=4, moon=5, heart=6, cross=7.

**Output files:** Written to `Data/order_sequencing/` when using the pipeline (see below).

- `algorithm1_load_balance_assignment.csv`
- `algorithm1b_stratified_balance_assignment.csv`
- `algorithm2_tote_overlap_assignment.csv`
- `algorithm3_itemtype_overlap_assignment.csv`
- `algorithm4_combined_overlap_assignment.csv`

**Folder layout (used by `run_all.py` and `compare_methods.py`):**
- `Data/raw/` — data generator outputs: `order_itemtypes.csv`, `order_quantities.csv`, `orders_totes.csv`
- `Data/order_sequencing/` — order_sequence notebook outputs: algorithm assignment CSVs above
- `Data/comparison/` — FIFO run results + comparison CSVs: `comparison_summary.csv`, `comparison_order_times.csv`, `comparison_order_conveyor.csv`

---

## Assumptions

The algorithms and this README rely on the following assumptions:

1. **Conveyor order (physical / timing)**  
   - **Conveyor 1** finishes orders **before** conveyor 2, conveyor 2 before 3, and 3 before 4.  
   - Reason: items travel a longer distance to later conveyors, so they are available earlier on conveyor 1 and later on conveyor 4.  
   - Implication: to balance completion times, we give **more work (heavier groups) to conveyor 1** and less to conveyor 4 where appropriate.

2. **Four conveyors**  
   - There are exactly four conveyor belts. Each belt has one “active” order at a time; when that order is fulfilled, the next order assigned to that belt starts.

3. **Shared totes create bursts**  
   - When a tote passes on the main line, all items from that tote appear in a short “burst.”  
   - Orders that **share a tote** therefore receive their items in the **same burst**.  
   - If two such orders are on the **same** belt, they are in a queue: one gets its items from that burst first, the other waits, which can increase average order time.

4. **Same belt, same item type → contention**  
   - Orders on the **same** belt that want the **same item types** (e.g. both circle-heavy) compete for those items as they pass.  
   - Fulfillment is serialized (first order takes what it needs, then the next), which can increase average order time.

5. **Data format**  
   - Orders and totes are described by the three CSVs above; the notebook does not consider tote sequencing or item order within totes for these algorithms (only which totes and item types each order has).

---

## Objective: Minimize Average Order Time

All four algorithms aim to **minimize average order completion time** by choosing **which orders go to which conveyor** (and, within each conveyor, the order in which orders are fulfilled). They do **not** optimize tote order or item order within totes; those could be handled elsewhere (e.g. in a simulator).

The idea is: better assignment reduces waiting and contention so that, on average, orders complete sooner.

---

## Algorithm 1: Load Balancing by Order Size

**Logic:**  
- Define **order size** = total number of units (sum of quantities) in that order.  
- Sort orders by size **largest first**.  
- Assign to conveyors **in round-robin**: 1st largest → conveyor 1, 2nd → conveyor 2, 3rd → conveyor 3, 4th → conveyor 4, 5th → conveyor 1, etc.

**Why it helps average order time:**  
- Conveyor 1 finishes first, so it can handle more work without becoming the bottleneck.  
- Putting the **largest** orders on conveyor 1 (and then spreading the rest in round-robin) balances total work across belts and avoids conveyor 1 sitting idle while 2–4 are still busy.  
- So we use the “conveyor 1 first” assumption to **load-balance by size**, which tends to smooth completion times and reduce average order time.

**Output:** `Data/algorithm1_load_balance_assignment.csv`

---

## Algorithm 1b: Stratified Load Balance (banded by size, minimax)

**Logic:**  
- Sort orders by **size** (total units).  
- Split the **sorted list into 4 contiguous groups** (banded: no reordering across groups).  
- Choose the 3 cut points to **minimize the maximum group sum** (minimax: make the heaviest belt as light as possible).  
- **strict_boundary = False**: equal-sized orders may be split across adjacent groups (cuts can fall anywhere in the sorted list).

**Why it helps:**  
- Belts are stratified by order size (big orders together, small together) while total workload is balanced.  
- Minimax keeps no single conveyor overloaded.

**Output:** `Data/algorithm1b_stratified_balance_assignment.csv`

---

## Algorithm 2: Minimize Tote Overlap Within the Same Belt

**The problem we’re solving:**  
When a tote goes down the main line, all the items in that tote show up in one short “burst.” If **two different orders** both need items from **the same tote**, and we put those two orders on **the same conveyor**, they have to share that one burst: the first order in line takes what it needs, and the second has to wait (or wait for the next time that item type appears). That waiting increases order completion time. So we want to **avoid putting two orders that share a tote on the same belt**.

**What “tote overlap” means:**  
- Each order gets its items from certain totes (e.g. Order A from totes 1 and 5, Order B from totes 5 and 9).  
- For two orders, their **tote overlap** is simply **how many totes they have in common**. In the example, Order A and B share tote 5, so overlap = 1. If they shared no totes, overlap = 0.

**What the algorithm does (in plain steps):**  
1. For every order, we know which totes it uses. For every **pair** of orders, we compute their tote overlap (0, 1, 2, …).  
2. We need to split all orders into **four groups** (one group per conveyor). The **cost** of a group is: for every pair of orders inside that group, add their tote overlap. So a group with many “overlapping” pairs is bad; we want each group to have **low total overlap**.  
3. We build the four groups **one order at a time**, in a greedy way:  
   - We process orders in a fixed order (e.g. start with orders that overlap with many others).  
   - For the next order, we try putting it on conveyor 1, 2, 3, or 4. For each choice we ask: “What would the total overlap on that conveyor become if we add this order?”  
   - We **assign this order to the conveyor that gives the smallest total overlap** (so we keep “overlapping” orders on different belts). If there’s a tie, we pick the conveyor that currently has **fewest orders** to balance load.  
4. After all orders are assigned, we have four groups. We then **relabel** which group is “conveyor 1,” “conveyor 2,” etc.: the group with the **most total units** (heaviest workload) is called conveyor 1, the next-heaviest conveyor 2, and so on. That uses the assumption that conveyor 1 finishes first, so we give it the most work.

**Why this helps average order time:**  
By keeping orders that **share totes** on **different** belts, when a tote’s burst comes through, each of those orders can grab its items from a **different** conveyor instead of queuing on the same one. So we reduce waiting and thus lower average order completion time.

**Output:** `Data/algorithm2_tote_overlap_assignment.csv`

---

## Algorithm 3: Minimize Item-Type Overlap Within the Same Belt

**The problem we’re solving:**  
On each conveyor, orders are in a queue: the first order takes the items it needs as they pass, then the next, and so on. If **two orders on the same belt** both need a lot of the **same item type** (e.g. circles), they compete for those circles: the first order grabs what it needs, and the second may have to wait for more circles to come by. That waiting increases order completion time. So we want to **avoid putting two orders that want the same item types on the same belt**.

**What “item-type overlap” means:**  
- Each order has a mix of item types and quantities (e.g. Order A: 3 circles, 2 stars; Order B: 1 circle, 4 stars).  
- For two orders, their **item-type overlap** is: for each item type, take the **smaller** of the two quantities, then add those up. So for circles we add min(3, 1) = 1, for stars min(2, 4) = 2; overlap = 3. This number is high when both orders want a lot of the same types; it’s low or zero when they want different types.

**What the algorithm does (in plain steps):**  
1. For every order, we compute how many units it needs of each item type (circle, pentagon, …, cross). For every **pair** of orders, we compute their item-type overlap as above.  
2. We split all orders into **four groups** (one per conveyor). The **cost** of a group is: for every pair of orders in that group, add their item-type overlap. So a group with many “similar” orders (same types) is bad; we want each group to have **low total item-type overlap**.  
3. We build the four groups **one order at a time**, in a greedy way:  
   - We process orders in a fixed order (e.g. start with orders that overlap a lot with others in terms of item types).  
   - For the next order, we try putting it on conveyor 1, 2, 3, or 4. For each choice we ask: “What would the total item-type overlap on that conveyor become if we add this order?”  
   - We **assign this order to the conveyor that gives the smallest total overlap** (so we keep “similar” orders on different belts). If there’s a tie, we pick the conveyor that currently has **fewest orders**.  
4. After all orders are assigned, we **relabel** the four groups: the group with the **most total units** is conveyor 1, the next-heaviest conveyor 2, and so on (conveyor 1 finishes first, so it gets the heaviest group).

**Why this helps average order time:**  
By keeping orders that **want the same item types** on **different** belts, each belt’s queue has a more diverse mix of demand. When circles (or any type) pass by, they’re not all being claimed by one belt’s competing orders, so we reduce waiting and lower average order completion time.

**Output:** `Data/algorithm3_itemtype_overlap_assignment.csv`

---

## Algorithm 4: Combined Tote + Item-Type Overlap

**The problem we’re solving:**  
The worst situation is when **two orders share a tote and also want the same item types** from that tote. They get their items in the **same burst** (shared tote) and they’re **competing for the same shapes** (e.g. circles). If we put them on the same belt, one order takes its circles from the burst first and the other waits — that’s maximum contention. Algorithm 2 only looks at shared totes; Algorithm 3 only looks at shared item types. Algorithm 4 combines both so we especially **avoid putting “same tote + same types” orders on the same belt**.

**What the “combined overlap” means:**  
- We still use **tote overlap** (number of shared totes) and **item-type overlap** (sum of min quantities per type) as in Algorithms 2 and 3.  
- **Default:** We add item-type overlap to the penalty **only when the two orders share at least one tote**. So: combined = tote_overlap + (itemtype_overlap if they share a tote, else 0). That way we focus on the worst case: same burst **and** same types.  
- **Optional (flag in notebook):** We can instead use a simple sum for every pair: combined = tote_overlap + itemtype_overlap, even when they don’t share a tote.

**What the algorithm does (in plain steps):**  
1. For every order we know its totes and its quantity per item type. For every **pair** of orders we compute the **combined overlap** (tote overlap + item-type overlap, with item-type only when totes overlap in the default mode).  
2. We split all orders into **four groups** (one per conveyor). The **cost** of a group is: for every pair of orders in that group, add their combined overlap. We want each group to have **low total combined overlap**.  
3. We build the four groups **one order at a time**, in a greedy way:  
   - We process orders in a fixed order (e.g. start with orders that have high combined overlap with others).  
   - For the next order, we try conveyor 1, 2, 3, or 4. For each choice we ask: “What would the total combined overlap on that conveyor become if we add this order?”  
   - We **assign this order to the conveyor that gives the smallest total combined overlap**. If there’s a tie, we pick the conveyor with **fewest orders**.  
4. After all orders are assigned, we **relabel** the four groups: the heaviest group (most total units) is conveyor 1, then 2, 3, 4.

**Why this helps average order time:**  
By penalizing both shared totes and (when totes overlap) shared item types, we spread apart the pairs that would hurt the most on the same belt. So we reduce the worst-case waiting (same burst + same types) and can improve average order completion time compared to using only tote overlap or only item-type overlap.

**Output:** `Data/algorithm4_combined_overlap_assignment.csv`

---

## How to Run the Notebook

1. Ensure the three data files are in `Data/`:  
   `order_itemtypes.csv`, `order_quantities.csv`, `orders_totes.csv`.
2. Run cells in order:  
   - First cell: imports.  
   - Second cell: load CSVs and build `orders_queue` and `totes_dict`.  
   - Then run the Algorithm 1 cells (algorithm + export), then Algorithm 2, then 3, then 4.  
3. Each algorithm’s export cell writes its CSV to `Data/` with the filenames listed above.

---

## Summary Table

| Algorithm | What it minimizes on each belt        | Main idea for average order time                    |
|----------|---------------------------------------|-----------------------------------------------------|
| 1        | — (load balance by size)             | Heaviest orders on conveyor 1; round-robin by size |
| 2        | Tote overlap                         | Don’t put orders that share totes on same belt     |
| 3        | Item-type overlap                    | Don’t put orders that want same types on same belt |
| 4        | Tote + item-type (combined)          | Especially avoid same belt when shared tote + same types |

All algorithms (except the pure size-based round-robin in 1) use the **conveyor 1 finishes first** assumption by assigning the **heaviest group** (by total units) to conveyor 1 after partitioning.
