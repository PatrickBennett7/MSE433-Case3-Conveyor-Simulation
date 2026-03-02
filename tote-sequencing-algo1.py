"""
Module 3: Conveyor Simulation with Smart Tote Sequencing
=========================================================
Smart tote selection: at each load opportunity (Conveyor 1, slot 1
is empty), the algorithm scores every remaining tote by how many
units it contains that are CURRENTLY NEEDED by the four active
conveyor orders.  The highest-scoring tote is loaded next.
Ties broken by original tote_id (FIFO).  If no tote helps the
active orders, the algorithm falls back to FIFO.
"""

import pandas as pd
from collections import deque, Counter

# ============================================================
# LOAD AND PARSE INPUT DATA
# ============================================================

items_raw = pd.read_excel('order_itemtypes.xlsx', header=None)
qty_raw   = pd.read_excel('order_quantities.xlsx', header=None)
tote_raw  = pd.read_excel('orders_totes.xlsx', header=None)

orders_queue = deque()
totes_dict   = {}

for order_num in range(len(items_raw)):
    items_row = items_raw.iloc[order_num]
    qty_row   = qty_raw.iloc[order_num]
    tote_row  = tote_raw.iloc[order_num]

    order_items = []
    for col_idx in range(len(items_row)):
        item = items_row.iloc[col_idx]
        qty  = qty_row.iloc[col_idx]
        tote = tote_row.iloc[col_idx]

        if pd.isna(item) or str(item).strip() == '':
            continue

        item = int(float(item))
        qty  = int(float(qty))  if pd.notna(qty)  else 1
        tote = int(float(tote)) if pd.notna(tote) else 0

        order_items.append({'item': item, 'qty': qty, 'tote': tote})

        if tote not in totes_dict:
            totes_dict[tote] = []
        totes_dict[tote].append({'item': item, 'qty': qty})

    if order_items:
        orders_queue.append({'order_num': order_num + 1, 'items': order_items})

# Build tote pool: each tote has its item list and a flat deque for loading
tote_pool = []
for tid, item_list in sorted(totes_dict.items()):
    flat = deque()
    for entry in item_list:
        flat.extend([entry['item']] * entry['qty'])
    tote_pool.append({'tote_id': tid, 'item_list': item_list, 'flat': flat})

total_items = sum(len(t['flat']) for t in tote_pool)

# ============================================================
# PRINT PARSED DATA
# ============================================================

print("ORDERS QUEUE:")
print("=" * 70)
for order in orders_queue:
    print(f"Order {order['order_num']}:")
    for ii in order['items']:
        print(f"  - {ii['qty']} unit(s) of Item Type {ii['item']} -> Tote {ii['tote']}")

print("\n\nTOTES POOL (unsequenced):")
print("=" * 70)
for t in tote_pool:
    print(f"Tote {t['tote_id']}:")
    for ii in t['item_list']:
        print(f"  - {ii['qty']} unit(s) of Item Type {ii['item']}")

print(f"\nTotal items to process: {total_items}")

# ============================================================
# SMART TOTE SEQUENCING ALGORITHM
# ============================================================

def compute_active_demand(active_orders):
    """
    Counter of {item_type: total_units_still_needed}
    across all four currently-active conveyor orders.
    """
    demand = Counter()
    for order in active_orders.values():
        if order['order_num'] is None:
            continue
        for item in order['remaining']:
            demand[item] += 1
    return demand


def score_tote(tote, demand):
    """
    Score = sum of min(qty_in_tote, demand) for each item type.
    Rewards totes that satisfy more of the current active demand.
    """
    score = 0
    for entry in tote['item_list']:
        score += min(entry['qty'], demand.get(entry['item'], 0))
    return score


def pick_best_tote_idx(pool, active_orders):
    """
    Choose the index in `pool` of the tote to load next.
    Highest score wins; ties broken by smallest tote_id (FIFO).
    If no tote scores > 0, returns index 0 (pure FIFO fallback).
    """
    if not pool:
        return None

    demand                         = compute_active_demand(active_orders)
    best_idx, best_score, best_tid = 0, -1, float('inf')

    for i, t in enumerate(pool):
        s   = score_tote(t, demand)
        tid = t['tote_id']
        if s > best_score or (s == best_score and tid < best_tid):
            best_score, best_idx, best_tid = s, i, tid

    return best_idx


# ============================================================
# CONVEYOR SIMULATION STATE
# ============================================================

num_conveyors  = 4
conveyor_time  = 1.0
conveyors      = {i: [None, None] for i in range(1, num_conveyors + 1)}

remaining_orders = list(orders_queue)
next_order_idx   = 0

orders = {
    i: {'order_num': None, 'items': [], 'remaining': [], 'fulfilled': []}
    for i in range(1, num_conveyors + 1)
}


