#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np


# In[2]:


# Read the raw CSVs
items_raw = pd.read_csv('Data/raw/order_itemtypes.csv', header=None)
qty_raw = pd.read_csv('Data/raw/order_quantities.csv', header=None)
tote_raw = pd.read_csv('Data/raw/orders_totes.csv', header=None)

# Add index column at the beginning
items_df = pd.concat([pd.Series(range(len(items_raw)), name='Index'), items_raw], axis=1)
qty_df = pd.concat([pd.Series(range(len(qty_raw)), name='Index'), qty_raw], axis=1)
tote_df = pd.concat([pd.Series(range(len(tote_raw)), name='Index'), tote_raw], axis=1)

# Create queues for orders and totes
from collections import deque
orders_queue = deque()
totes_queue = deque()
totes_dict = {}  # To group items by tote

# Process each order (row)
for order_num in range(len(items_df)):
    items_row = items_df.iloc[order_num]
    qty_row = qty_df.iloc[order_num]
    tote_row = tote_df.iloc[order_num]

    order_items = []

    # Process each column (skip column 0 which is now the index)
    for col_idx in range(1, len(items_row)):
        item = items_row.iloc[col_idx]
        qty = qty_row.iloc[col_idx]
        tote = tote_row.iloc[col_idx]

        # Skip empty cells (Weird that some totes are empty)
        if pd.isna(item) or str(item).strip() == '':
            continue

        item = int(float(item))
        qty = int(float(qty)) if pd.notna(qty) else 1
        tote = int(float(tote)) if pd.notna(tote) else 0

        # Add to order items
        order_items.append({'item': item, 'qty': qty, 'tote': tote})

        # Add to totes dictionary
        if tote not in totes_dict:
            totes_dict[tote] = []
        totes_dict[tote].append({'item': item, 'qty': qty})

    # Append order to queue if it has items
    if order_items:
        orders_queue.append({'order_num': order_num + 1, 'items': order_items})

# Create totes queue from totes dictionary
for tote_id in sorted(totes_dict.keys()):
    totes_queue.append({'tote_id': tote_id, 'items': totes_dict[tote_id]})

print("ORDERS QUEUE:")
print("=" * 70)
for order in orders_queue:
    print(f"Order {order['order_num']}:")
    for item_info in order['items']:
        print(f"  - {item_info['qty']} unit(s) of Item Type {item_info['item']} -> Tote {item_info['tote']}")

print("\n\nTOTES QUEUE:")
print("=" * 70)
for tote in totes_queue:
    print(f"Tote {tote['tote_id']}:")
    for item_info in tote['items']:
        print(f"  - {item_info['qty']} unit(s) of Item Type {item_info['item']}")


# In[3]:


# =============================================================================
# Algorithm 1: Load balancing by order size
# Assumption: Conveyor 1 completes before 2, 2 before 3, 3 before 4 (items travel
# longer on later conveyors). So we assign largest orders to conveyor 1 first,
# then 2, 3, 4 in round-robin so that conveyor 1 gets the heaviest load and
# completion times are better balanced.
# =============================================================================

NUM_CONVEYORS = 4
# Item type index -> CSV column name (user mapping: Circle=1, pentagon=2, ...)
SHAPE_COLS = ['circle', 'pentagon', 'trapezoid', 'triangle', 'star', 'moon', 'heart', 'cross']  # item types 0..7

# Compute order size (total units) for each order
orders_list = list(orders_queue)
for order in orders_list:
    order['total_units'] = sum(item['qty'] for item in order['items'])

# Sort by size descending (largest first)
orders_sorted = sorted(orders_list, key=lambda o: o['total_units'], reverse=True)

# Assign to conveyors 1..4 in round-robin (order 1 -> conv 1, order 2 -> conv 2, ...)
conveyor_orders = {c: [] for c in range(1, NUM_CONVEYORS + 1)}
for i, order in enumerate(orders_sorted):
    conv = (i % NUM_CONVEYORS) + 1
    conveyor_orders[conv].append(order)

print("Load balancing assignment (largest orders first, round-robin to conv 1,2,3,4):")
print("=" * 60)
for c in range(1, NUM_CONVEYORS + 1):
    orders_on_c = conveyor_orders[c]
    sizes = [o['total_units'] for o in orders_on_c]
    print(f"Conveyor {c}: orders {[o['order_num'] for o in orders_on_c]} (sizes: {sizes})")


# In[4]:


