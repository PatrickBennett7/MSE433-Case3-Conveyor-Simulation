#!/usr/bin/env python
# coding: utf-8

# ### Module 3: FIFO Simulation
# Runs the FIFO baseline (fifo order sequencing, fifo tote sequencing, fixed item order)
# using the SAME run_simulation() engine as compare_methods.py so results are comparable.

import os
import sys
import pandas as pd

# ---------------------------------------------------------------------------
# Import the shared simulation engine from compare_methods.py
# ---------------------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
from compare_methods import load_data, run_simulation, SHAPE_COLS

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
raw_dir        = os.environ.get('DATA_RAW_DIR',        os.path.join(script_dir, 'Data', 'raw'))
comparison_dir = os.environ.get('DATA_COMPARISON_DIR', os.path.join(script_dir, 'Data', 'comparison'))
os.makedirs(comparison_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
orders_queue, totes_queue = load_data(raw_dir)
total_orders_expected = len(orders_queue)

print(f"Loaded {total_orders_expected} orders, {len(totes_queue)} totes")

# ---------------------------------------------------------------------------
# Build a FIFO solution_df:
# Assign orders to conveyors round-robin (conveyor 1, 2, 3, 4, 1, 2, ...)
# This matches what the original FIFO notebook did implicitly.
# ---------------------------------------------------------------------------
num_conveyors = 4
rows = []
for i, order in enumerate(orders_queue):
    conv_num = (i % num_conveyors) + 1
    row = {'conv_num': conv_num}
    # Build shape vector (qty per item type)
    shape_qty = {col: 0 for col in SHAPE_COLS}
    shape_map = {j: col for j, col in enumerate(SHAPE_COLS)}
    for item_info in order['items']:
        item_type = int(item_info['item'])
        qty       = int(item_info.get('qty', 1))
        if item_type in shape_map:
            shape_qty[shape_map[item_type]] += qty
    row.update(shape_qty)
    rows.append(row)

solution_df = pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# Run simulation — same engine as compare_methods.py
# ---------------------------------------------------------------------------
result = run_simulation(
    orders_queue   = orders_queue,
    totes_queue    = totes_queue,
    solution_df    = solution_df,
    tote_algo      = 'fifo',
    within_tote_order = 'fixed',
    verbose        = False,
)

completed_orders_log = result['completed_orders_log']
order_assignment     = result['order_assignment']
num_orders           = len(completed_orders_log)
all_orders_completed = num_orders >= total_orders_expected
flawed_run           = not all_orders_completed
total_time           = result['total_time']
avg_time             = result['avg_order_time']
loaded_totes         = result['loaded_totes']
loaded_item_sequence = result['loaded_item_sequence']

print(f"Completed {num_orders}/{total_orders_expected} orders")
print(f"Total time: {total_time:.1f},  Avg order time: {avg_time:.4f}")
print(f"Flawed run: {flawed_run}")

# ---------------------------------------------------------------------------
# Write outputs for compare_methods.py to merge as run_id=1
# ---------------------------------------------------------------------------
summary_row = pd.DataFrame([{
    'order_sequencing'    : 'fifo_all',
    'tote_sequencing'     : 'fifo',
    'item_sequencing'     : 'fixed',
    'total_time'          : total_time,
    'avg_order_time'      : avg_time,
    'num_orders'          : num_orders,
    'total_orders_expected': total_orders_expected,
    'all_orders_completed': all_orders_completed,
    'flawed_run'          : flawed_run,
    'tote_sequence'       : str(loaded_totes),
    'item_sequence'       : str(loaded_item_sequence),
    'item_sequence_length': len(loaded_item_sequence),
}])
summary_row.to_csv(os.path.join(comparison_dir, 'simulation_just_FIFO_summary.csv'), index=False)

order_times_rows = [
    {'order_num': e['order_num'], 'completion_time': e['time'], 'conveyor': e['conveyor']}
    for e in completed_orders_log
]
pd.DataFrame(order_times_rows).to_csv(
    os.path.join(comparison_dir, 'simulation_just_FIFO_order_times.csv'), index=False
)

order_conveyor_rows = [
    {'order_num': onum, 'conveyor': conv}
    for onum, conv in sorted(order_assignment.items())
]
pd.DataFrame(order_conveyor_rows).to_csv(
    os.path.join(comparison_dir, 'simulation_just_FIFO_order_conveyor.csv'), index=False
)

print("FIFO results written:")
print(f"  {comparison_dir}/simulation_just_FIFO_summary.csv")
print(f"  {comparison_dir}/simulation_just_FIFO_order_times.csv")
print(f"  {comparison_dir}/simulation_just_FIFO_order_conveyor.csv")