def assign_order_to_conveyor(conveyor_num):
    global next_order_idx
    if next_order_idx < len(remaining_orders):
        order      = remaining_orders[next_order_idx]
        next_order_idx += 1
        items_list = []
        for ii in order['items']:
            items_list.extend([ii['item']] * ii['qty'])
        orders[conveyor_num] = {
            'order_num': order['order_num'],
            'items':     items_list.copy(),
            'remaining': items_list.copy(),
            'fulfilled': []
        }
        return True
    return False


print("\n\nINITIAL CONVEYOR ASSIGNMENTS:")
print("=" * 70)
for c in range(1, num_conveyors + 1):
    assign_order_to_conveyor(c)
    print(f"Conveyor {c} (Order {orders[c]['order_num']}): {orders[c]['items']}")

# ============================================================
# TOTE LOADER: live smart selection
# ============================================================

current_tote    = None   # tote currently being drained
chosen_seq_log  = []     # tote_ids selected, in order


def next_item_to_load():
    """
    Return the next item to place on Conveyor 1, or None when done.
    Picks the best tote dynamically based on current active demand,
    then drains items from it one-by-one.
    """
    global current_tote, tote_pool

    # Advance to the next tote when current one is empty
    while current_tote is None or len(current_tote['flat']) == 0:
        if not tote_pool:
            return None
        idx          = pick_best_tote_idx(tote_pool, orders)
        current_tote = tote_pool.pop(idx)
        chosen_seq_log.append(current_tote['tote_id'])

    return current_tote['flat'].popleft()


# ============================================================
# SIMULATION STEP
# ============================================================

def simulate_conveyor_step():
    """One half-time-unit step of the conveyor system."""
    added_items             = []
    conveyors_received_item = set()

    if conveyors[num_conveyors][1] is not None:
        # Loop-back: item exits conveyor 4 and re-enters conveyor 1
        loop_item = conveyors[num_conveyors][1]
        conveyors[num_conveyors][1] = None

        for cascade_idx in range(num_conveyors - 1, 0, -1):
            if conveyors[cascade_idx][1] is not None:
                cascade_item              = conveyors[cascade_idx][1]
                conveyors[cascade_idx][1] = None
                conveyors[cascade_idx + 1][1] = conveyors[cascade_idx + 1][0]
                conveyors[cascade_idx + 1][0] = cascade_item
                conveyors_received_item.add(cascade_idx + 1)
                added_items.append(
                    f"Item {cascade_item} moved from Conveyor {cascade_idx} "
                    f"slot 2 to Conveyor {cascade_idx + 1} slot 1"
                )

        conveyors[1][1] = conveyors[1][0]
        conveyors[1][0] = loop_item
        conveyors_received_item.add(1)
        added_items.append(
            f"Item {loop_item} moved from Conveyor {num_conveyors} "
            f"slot 2 back to Conveyor 1 slot 1 (LOOP)"
        )
    else:
        for ci in range(num_conveyors, 0, -1):
            if conveyors[ci][1] is not None:
                item = conveyors[ci][1]
                conveyors[ci][1] = None
                if ci < num_conveyors:
                    conveyors[ci + 1][1] = conveyors[ci + 1][0]
                    conveyors[ci + 1][0] = item
                    conveyors_received_item.add(ci + 1)
                    added_items.append(
                        f"Item {item} moved from Conveyor {ci} slot 2 "
                        f"to Conveyor {ci + 1} slot 1"
                    )

    # Advance slot 1 → slot 2 within each conveyor (if slot 2 free)
    for ci in range(1, num_conveyors + 1):
        if ci not in conveyors_received_item:
            if conveyors[ci][0] is not None and conveyors[ci][1] is None:
                item             = conveyors[ci][0]
                conveyors[ci][1] = item
                conveyors[ci][0] = None
                added_items.append(
                    f"Item {item} moved within Conveyor {ci} from slot 1 to slot 2"
                )

    # Load next item onto Conveyor 1 slot 1 using smart tote selection
    if conveyors[1][0] is None:
        item_type = next_item_to_load()
        if item_type is not None:
            conveyors[1][0] = item_type
            added_items.append(f"Item {item_type} ADDED to Conveyor 1 slot 1")

    return added_items


def scan_and_remove_items():
    """Scan slot 2 of each conveyor; remove item if it matches the active order."""
    items_removed    = []
    orders_completed = []

    for ci in range(1, num_conveyors + 1):
        item_type = conveyors[ci][1]
        if item_type is None or orders[ci]['order_num'] is None:
            continue
        if item_type in orders[ci]['remaining']:
            current_order_num  = orders[ci]['order_num']
            conveyors[ci][1]   = None
            orders[ci]['remaining'].remove(item_type)
            orders[ci]['fulfilled'].append(item_type)
            items_removed.append((ci, item_type, current_order_num))

            if len(orders[ci]['remaining']) == 0:
                completed = current_order_num
                if assign_order_to_conveyor(ci):
                    orders_completed.append(
                        (ci, completed,
                         orders[ci]['order_num'],
                         orders[ci]['remaining'].copy())
                    )
                else:
                    orders_completed.append((ci, completed, None, None))

    return items_removed, orders_completed