# Export Algorithm 2 assignment to CSV  
def order_to_shape_row(order):
    """Build list of 8 quantities (item types 0..7) for one order."""
    row = [0] * 8
    for it in order['items']:
        item_type = int(it['item'])
        qty = it['qty']
        if 0 <= item_type < 8:
            row[item_type] += qty
    return row

rows = []
for conv_num in range(1, NUM_CONVEYORS + 1):
    for order in conveyor_orders[conv_num]:
        shape_row = order_to_shape_row(order)
        rows.append([conv_num] + shape_row)

out_df = pd.DataFrame(rows, columns=['conv_num'] + SHAPE_COLS)
out_path = 'Data/order_sequencing/algorithm1_load_balance_assignment.csv'
out_df.to_csv(out_path, index=False)
print(f"Saved to {out_path}")
print(out_df.to_string())


# In[5]:


# =============================================================================
# Algorithm 1b: Stratified load balance (banded by order size, minimax)
# Sort orders by size; split into 4 contiguous groups to minimize max group sum.
# strict_boundary = False: equal-sized orders may split across adjacent groups.
# =============================================================================

STRICT_BOUNDARY = False  # allow equal-sized orders to split across groups

# Reuse orders_list with total_units (from Algorithm 1 cell)
orders_sorted_1b = sorted(orders_list, key=lambda o: o['total_units'])  # ascending: smallest first
sizes_1b = [o['total_units'] for o in orders_sorted_1b]
n = len(orders_sorted_1b)

best_max = float('inf')
best_cuts = (None, None, None)
for i in range(1, n - 2):
    for j in range(i + 1, n - 1):
        for k in range(j + 1, n):
            S1 = sum(sizes_1b[0:i])
            S2 = sum(sizes_1b[i:j])
            S3 = sum(sizes_1b[j:k])
            S4 = sum(sizes_1b[k:n])
            M = max(S1, S2, S3, S4)
            if M < best_max:
                best_max = M
                best_cuts = (i, j, k)

i, j, k = best_cuts
conveyor_orders_1b = {
    1: orders_sorted_1b[0:i],
    2: orders_sorted_1b[i:j],
    3: orders_sorted_1b[j:k],
    4: orders_sorted_1b[k:n],
}

print("Stratified load balance (banded by size, minimax; strict_boundary=False):")
print("=" * 60)
for c in range(1, NUM_CONVEYORS + 1):
    orders_on_c = conveyor_orders_1b[c]
    sizes = [o['total_units'] for o in orders_on_c]
    print(f"Conveyor {c}: orders {[o['order_num'] for o in orders_on_c]} (sizes: {sizes})")

# Export to CSV (same format as Algorithm 1)
rows_1b = []
for conv_num in range(1, NUM_CONVEYORS + 1):
    for order in conveyor_orders_1b[conv_num]:
        shape_row = order_to_shape_row(order)
        rows_1b.append([conv_num] + shape_row)
out_df_1b = pd.DataFrame(rows_1b, columns=['conv_num'] + SHAPE_COLS)
out_path_1b = 'Data/order_sequencing/algorithm1b_stratified_balance_assignment.csv'
out_df_1b.to_csv(out_path_1b, index=False)
print(f"\nSaved to {out_path_1b}")
print(out_df_1b.to_string())


# In[6]:


# =============================================================================
# Algorithm 2: Minimize tote overlap within the same belt
# Orders that share totes get their items in the same "burst"; putting them on
# the same belt makes one wait. We partition orders into 4 groups to minimize
# total within-group overlap (shared totes).
# Conveyor order: conveyor 1 finishes before 2 before 3 before 4 (items travel
# farther on later conveyors). After partitioning, we assign the heaviest group
# (most total units) to conveyor 1, next to 2, etc., so conveyor 1 gets more work.
# =============================================================================

# Reuse constants from Algorithm 1
orders_list_algo2 = list(orders_queue)

# Per order: set of totes and (optional) units per tote for overlap metric
for order in orders_list_algo2:
    order['totes'] = set()
    order['tote_units'] = {}  # tote_id -> total qty from that tote
    for it in order['items']:
        t = it['tote']
        q = it['qty']
        order['totes'].add(t)
        order['tote_units'][t] = order['tote_units'].get(t, 0) + q

# Overlap between two orders: count of shared totes (or use total units from shared totes)
def overlap_orders(o1, o2):
    shared = o1['totes'] & o2['totes']
    # Metric: number of shared totes
    return len(shared)

