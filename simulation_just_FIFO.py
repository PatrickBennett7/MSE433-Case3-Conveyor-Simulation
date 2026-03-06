#!/usr/bin/env python
# coding: utf-8

# ### Module 3: Conveyor Simulation  

# In[1]:


import pandas as pd
import numpy as np


# #### Clean Up the Input Data

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


# ### Simulate the Conveyor Belts

# In[3]:


# Initialize conveyor system with first 4 orders from data
from collections import deque

num_conveyors = 4
slots_per_conveyor = 2
conveyor_time = 1.0  # time units for item to traverse one conveyor (will modify later)
scan_interval = conveyor_time / 2  # Scan at each 0.5 second interval

# Create conveyors as lists with 2 slots each (None = empty)
conveyors = {i: [None, None] for i in range(1, num_conveyors + 1)}

# Build orders from orders_queue and item sequence from totes_queue
# ORDERS: What each conveyor should receive (from orders_queue, first 4 orders)
# ITEM SEQUENCE: The order items are loaded into the system (from totes_queue, in tote order)

assumed_item_order = []

# Create a working copy of orders_queue for assignment
remaining_orders = list(orders_queue)
next_order_idx = 0  # Track which order to assign next

# Orders dict now also tracks order_num
orders = {1: {'order_num': None, 'items': [], 'remaining': [], 'fulfilled': []},
          2: {'order_num': None, 'items': [], 'remaining': [], 'fulfilled': []},
          3: {'order_num': None, 'items': [], 'remaining': [], 'fulfilled': []},
          4: {'order_num': None, 'items': [], 'remaining': [], 'fulfilled': []}}

def assign_order_to_conveyor(conveyor_num):
    """Assign the next available order to a conveyor"""
    global next_order_idx

    if next_order_idx < len(remaining_orders):
        order = remaining_orders[next_order_idx]
        next_order_idx += 1

        # Build the items list fresh
        items_list = []
        for item_info in order['items']:
            item = item_info['item']
            qty = item_info['qty']
            for _ in range(qty):
                items_list.append(item)

        # Create a completely new order entry
        orders[conveyor_num] = {
            'order_num': order['order_num'],
            'items': items_list.copy(),  # Original items (for reference)
            'remaining': items_list.copy(),  # Items still needed
            'fulfilled': []
        }

        return True
    return False

# Print all orders
print("ALL ORDERS (expanded with quantities):")
print("=" * 70)
for order in remaining_orders:
    items_list = []
    for item_info in order['items']:
        for _ in range(item_info['qty']):
            items_list.append(item_info['item'])
    print(f"Order {order['order_num']}: {items_list}")

# Assign first 4 orders to conveyors
print("\nINITIAL CONVEYOR ASSIGNMENTS:")
print("=" * 70)

for conveyor_num in range(1, num_conveyors + 1):
    assign_order_to_conveyor(conveyor_num)
    print(f"Conveyor {conveyor_num} (Order {orders[conveyor_num]['order_num']}): {orders[conveyor_num]['items']}")

# Build item sequence from ALL totes in totes_queue
# Items are loaded in tote order (Tote 0, then Tote 1, etc.)
print("\n\nITEM SEQUENCE (from totes_queue - order items are loaded):")
print("=" * 70)

# Get ALL totes and build sequence
all_totes = list(totes_queue)

for tote_info in all_totes:
    tote_id = tote_info['tote_id']
    tote_items = []

    for item_info in tote_info['items']:
        item = item_info['item']
        qty = item_info['qty']

        # Add items to sequence (repeat by quantity)
        for _ in range(qty):
            assumed_item_order.append(item)
            tote_items.append(item)

    print(f"Tote {tote_id}: {tote_items}")

# Track orders and fulfillment
time = 0
item_counter = 0
total_items = len(assumed_item_order)
completed_orders_log = []  # Track when each order was completed

print("\n" + "=" * 70)
print(f"Total items to process: {total_items}")
print(f"\nFull item sequence (loaded in tote order): {assumed_item_order}")
print("\n" + "=" * 70)