# ============================================================
# RUN SIMULATION
# ============================================================

time                 = 0.0
completed_orders_log = []

print("\n" + "=" * 70)
print("Conveyor System Simulation with Smart Tote Sequencing")
print("=" * 70)

for step in range(total_items * 20):
    added_items                      = simulate_conveyor_step()
    time                            += conveyor_time / 2
    items_removed, orders_completed  = scan_and_remove_items()

    print(f"\n\nTime {time:.1f}:")
    for c_id in range(1, num_conveyors + 1):
        s1 = conveyors[c_id][0] if conveyors[c_id][0] is not None else ''
        s2 = conveyors[c_id][1] if conveyors[c_id][1] is not None else ''
        print(f"  Conveyor {c_id}: [{s1}, {s2}]")

    for msg in added_items:
        print(f"  >> {msg}")

    for conv_id, item_type, order_id in items_removed:
        print(f"  ** Item {item_type} REMOVED from Conveyor {conv_id} for Order {order_id}")

    for conv_id, completed_order, new_order, new_items in orders_completed:
        completed_orders_log.append(
            {'order_num': completed_order, 'time': time, 'conveyor': conv_id}
        )
        if new_order is not None:
            print(f"  *** ORDER {completed_order} COMPLETE on Conveyor {conv_id}! "
                  f"New Order {new_order} assigned: {new_items}")
        else:
            print(f"  *** ORDER {completed_order} COMPLETE on Conveyor {conv_id}! "
                  f"No more orders to assign.")

    # Termination: all totes loaded, belt empty, all active orders done
    totes_done  = (not tote_pool and
                   (current_tote is None or len(current_tote['flat']) == 0))
    belt_empty  = all(conveyors[c][0] is None and conveyors[c][1] is None
                      for c in range(1, num_conveyors + 1))
    orders_done = all(orders[c]['order_num'] is None
                      or len(orders[c]['remaining']) == 0
                      for c in range(1, num_conveyors + 1))
    if totes_done and belt_empty and orders_done:
        break

# ============================================================
# RESULTS
# ============================================================

print("\n" + "=" * 70)
print("Tote Loading Sequence (smart order):")
for i, tid in enumerate(chosen_seq_log, 1):
    print(f"  {i:2d}. Tote {tid}")

print("\n" + "=" * 70)
print("Order Fulfillment Summary:")
print(f"Total orders processed: {next_order_idx}")
print("\nCompleted Orders:")
for entry in sorted(completed_orders_log, key=lambda x: x['order_num']):
    print(f"  Order {entry['order_num']}: Completed at Time {entry['time']:.1f} "
          f"on Conveyor {entry['conveyor']}")

if completed_orders_log:
    total_time = max(e['time'] for e in completed_orders_log)
    avg_time   = sum(e['time'] for e in completed_orders_log) / len(completed_orders_log)
    print(f"\nTotal time to complete all orders: {total_time:.1f}")
    print(f"Average completion time per order:  {avg_time:.1f}")

# ============================================================
# EXPORT SOLUTION CSV
# ============================================================

shape_names = {
    0: 'circle', 1: 'pentagon', 2: 'trapezoid', 3: 'triangle',
    4: 'star',   5: 'moon',     6: 'heart',     7: 'cross'
}

# Build tote -> queue position mapping from chosen_seq_log
# chosen_seq_log is the ordered list of tote_ids loaded one-by-one
# through the single entry point at Conveyor 1 slot 1
tote_queue_position = {tid: idx for idx, tid in enumerate(chosen_seq_log)}

all_item_types_export = sorted(shape_names.keys())
export_data = []

for order in remaining_orders:
    on = order['order_num']

    # Find queue position of the earliest tote loaded for this order
    tote_ids_for_order = [ii['tote'] for ii in order['items']]
    queue_positions    = [tote_queue_position[t] for t in tote_ids_for_order
                          if t in tote_queue_position]
    conv_num = min(queue_positions) if queue_positions else -1

    row = {'conv_num': conv_num}
    for it in all_item_types_export:
        row[shape_names[it]] = 0
    for ii in order['items']:
        row[shape_names.get(ii['item'], f"item_{ii['item']}")] += ii['qty']
    export_data.append(row)

export_df  = pd.DataFrame(export_data)
shape_cols = [shape_names[i] for i in all_item_types_export]
export_df  = export_df[['conv_num'] + shape_cols]

# Sort rows by conv_num to reflect the single physical queue order
export_df = export_df.sort_values('conv_num').reset_index(drop=True)

export_df.to_csv('solution_output.csv', index=False)

print("\n\nSolution saved to solution_output.csv")
print(export_df.to_string(index=False))