# Build overlap "matrix" (dict of (i,j) -> overlap for order indices)
order_nums = [o['order_num'] for o in orders_list_algo2]
overlap = {}
for i, o1 in enumerate(orders_list_algo2):
    for j in range(i + 1, len(orders_list_algo2)):
        o2 = orders_list_algo2[j]
        ov = overlap_orders(o1, o2)
        overlap[(i, j)] = ov
        overlap[(j, i)] = ov

# Greedy partition: assign each order to the belt that minimizes increase in within-group overlap
# Process orders by total overlap with others (descending) so high-overlap orders get placed first
total_overlap_per_order = [sum(overlap.get((i, j), 0) for j in range(len(orders_list_algo2)) if j != i) for i in range(len(orders_list_algo2))]
order_indices_sorted = sorted(range(len(orders_list_algo2)), key=lambda i: total_overlap_per_order[i], reverse=True)

conveyor_orders_algo2 = {c: [] for c in range(1, NUM_CONVEYORS + 1)}

def within_group_overlap(belt_orders):
    """Total pairwise overlap among orders on this belt."""
    total = 0
    for i, o1 in enumerate(belt_orders):
        idx1 = orders_list_algo2.index(o1)
        for o2 in belt_orders[i + 1:]:
            idx2 = orders_list_algo2.index(o2)
            total += overlap.get((idx1, idx2), 0)
    return total

for idx in order_indices_sorted:
    order = orders_list_algo2[idx]
    best_conv = None
    best_new_overlap = float('inf')
    for c in range(1, NUM_CONVEYORS + 1):
        belt = conveyor_orders_algo2[c]
        new_belt = belt + [order]
        new_overlap = within_group_overlap(new_belt)
        # Minimize overlap; on tie, prefer conveyor with fewest orders (load balance)
        if best_conv is None or new_overlap < best_new_overlap:
            best_new_overlap = new_overlap
            best_conv = c
        elif new_overlap == best_new_overlap and len(belt) < len(conveyor_orders_algo2[best_conv]):
            best_conv = c
    conveyor_orders_algo2[best_conv].append(order)

# Conveyor 1 finishes before 2 before 3 before 4: assign heaviest group to conveyor 1
def total_units_order(o):
    return sum(it['qty'] for it in o['items'])
units_per_conv = {c: sum(total_units_order(o) for o in conveyor_orders_algo2[c]) for c in range(1, NUM_CONVEYORS + 1)}
conv_by_work = sorted(range(1, NUM_CONVEYORS + 1), key=lambda c: units_per_conv[c], reverse=True)
conveyor_orders_algo2 = {new_c: conveyor_orders_algo2[old_c] for new_c, old_c in enumerate(conv_by_work, start=1)}

print("Minimize tote overlap assignment (heaviest group -> conveyor 1, ...):")
print("=" * 60)
for c in range(1, NUM_CONVEYORS + 1):
    orders_on_c = conveyor_orders_algo2[c]
    print(f"Conveyor {c}: orders {[o['order_num'] for o in orders_on_c]}")
    # Show within-group overlap for this belt
    w = within_group_overlap(orders_on_c)
    print(f"  -> within-group overlap = {w}")


# In[7]:


# Export Algorithm 2 assignment to CSV 
rows_algo2 = []
for conv_num in range(1, NUM_CONVEYORS + 1):
    for order in conveyor_orders_algo2[conv_num]:
        shape_row = order_to_shape_row(order)
        rows_algo2.append([conv_num] + shape_row)

out_df_algo2 = pd.DataFrame(rows_algo2, columns=['conv_num'] + SHAPE_COLS)
out_path_algo2 = 'Data/order_sequencing/algorithm2_tote_overlap_assignment.csv'
out_df_algo2.to_csv(out_path_algo2, index=False)
print(f"Saved to {out_path_algo2}")
print(out_df_algo2.to_string())


# In[8]:


# =============================================================================
# Algorithm 3: Minimize item-type overlap within the same belt
# Orders that want the same item types (e.g. both circle-heavy) compete for those
# items when they pass; putting them on the same belt serializes fulfillment.
# We partition orders into 4 groups to minimize within-group item-type overlap.
# Conveyor order: conveyor 1 finishes before 2 before 3 before 4; assign heaviest
# group to conveyor 1, etc.
# =============================================================================

orders_list_algo3 = list(orders_queue)

# Per order: quantities per item type (0..7)
for order in orders_list_algo3:
    order['item_type_qty'] = [0] * 8
    for it in order['items']:
        t = int(it['item'])
        if 0 <= t < 8:
            order['item_type_qty'][t] += it['qty']