def scan_and_remove_items():
    """
    Scan the second slot (index 1) of each conveyor.
    Each order is only fulfilled from its corresponding conveyor.
    When an order is complete, assign the next order to that conveyor.
    """
    global orders
    items_removed = []
    orders_completed = []  # Track completed orders for later printing

    for conveyor_idx in range(1, num_conveyors + 1):
        item_type = conveyors[conveyor_idx][1]  # Check slot 2

        # Skip if no item or no order assigned
        if item_type is None or orders[conveyor_idx]['order_num'] is None:
            continue

        # Check if this item type is still needed for the current order
        if item_type in orders[conveyor_idx]['remaining']:
            # Capture current order number
            current_order_num = orders[conveyor_idx]['order_num']

            # Remove item from belt
            conveyors[conveyor_idx][1] = None

            # Remove ONE instance from remaining and add to fulfilled
            orders[conveyor_idx]['remaining'].remove(item_type)
            orders[conveyor_idx]['fulfilled'].append(item_type)
            items_removed.append((conveyor_idx, item_type, current_order_num))

            # Check if order is complete (no remaining items)
            if len(orders[conveyor_idx]['remaining']) == 0:
                completed_order_num = current_order_num

                # Assign next order to this conveyor
                if assign_order_to_conveyor(conveyor_idx):
                    orders_completed.append((conveyor_idx, completed_order_num, orders[conveyor_idx]['order_num'], orders[conveyor_idx]['remaining'].copy()))
                else:
                    orders_completed.append((conveyor_idx, completed_order_num, None, None))

    return items_removed, orders_completed

def simulate_conveyor_step(item_counter):
    """
    At each time step (conveyor_time/2 intervals):
    1. Move items from conveyor N slot 2 to conveyor N+1 slot 1 (reverse order to avoid conflicts)
    2. Move items from slot 1 to slot 2 within each conveyor (if slot 2 is empty)
       - But NOT for conveyors that just received items in step 1
    3. Add new item to conveyor 1, slot 1
    """
    added_items = []
    conveyors_received_item = set()  # Track which conveyors just received items
    already_processed_slot2 = set()  # Track conveyors whose slot 2 was already processed

    # Step 1: First handle the loop-back from Conveyor 4 to Conveyor 1 (if applicable)
    # This needs special handling because it affects all conveyors
    if conveyors[num_conveyors][1] is not None:
        loop_item = conveyors[num_conveyors][1]
        conveyors[num_conveyors][1] = None
        already_processed_slot2.add(num_conveyors)

        # Before inserting at Conveyor 1, we need to cascade all items forward
        # Move all slot 2 items to next conveyor (3->4, 2->3, 1->2)
        for cascade_idx in range(num_conveyors - 1, 0, -1):
            if conveyors[cascade_idx][1] is not None:
                cascade_item = conveyors[cascade_idx][1]
                conveyors[cascade_idx][1] = None
                already_processed_slot2.add(cascade_idx)

                # Push to next conveyor
                conveyors[cascade_idx + 1][1] = conveyors[cascade_idx + 1][0]
                conveyors[cascade_idx + 1][0] = cascade_item
                conveyors_received_item.add(cascade_idx + 1)
                added_items.append(f"Item {cascade_item} moved from Conveyor {cascade_idx} slot 2 to Conveyor {cascade_idx + 1} slot 1")

        # Now insert the looped item at Conveyor 1
        conveyors[1][1] = conveyors[1][0]
        conveyors[1][0] = loop_item
        conveyors_received_item.add(1)
        added_items.append(f"Item {loop_item} moved from Conveyor {num_conveyors} slot 2 back to Conveyor 1 slot 1 (LOOP)")

    else:
        # No loop, process slot 2 movements normally (backwards to avoid conflicts)
        for conveyor_idx in range(num_conveyors, 0, -1):
            if conveyors[conveyor_idx][1] is not None:
                item = conveyors[conveyor_idx][1]
                conveyors[conveyor_idx][1] = None
                already_processed_slot2.add(conveyor_idx)

                if conveyor_idx < num_conveyors:
                    # Move to next conveyor: push current slot 1 to slot 2, item goes to slot 1
                    conveyors[conveyor_idx + 1][1] = conveyors[conveyor_idx + 1][0]
                    conveyors[conveyor_idx + 1][0] = item
                    conveyors_received_item.add(conveyor_idx + 1)
                    added_items.append(f"Item {item} moved from Conveyor {conveyor_idx} slot 2 to Conveyor {conveyor_idx + 1} slot 1")

    # Step 2: Move items from slot 1 to slot 2 within each conveyor (if slot 2 is empty)
    # BUT skip conveyors that just received items in step 1
    for conveyor_idx in range(1, num_conveyors + 1):
        if conveyor_idx not in conveyors_received_item:
            if conveyors[conveyor_idx][0] is not None and conveyors[conveyor_idx][1] is None:
                # Item in slot 1, slot 2 is empty - move to slot 2
                item = conveyors[conveyor_idx][0]
                conveyors[conveyor_idx][1] = item
                conveyors[conveyor_idx][0] = None
                added_items.append(f"Item {item} moved within Conveyor {conveyor_idx} from slot 1 to slot 2")

    # Step 3: Add new item to conveyor 1, slot 1
    # Only add if slot 1 is empty
    if item_counter < total_items and conveyors[1][0] is None:
        item_type = assumed_item_order[item_counter]
        conveyors[1][0] = item_type
        added_items.append(f"Item {item_type} ADDED to Conveyor 1 slot 1")
        item_counter += 1

    return item_counter, added_items