# Overlap between two orders: sum over item types of min(qty1[t], qty2[t]) ("contention" units)
def overlap_itemtype(o1, o2):
    return sum(min(o1['item_type_qty'][t], o2['item_type_qty'][t]) for t in range(8))

# Build overlap matrix by order index
overlap_it = {}
for i, o1 in enumerate(orders_list_algo3):
    for j in range(i + 1, len(orders_list_algo3)):
        o2 = orders_list_algo3[j]
        ov = overlap_itemtype(o1, o2)
        overlap_it[(i, j)] = ov
        overlap_it[(j, i)] = ov

# Greedy partition: assign to belt that minimizes increase in within-group item-type overlap
total_overlap_it = [sum(overlap_it.get((i, j), 0) for j in range(len(orders_list_algo3)) if j != i) for i in range(len(orders_list_algo3))]
order_indices_sorted_it = sorted(range(len(orders_list_algo3)), key=lambda i: total_overlap_it[i], reverse=True)

conveyor_orders_algo3 = {c: [] for c in range(1, NUM_CONVEYORS + 1)}

def within_group_overlap_it(belt_orders):
    total = 0
    for i, o1 in enumerate(belt_orders):
        idx1 = orders_list_algo3.index(o1)
        for o2 in belt_orders[i + 1:]:
            idx2 = orders_list_algo3.index(o2)
            total += overlap_it.get((idx1, idx2), 0)
    return total

for idx in order_indices_sorted_it:
    order = orders_list_algo3[idx]
    best_conv = None
    best_new_overlap = float('inf')
    for c in range(1, NUM_CONVEYORS + 1):
        belt = conveyor_orders_algo3[c]
        new_belt = belt + [order]
        new_overlap = within_group_overlap_it(new_belt)
        if best_conv is None or new_overlap < best_new_overlap:
            best_new_overlap = new_overlap
            best_conv = c
        elif new_overlap == best_new_overlap and len(belt) < len(conveyor_orders_algo3[best_conv]):
            best_conv = c
    conveyor_orders_algo3[best_conv].append(order)

# Conveyor 1 finishes first: assign heaviest group to conveyor 1
units_per_conv3 = {c: sum(sum(it['qty'] for it in o['items']) for o in conveyor_orders_algo3[c]) for c in range(1, NUM_CONVEYORS + 1)}
conv_by_work3 = sorted(range(1, NUM_CONVEYORS + 1), key=lambda c: units_per_conv3[c], reverse=True)
conveyor_orders_algo3 = {new_c: conveyor_orders_algo3[old_c] for new_c, old_c in enumerate(conv_by_work3, start=1)}

print("Minimize item-type overlap assignment (heaviest group -> conveyor 1, ...):")
print("=" * 60)
for c in range(1, NUM_CONVEYORS + 1):
    orders_on_c = conveyor_orders_algo3[c]
    print(f"Conveyor {c}: orders {[o['order_num'] for o in orders_on_c]}")
    w = within_group_overlap_it(orders_on_c)
    print(f"  -> within-group item-type overlap = {w}")


# In[9]:


# Export Algorithm 3 assignment to CSV (same format as Algorithms 1 and 2)
rows_algo3 = []
for conv_num in range(1, NUM_CONVEYORS + 1):
    for order in conveyor_orders_algo3[conv_num]:
        shape_row = order_to_shape_row(order)
        rows_algo3.append([conv_num] + shape_row)

out_df_algo3 = pd.DataFrame(rows_algo3, columns=['conv_num'] + SHAPE_COLS)
out_path_algo3 = 'Data/order_sequencing/algorithm3_itemtype_overlap_assignment.csv'
out_df_algo3.to_csv(out_path_algo3, index=False)
print(f"Saved to {out_path_algo3}")
print(out_df_algo3.to_string())


# In[10]:


# =============================================================================
# Algorithm 4: Combined tote overlap + item-type overlap for belt assignment
# Metric: tote_overlap(A,B) + itemtype_overlap(A,B) when they share totes (same burst),
# else just tote_overlap. So we only add item-type contention when orders share a tote.
# Alternative (use_combined_sum=True): simple sum tote_overlap + itemtype_overlap always.
# Conveyor order: heaviest group -> conveyor 1, etc.
# =============================================================================

orders_list_algo4 = list(orders_queue)

# Per order: totes set and item_type_qty
for order in orders_list_algo4:
    order['totes'] = set(it['tote'] for it in order['items'])
    order['item_type_qty'] = [0] * 8
    for it in order['items']:
        t = int(it['item'])
        if 0 <= t < 8:
            order['item_type_qty'][t] += it['qty']

def tote_overlap(o1, o2):
    return len(o1['totes'] & o2['totes'])

def itemtype_overlap(o1, o2):
    return sum(min(o1['item_type_qty'][t], o2['item_type_qty'][t]) for t in range(8))

# Combined: item-type overlap only when totes overlap (worst case = same burst + same types)
USE_ITEMTYPE_ONLY_WHEN_TOTES_OVERLAP = True  # False = simple sum tote + itemtype always

def combined_overlap(o1, o2):
    tote_ov = tote_overlap(o1, o2)
    it_ov = itemtype_overlap(o1, o2)
    if USE_ITEMTYPE_ONLY_WHEN_TOTES_OVERLAP:
        return tote_ov + (it_ov if tote_ov > 0 else 0)
    return tote_ov + it_ov

overlap_comb = {}
for i, o1 in enumerate(orders_list_algo4):
    for j in range(i + 1, len(orders_list_algo4)):
        o2 = orders_list_algo4[j]
        ov = combined_overlap(o1, o2)
        overlap_comb[(i, j)] = ov
        overlap_comb[(j, i)] = ov

total_overlap_comb = [sum(overlap_comb.get((i, j), 0) for j in range(len(orders_list_algo4)) if j != i) for i in range(len(orders_list_algo4))]
order_indices_sorted_comb = sorted(range(len(orders_list_algo4)), key=lambda i: total_overlap_comb[i], reverse=True)

conveyor_orders_algo4 = {c: [] for c in range(1, NUM_CONVEYORS + 1)}

def within_group_overlap_comb(belt_orders):
    total = 0
    for i, o1 in enumerate(belt_orders):
        idx1 = orders_list_algo4.index(o1)
        for o2 in belt_orders[i + 1:]:
            idx2 = orders_list_algo4.index(o2)
            total += overlap_comb.get((idx1, idx2), 0)
    return total

for idx in order_indices_sorted_comb:
    order = orders_list_algo4[idx]
    best_conv = None
    best_new_overlap = float('inf')
    for c in range(1, NUM_CONVEYORS + 1):
        belt = conveyor_orders_algo4[c]
        new_belt = belt + [order]
        new_overlap = within_group_overlap_comb(new_belt)
        if best_conv is None or new_overlap < best_new_overlap:
            best_new_overlap = new_overlap
            best_conv = c
        elif new_overlap == best_new_overlap and len(belt) < len(conveyor_orders_algo4[best_conv]):
            best_conv = c
    conveyor_orders_algo4[best_conv].append(order)

# Conveyor 1 finishes first: assign heaviest group to conveyor 1
units_per_conv4 = {c: sum(sum(it['qty'] for it in o['items']) for o in conveyor_orders_algo4[c]) for c in range(1, NUM_CONVEYORS + 1)}
conv_by_work4 = sorted(range(1, NUM_CONVEYORS + 1), key=lambda c: units_per_conv4[c], reverse=True)
conveyor_orders_algo4 = {new_c: conveyor_orders_algo4[old_c] for new_c, old_c in enumerate(conv_by_work4, start=1)}

mode = "item-type only when totes overlap" if USE_ITEMTYPE_ONLY_WHEN_TOTES_OVERLAP else "tote + item-type (simple sum)"
print(f"Combined overlap assignment ({mode}), heaviest group -> conveyor 1:")
print("=" * 60)
for c in range(1, NUM_CONVEYORS + 1):
    orders_on_c = conveyor_orders_algo4[c]
    print(f"Conveyor {c}: orders {[o['order_num'] for o in orders_on_c]}")
    w = within_group_overlap_comb(orders_on_c)
    print(f"  -> within-group combined overlap = {w}")


# In[11]:


# Export Algorithm 4 assignment to CSV (same format as Algorithms 1–3)
rows_algo4 = []
for conv_num in range(1, NUM_CONVEYORS + 1):
    for order in conveyor_orders_algo4[conv_num]:
        shape_row = order_to_shape_row(order)
        rows_algo4.append([conv_num] + shape_row)

out_df_algo4 = pd.DataFrame(rows_algo4, columns=['conv_num'] + SHAPE_COLS)
out_path_algo4 = 'Data/order_sequencing/algorithm4_combined_overlap_assignment.csv'
out_df_algo4.to_csv(out_path_algo4, index=False)
print(f"Saved to {out_path_algo4}")
print(out_df_algo4.to_string())