# Run simulation
VERBOSE = False  # Set True to print per-step conveyor state (slows execution)

if VERBOSE:
    print("Conveyor System Simulation with Item Scanning")
    print("=" * 70)

for step in range(total_items * 8):
    item_counter, added_items = simulate_conveyor_step(item_counter)
    time += conveyor_time / 2

    # Scan and remove items AFTER movement
    items_removed, orders_completed = scan_and_remove_items()

    if VERBOSE:
        print("\n")
        print(f"Time {time:.1f}:")

        for c_id in range(1, num_conveyors + 1):
            slot1 = conveyors[c_id][0] if conveyors[c_id][0] is not None else ''
            slot2 = conveyors[c_id][1] if conveyors[c_id][1] is not None else ''
            print(f"  Conveyor {c_id}: [{slot1}, {slot2}]")

        # Print items added
        for msg in added_items:
            print(f"  >> {msg}")

        # Print items removed
        if items_removed:
            for conv_id, item_type, order_id in items_removed:
                print(f"  ** Item {item_type} REMOVED from Conveyor {conv_id} for Order {order_id}")

        # Print orders completed (after removals)
        for conv_id, completed_order, new_order, new_items in orders_completed:
            # Log the completed order with time
            completed_orders_log.append({'order_num': completed_order, 'time': time, 'conveyor': conv_id})

            if new_order is not None:
                print(f"  *** ORDER {completed_order} COMPLETE on Conveyor {conv_id}! New Order {new_order} assigned: {new_items}")
            else:
                print(f"  *** ORDER {completed_order} COMPLETE on Conveyor {conv_id}! No more orders to assign.")
    else:
        # Still log completed orders for summary even when not verbose
        for conv_id, completed_order, new_order, new_items in orders_completed:
            completed_orders_log.append({'order_num': completed_order, 'time': time, 'conveyor': conv_id})

    # Check if all items processed
    if item_counter >= total_items and all(conveyors[c][0] is None and conveyors[c][1] is None for c in range(1, num_conveyors + 1)):
        break

print("\n" + "=" * 70)
print("Order Fulfillment Summary:")
print(f"Total orders processed: {next_order_idx}")
print("\nCompleted Orders:")
for entry in sorted(completed_orders_log, key=lambda x: x['order_num']):
    print(f"  Order {entry['order_num']}: Completed at Time {entry['time']:.1f} on Conveyor {entry['conveyor']}")

# Calculate statistics
if completed_orders_log:
    total_time = max(entry['time'] for entry in completed_orders_log)
    avg_time = sum(entry['time'] for entry in completed_orders_log) / len(completed_orders_log)
    print(f"\nTotal time to complete all orders: {total_time:.1f}")
    print(f"Average completion time per order: {avg_time:.1f}")


# ### Export Solution File

# In[4]:


# Export solution based on actual simulation results
# Map item types to shape names
shape_names = {
    0: 'circle',
    1: 'pentagon',
    2: 'trapezoid',
    3: 'triangle',
    4: 'star',
    5: 'moon',
    6: 'heart',
    7: 'cross'
}

# Build mapping of order_num -> conveyor_num from the simulation
order_to_conveyor = {}

for conveyor_num in range(1, num_conveyors + 1):
    if orders[conveyor_num]['order_num'] is not None:
        order_to_conveyor[orders[conveyor_num]['order_num']] = conveyor_num  # Conveyor 1-4

# Also map completed orders to their conveyors from the log
for log_entry in completed_orders_log:
    order_num = log_entry['order_num']
    conveyor_num = log_entry['conveyor']  # Conveyor 1-4
    if order_num not in order_to_conveyor:
        order_to_conveyor[order_num] = conveyor_num

print("Order to Conveyor Mapping:")
print("=" * 70)
for order_num in sorted(order_to_conveyor.keys()):
    print(f"  Order {order_num} -> Conveyor {order_to_conveyor[order_num]}")

# Always use all 8 shape types, regardless of what's in the data
all_item_types_export = sorted(list(shape_names.keys()))

# Build export dataframe with one row per order
export_data = []

for order in remaining_orders:
    order_num = order['order_num']

    # Get the conveyor this order was assigned to
    if order_num in order_to_conveyor:
        conv_num = order_to_conveyor[order_num]
    else:
        conv_num = -1  # Not assigned

    row = {'conv_num': conv_num}

    # Initialize all items to 0 (for all 8 shapes)
    for item_type in all_item_types_export:
        shape_name = shape_names[item_type]
        row[shape_name] = 0

    # Add this order's items
    for item_info in order['items']:
        item = item_info['item']
        qty = item_info['qty']
        shape_name = shape_names.get(item, f'item_{item}')
        row[shape_name] += qty

    export_data.append(row)

# Create export dataframe
export_df = pd.DataFrame(export_data)

# Reorder columns: conv_num first, then all 8 shapes in order
shape_cols = [shape_names[i] for i in all_item_types_export]
cols = ['conv_num'] + shape_cols
export_df = export_df[cols]

print("\n\nSOLUTION OUTPUT FILE (One Row Per Order):")
print("=" * 70)
print(export_df.to_string(index=False))

# Save to CSV
export_df.to_csv('Data/comparison/solution_output.csv', index=False)
print("\n\nFile saved to: Data/comparison/solution_output.csv")

print("\n\nSUMMARY:")
print("=" * 70)
print("Order Assignments to Conveyors:")
for idx, row in export_df.iterrows():
    order_num = idx + 1
    conv_num = int(row['conv_num'])
    items_list = []
    for item_type in all_item_types_export:
        shape_name = shape_names[item_type]
        qty = int(row[shape_name])
        if qty > 0:
            items_list.append(f"{qty}x {shape_name}")
    items_str = ", ".join(items_list) if items_list else "Empty"
    print(f"  Order {order_num} (Conveyor {conv_num}): {items_str}")


# In[5]:


# Write results for compare_methods.py to merge into comparison CSVs (run_id=1, fifo_all / fifo / fixed)
import os
total_orders_expected = len(remaining_orders)
num_orders = len(completed_orders_log)
all_orders_completed = (num_orders >= total_orders_expected)
flawed_run = not all_orders_completed
total_time = max(e['time'] for e in completed_orders_log) if completed_orders_log else 0
avg_time = (sum(e['time'] for e in completed_orders_log) / len(completed_orders_log)) if completed_orders_log else 0
tote_sequence = [t['tote_id'] for t in totes_queue]
item_sequence = []
for t in totes_queue:
    for info in t['items']:
        item_sequence.extend([info['item']] * info['qty'])

summary_row = pd.DataFrame([{
    'order_sequencing': 'fifo_all',
    'tote_sequencing': 'fifo',
    'item_sequencing': 'fixed',
    'total_time': total_time,
    'avg_order_time': avg_time,
    'num_orders': num_orders,
    'total_orders_expected': total_orders_expected,
    'all_orders_completed': all_orders_completed,
    'flawed_run': flawed_run,
    'tote_sequence': str(tote_sequence),
    'item_sequence': str(item_sequence),
    'item_sequence_length': len(item_sequence),
}])
summary_row.to_csv('Data/comparison/simulation_just_FIFO_summary.csv', index=False)

order_times_rows = [{'order_num': e['order_num'], 'completion_time': e['time'], 'conveyor': e['conveyor']} for e in completed_orders_log]
pd.DataFrame(order_times_rows).to_csv('Data/comparison/simulation_just_FIFO_order_times.csv', index=False)

order_conveyor_rows = [{'order_num': onum, 'conveyor': order_to_conveyor[onum]} for onum in sorted(order_to_conveyor.keys())]
pd.DataFrame(order_conveyor_rows).to_csv('Data/comparison/simulation_just_FIFO_order_conveyor.csv', index=False)

print("FIFO run results written for compare_methods: Data/comparison/simulation_just_FIFO_summary.csv, _order_times.csv, _order_conveyor.csv")

