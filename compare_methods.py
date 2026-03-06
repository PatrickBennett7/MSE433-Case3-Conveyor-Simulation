"""
Compare all combinations of:
  - Order sequencing (algorithm 1, 2, 3, 4 solution files)
  - Tote sequencing (fifo, smart_active_need, smart_active_need_weighted)
  - Within-tote item order (fixed, critical_first)

Outputs: comparison_summary.csv, comparison_order_times.csv, comparison_order_conveyor.csv

Run 1 is the FIFO baseline: compare_methods executes simulation_just_FIFO.ipynb once
and merges its outputs from the comparison dir into the comparison CSVs. All other
runs (2+) use the algorithm solution files and run_simulation().

Folder layout (see run_all.py):
  Data/raw/                  -- data generator outputs (order_itemtypes, order_quantities, orders_totes)
  Data/order_sequencing/      -- order_sequence notebook outputs (algorithm*_assignment.csv)
  Data/comparison/            -- FIFO run results + comparison_summary, comparison_order_times, comparison_order_conveyor

Requirement: Algorithm solution CSVs must be generated from the same Data (run
order_sequence.ipynb first) so solution rows match orders by shape.

Runs that do not complete all orders (items stuck on belt, no space to load more)
are reported as flawed_run=True: that indicates a flaw in that algorithm combination.

Why FIFO tote sequencing often causes flawed runs:
  FIFO chooses the next tote by smallest tote_id (0, 1, 2, ...), ignoring which
  orders are currently active on each conveyor. So we load totes in an order that
  may only match one conveyor's current order; items for other conveyors' orders
  (often in higher-id totes) are loaded later. The belt can fill with "wrong"
  items that just circulate, and we can only add a new item when conveyor 1's
  slot is free—so loading is effectively throttled by belt flow. Within the
  fixed step cap, many orders never see their items in time, so the run is
  flawed. Smart tote sequencing (smart_active_need*) prioritizes totes that
  contain items needed by current orders, so items tend to match demand and
  more orders complete.
"""

import pandas as pd
from collections import deque, Counter
import copy
import os
import sys
import subprocess

# ---------------------------------------------------------------------------
# Data loading (same as simulate_conveyor.ipynb)
# ---------------------------------------------------------------------------
def load_data(data_dir='Data'):
    items_raw = pd.read_csv(os.path.join(data_dir, 'order_itemtypes.csv'), header=None)
    qty_raw = pd.read_csv(os.path.join(data_dir, 'order_quantities.csv'), header=None)
    tote_raw = pd.read_csv(os.path.join(data_dir, 'orders_totes.csv'), header=None)
    items_df = pd.concat([pd.Series(range(len(items_raw)), name='Index'), items_raw], axis=1)
    qty_df = pd.concat([pd.Series(range(len(qty_raw)), name='Index'), qty_raw], axis=1)
    tote_df = pd.concat([pd.Series(range(len(tote_raw)), name='Index'), tote_raw], axis=1)

    orders_queue = []
    totes_dict = {}
    for order_num in range(len(items_df)):
        items_row = items_df.iloc[order_num]
        qty_row = qty_df.iloc[order_num]
        tote_row = tote_df.iloc[order_num]
        order_items = []
        for col_idx in range(1, len(items_row)):
            item = items_row.iloc[col_idx]
            qty = qty_row.iloc[col_idx]
            tote = tote_row.iloc[col_idx]
            if pd.isna(item) or str(item).strip() == '':
                continue
            item = int(float(item))
            qty = int(float(qty)) if pd.notna(qty) else 1
            tote = int(float(tote)) if pd.notna(tote) else 0
            order_items.append({'item': item, 'qty': qty, 'tote': tote})
            if tote not in totes_dict:
                totes_dict[tote] = []
            totes_dict[tote].append({'item': item, 'qty': qty})
        if order_items:
            orders_queue.append({'order_num': order_num + 1, 'items': order_items})

    totes_queue = [{'tote_id': tid, 'items': totes_dict[tid]} for tid in sorted(totes_dict.keys())]
    return orders_queue, totes_queue


# Solution CSV uses these columns for shape quantities (item types 0..7)
SHAPE_COLS = ['circle', 'pentagon', 'trapezoid', 'triangle', 'star', 'moon', 'heart', 'cross']


def _order_to_shape_tuple(order):
    """Build (qty per item type 0..7) for one order. Sum by type to match solution CSV (same as order_sequence.ipynb order_to_shape_row)."""
    row = [0] * 8
    for it in order['items']:
        item_type = int(it['item'])
        qty = int(it.get('qty', 1))
        if 0 <= item_type < 8:
            row[item_type] += qty
    return tuple(row)


# ---------------------------------------------------------------------------
# Run simulation_just_FIFO.ipynb once and read its result CSVs for run_id=1
# ---------------------------------------------------------------------------
def run_fifo_notebook_and_load_results(script_dir, data_dir):
    """Execute simulation_just_FIFO.ipynb and return (summary_row dict, order_times list, order_conveyor list) or (None, None, None) on failure."""
    nb_path = os.path.join(script_dir, 'simulation_just_FIFO.ipynb')
    if not os.path.isfile(nb_path):
        return None, None, None
    try:
        subprocess.run(
            [sys.executable, '-m', 'jupyter', 'nbconvert', '--execute', '--to', 'notebook', '--inplace', "--ExecutePreprocessor.kernel_name=venv_m3", nb_path],
            cwd=script_dir,
            check=True,
            capture_output=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  Warning: could not run simulation_just_FIFO.ipynb: {e}")
        return None, None, None
    
    summary_path = os.path.join(data_dir, 'simulation_just_FIFO_summary.csv')
    times_path = os.path.join(data_dir, 'simulation_just_FIFO_order_times.csv')
    conveyor_path = os.path.join(data_dir, 'simulation_just_FIFO_order_conveyor.csv')
    if not os.path.isfile(summary_path):
        print(f"  Warning: {summary_path} not found after running notebook.")
        return None, None, None
    try:
        summary_df = pd.read_csv(summary_path)
        summary_row = summary_df.iloc[0].to_dict()
        order_times = pd.read_csv(times_path).to_dict('records') if os.path.isfile(times_path) else []
        order_conveyor = pd.read_csv(conveyor_path).to_dict('records') if os.path.isfile(conveyor_path) else []
        return summary_row, order_times, order_conveyor
    except Exception as e:
        print(f"  Warning: could not read FIFO result CSVs: {e}")
        return None, None, None


# ---------------------------------------------------------------------------
# Run one simulation with given solution and sequencing options
# ---------------------------------------------------------------------------
def run_simulation(orders_queue, totes_queue, solution_df, tote_algo, within_tote_order, verbose=False):
    num_conveyors = 4
    conveyor_time = 7.5
    CONVEYOR_WEIGHTS = {1: 4, 2: 3, 3: 2, 4: 1}

    # Match solution rows to orders by shape vector (solution CSV is ordered by conveyor then sequence, not by order number)
    conveyor_order_queues = {i: deque() for i in range(1, num_conveyors + 1)}
    unmatched_orders = list(orders_queue)  # copy; we'll remove as we match
    for idx, row in solution_df.iterrows():
        row_shape = tuple(int(row[col]) for col in SHAPE_COLS)
        conv_num = int(row['conv_num'])
        # Find an order with this exact shape vector (one-to-one match)
        match_idx = None
        for i, order in enumerate(unmatched_orders):
            if _order_to_shape_tuple(order) == row_shape:
                match_idx = i
                break
        if match_idx is None:
            continue  # no matching order (data mismatch); skip this row
        order = unmatched_orders.pop(match_idx)
        order_num = order['order_num']
        items_list = []
        remaining_list = []
        for item_info in order['items']:
            item = item_info['item']
            qty = int(item_info['qty'])
            tote_id = int(item_info.get('tote', 0)) if item_info.get('tote') is not None else 0
            for _ in range(qty):
                items_list.append(item)
                remaining_list.append((item, tote_id))
        conveyor_order_queues[conv_num].append({
            'order_num': order_num, 'items': items_list.copy(),
            'remaining': remaining_list.copy(), 'fulfilled': []
        })

    total_matched = sum(len(conveyor_order_queues[c]) for c in range(1, num_conveyors + 1))
    if total_matched < len(orders_queue) and verbose:
        import warnings
        warnings.warn(f"Solution matched only {total_matched}/{len(orders_queue)} orders; regenerate algorithm CSVs from order_sequence.ipynb with current Data.")

    # order_num -> conv_num for reporting (derived from queues we just built)
    order_assignment = {}
    for c in range(1, num_conveyors + 1):
        for order_dict in list(conveyor_order_queues[c]):
            order_assignment[order_dict['order_num']] = c

    conveyors = {i: [None, None] for i in range(1, num_conveyors + 1)}
    orders = {i: {'order_num': None, 'items': [], 'remaining': [], 'fulfilled': []} for i in range(1, num_conveyors + 1)}

    def assign_next_order_to_conveyor(conveyor_num):
        if conveyor_order_queues[conveyor_num]:
            next_order = conveyor_order_queues[conveyor_num].popleft()
            orders[conveyor_num] = next_order
            return True
        orders[conveyor_num] = {'order_num': None, 'items': [], 'remaining': [], 'fulfilled': []}
        return False

    for c in range(1, num_conveyors + 1):
        assign_next_order_to_conveyor(c)

    # Tote/item helpers
    def _active_need_counts():
        need = Counter()
        for c in range(1, num_conveyors + 1):
            if orders[c]['order_num'] is None:
                continue
            need.update(orders[c]['remaining'])
        return need

    def _tote_score_smart_active_need(tote, need_counts):
        score = 0
        tid = tote['tote_id']
        for item_info in tote['items']:
            item, qty = item_info['item'], int(item_info['qty'])
            score += min(qty, need_counts.get((item, tid), 0))
        return score

    def _active_need_per_conveyor():
        return {c: Counter(orders[c]['remaining']) if orders[c]['order_num'] else Counter()
                for c in range(1, num_conveyors + 1)}

    def _tote_score_weighted(tote, need_per_conveyor, weights):
        score = 0
        tid = tote['tote_id']
        for item_info in tote['items']:
            item, qty = item_info['item'], int(item_info['qty'])
            for c in range(1, num_conveyors + 1):
                need_c = need_per_conveyor.get(c, Counter()).get((item, tid), 0)
                score += weights.get(c, 1) * min(qty, need_c)
        return score

    def select_next_tote(remaining_totes, algorithm):
        if not remaining_totes:
            return None
        if algorithm == 'fifo':
            return min(remaining_totes, key=lambda t: t['tote_id'])
        if algorithm == 'smart_active_need':
            need_counts = _active_need_counts()
            best = max(remaining_totes, key=lambda t: _tote_score_smart_active_need(t, need_counts))
            if _tote_score_smart_active_need(best, need_counts) <= 0:
                return min(remaining_totes, key=lambda t: t['tote_id'])
            return best
        if algorithm == 'smart_active_need_weighted':
            need_per_conveyor = _active_need_per_conveyor()
            best = max(remaining_totes, key=lambda t: _tote_score_weighted(t, need_per_conveyor, CONVEYOR_WEIGHTS))
            if _tote_score_weighted(best, need_per_conveyor, CONVEYOR_WEIGHTS) <= 0:
                return min(remaining_totes, key=lambda t: t['tote_id'])
            return best
        raise ValueError(f"Unknown tote algo: {algorithm}")

    def _expand_tote_to_item_pairs(tote):
        tid = tote['tote_id']
        pairs = []
        for item_info in tote['items']:
            item, qty = item_info['item'], int(item_info['qty'])
            pairs.extend([(item, tid)] * qty)
        return pairs

    def _expand_tote_critical_first(tote, orders_ref):
        pairs = _expand_tote_to_item_pairs(tote)
        def priority(unit):
            item, t = unit
            best_conv, best_remaining = None, 999
            for c in range(1, num_conveyors + 1):
                if orders_ref[c]['order_num'] is None:
                    continue
                rem = orders_ref[c]['remaining']
                if (item, t) not in rem:
                    continue
                if best_conv is None or c < best_conv:
                    best_conv, best_remaining = c, len(rem)
            if best_conv is None:
                return 9999
            is_last = (best_remaining == 1)
            return (0 if is_last else 1000) + best_conv * 10 + best_remaining
        pairs.sort(key=priority)
        return pairs

    def scan_and_remove():
        items_removed = []
        orders_completed = []
        for conveyor_idx in range(1, num_conveyors + 1):
            slot_content = conveyors[conveyor_idx][1]
            if slot_content is None or orders[conveyor_idx]['order_num'] is None:
                continue
            item_type, tote_id = slot_content
            pair = (item_type, tote_id)
            if pair not in orders[conveyor_idx]['remaining']:
                continue
            current_order_num = orders[conveyor_idx]['order_num']
            conveyors[conveyor_idx][1] = None
            orders[conveyor_idx]['remaining'].remove(pair)
            orders[conveyor_idx]['fulfilled'].append(pair)
            items_removed.append((conveyor_idx, item_type, current_order_num))
            if len(orders[conveyor_idx]['remaining']) == 0:
                completed_order_num = current_order_num
                assign_next_order_to_conveyor(conveyor_idx)
                orders_completed.append((conveyor_idx, completed_order_num))
        return items_removed, orders_completed

    def simulate_step(item_counter, total_items):
        conveyors_received_item = set()
        # Step 1: movements
        if conveyors[num_conveyors][1] is not None:
            loop_item = conveyors[num_conveyors][1]
            conveyors[num_conveyors][1] = None
            for cascade_idx in range(num_conveyors - 1, 0, -1):
                if conveyors[cascade_idx][1] is not None:
                    cascade_item = conveyors[cascade_idx][1]
                    conveyors[cascade_idx][1] = None
                    conveyors[cascade_idx + 1][1], conveyors[cascade_idx + 1][0] = conveyors[cascade_idx + 1][0], cascade_item
                    conveyors_received_item.add(cascade_idx + 1)
            conveyors[1][1], conveyors[1][0] = conveyors[1][0], loop_item
            conveyors_received_item.add(1)
        else:
            for conveyor_idx in range(num_conveyors, 0, -1):
                if conveyors[conveyor_idx][1] is not None:
                    item = conveyors[conveyor_idx][1]
                    conveyors[conveyor_idx][1] = None
                    if conveyor_idx < num_conveyors:
                        conveyors[conveyor_idx + 1][1], conveyors[conveyor_idx + 1][0] = conveyors[conveyor_idx + 1][0], item
                        conveyors_received_item.add(conveyor_idx + 1)
        for conveyor_idx in range(1, num_conveyors + 1):
            if conveyor_idx not in conveyors_received_item and conveyors[conveyor_idx][0] is not None and conveyors[conveyor_idx][1] is None:
                conveyors[conveyor_idx][1], conveyors[conveyor_idx][0] = conveyors[conveyor_idx][0], None
        # Step 2: add new item
        if item_counter < total_items and conveyors[1][0] is None:
            if not current_tote_items and remaining_totes:
                selected_tote = select_next_tote(remaining_totes, tote_algo)
                for i, t in enumerate(remaining_totes):
                    if t['tote_id'] == selected_tote['tote_id']:
                        remaining_totes.pop(i)
                        break
                loaded_totes.append(selected_tote['tote_id'])
                if within_tote_order == 'critical_first':
                    current_tote_items.extend(_expand_tote_critical_first(selected_tote, orders))
                else:
                    current_tote_items.extend(_expand_tote_to_item_pairs(selected_tote))
            if current_tote_items:
                item_type, tote_id = current_tote_items.popleft()
                conveyors[1][0] = (item_type, tote_id)
                loaded_item_sequence.append(item_type)
                item_counter += 1
        return item_counter

    remaining_totes = [copy.deepcopy(t) for t in totes_queue]
    current_tote_items = deque()
    loaded_totes = []
    loaded_item_sequence = []
    total_items = sum(int(info['qty']) for tote in remaining_totes for info in tote['items'])
    time = 0
    completed_orders_log = []

    # Fixed step cap: if a combination can't complete all orders before this, it's a flaw in that algorithm combo (items stuck on belt, no space to load more, etc.)
    max_steps = total_items * 8
    for _ in range(max_steps):
        item_counter = simulate_step(len(loaded_item_sequence), total_items)
        time += conveyor_time / 2
        items_removed, orders_completed = scan_and_remove()
        for conv_id, completed_order_num in orders_completed:
            completed_orders_log.append({'order_num': completed_order_num, 'time': time, 'conveyor': conv_id})
        all_queues_empty = all(len(conveyor_order_queues[c]) == 0 for c in range(1, num_conveyors + 1))
        all_done = all(orders[c]['order_num'] is None or len(orders[c]['remaining']) == 0 for c in range(1, num_conveyors + 1))
        belt_empty = all(conveyors[c][0] is None and conveyors[c][1] is None for c in range(1, num_conveyors + 1))
        total_orders_in_run = len(order_assignment)
        if (len(loaded_item_sequence) >= total_items and belt_empty and all_queues_empty and all_done
                and len(completed_orders_log) >= total_orders_in_run):
            break

    total_time = max((e['time'] for e in completed_orders_log), default=0)
    avg_time = total_time
    if completed_orders_log:
        avg_time = sum(e['time'] for e in completed_orders_log) / len(completed_orders_log)

    return {
        'order_assignment': order_assignment,
        'total_time': total_time,
        'avg_order_time': avg_time,
        'completed_orders_log': completed_orders_log,
        'loaded_totes': loaded_totes,
        'loaded_item_sequence': loaded_item_sequence,
    }


# ---------------------------------------------------------------------------
# Main: run all combinations and write outputs
# ---------------------------------------------------------------------------
def main(raw_data_dir='Data/raw', order_sequencing_dir='Data/order_sequencing', comparison_dir='Data/comparison', rep_num: int=1):
    os.makedirs(comparison_dir, exist_ok=True)
    orders_queue, totes_queue = load_data(raw_data_dir)

    order_configs = [
        ('algorithm1_load_balance', os.path.join(order_sequencing_dir, 'algorithm1_load_balance_assignment.csv')),
        ('algorithm1b_stratified_balance', os.path.join(order_sequencing_dir, 'algorithm1b_stratified_balance_assignment.csv')),
        ('algorithm2_tote_overlap', os.path.join(order_sequencing_dir, 'algorithm2_tote_overlap_assignment.csv')),
        ('algorithm3_itemtype_overlap', os.path.join(order_sequencing_dir, 'algorithm3_itemtype_overlap_assignment.csv')),
        ('algorithm4_combined_overlap', os.path.join(order_sequencing_dir, 'algorithm4_combined_overlap_assignment.csv')),
    ]
    tote_algos = ['fifo', 'smart_active_need', 'smart_active_need_weighted']
    item_algos = ['fixed', 'critical_first']

    summary_rows = []
    order_times_rows = []
    order_conveyor_rows = []

    run_id = 0
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Run simulation_just_FIFO.ipynb once and merge its results as run_id=1
    print("Run 1: simulation_just_FIFO.ipynb (FIFO orders, totes, items)")
    summary_row, fifo_order_times, fifo_order_conveyor = run_fifo_notebook_and_load_results(script_dir, comparison_dir)
    if summary_row is not None:
        run_id = 1
        run_label = "run_1_fifo_all_fifo_fixed"
        summary_rows.append({
            'run_id': run_id,
            'run_label': run_label,
            'order_sequencing': summary_row.get('order_sequencing', 'fifo_all'),
            'tote_sequencing': summary_row.get('tote_sequencing', 'fifo'),
            'item_sequencing': summary_row.get('item_sequencing', 'fixed'),
            'total_time': summary_row.get('total_time', 0),
            'avg_order_time': summary_row.get('avg_order_time', 0),
            'num_orders': int(summary_row.get('num_orders', 0)),
            'total_orders_expected': int(summary_row.get('total_orders_expected', 0)),
            'all_orders_completed': bool(summary_row.get('all_orders_completed', False)),
            'flawed_run': bool(summary_row.get('flawed_run', True)),
            'tote_sequence': str(summary_row.get('tote_sequence', '[]')),
            'item_sequence': str(summary_row.get('item_sequence', '[]')),
            'item_sequence_length': int(summary_row.get('item_sequence_length', 0)),
            'replication': rep_num,
        })
        for e in fifo_order_times:
            order_times_rows.append({
                'run_id': run_id,
                'run_label': run_label,
                'order_num': int(e.get('order_num', 0)),
                'completion_time': float(e.get('completion_time', e.get('time', 0))),
                'conveyor': int(e.get('conveyor', 0)),
                'replication': rep_num,
            })
        for row in fifo_order_conveyor:
            order_conveyor_rows.append({
                'run_id': run_id,
                'run_label': run_label,
                'order_num': int(row.get('order_num', 0)),
                'conveyor': int(row.get('conveyor', 0)),
                'replication': rep_num,
            })
    else:
        print("  Skipped (notebook not run or result files missing).")

    for order_name, solution_path in order_configs:
        if not os.path.isfile(solution_path):
            print(f"Skip (file not found): {solution_path}")
            continue
        solution_df = pd.read_csv(solution_path)
        for tote_algo in tote_algos:
            for item_algo in item_algos:
                run_id += 1
                print(f"Run {run_id}: order={order_name}, tote={tote_algo}, item={item_algo}")
                try:
                    result = run_simulation(orders_queue, totes_queue, solution_df, tote_algo, item_algo, verbose=False)
                except Exception as e:
                    print(f"  Error: {e}")
                    continue
                run_label = f"run_{run_id}_{order_name}_{tote_algo}_{item_algo}"
                total_expected = len(result['order_assignment'])
                num_completed = len(result['completed_orders_log'])
                all_orders_completed = (num_completed >= total_expected)
                summary_rows.append({
                    'run_id': run_id,
                    'run_label': run_label,
                    'order_sequencing': order_name,
                    'tote_sequencing': tote_algo,
                    'item_sequencing': item_algo,
                    'total_time': result['total_time'],
                    'avg_order_time': result['avg_order_time'],
                    'num_orders': num_completed,
                    'total_orders_expected': total_expected,
                    'all_orders_completed': all_orders_completed,
                    'flawed_run': not all_orders_completed,
                    'tote_sequence': str(result['loaded_totes']),
                    'item_sequence': str(result['loaded_item_sequence']),
                    'item_sequence_length': len(result['loaded_item_sequence']),
                    'replication': rep_num,
                })
                for e in result['completed_orders_log']:
                    order_times_rows.append({
                        'run_id': run_id,
                        'run_label': run_label,
                        'order_num': e['order_num'],
                        'completion_time': e['time'],
                        'conveyor': e['conveyor'],
                        'replication': rep_num,
                    })
                for order_num, conv in result['order_assignment'].items():
                    order_conveyor_rows.append({
                        'run_id': run_id,
                        'run_label': run_label,
                        'order_num': order_num,
                        'conveyor': conv,
                        'replication': rep_num,
                    })

    summary_df = pd.DataFrame(summary_rows)
    order_times_df = pd.DataFrame(order_times_rows)
    order_conveyor_df = pd.DataFrame(order_conveyor_rows)

    summary_path = os.path.join(comparison_dir, 'comparison_summary.csv')
    times_path = os.path.join(comparison_dir, 'comparison_order_times.csv')
    conveyor_path = os.path.join(comparison_dir, 'comparison_order_conveyor.csv')

    summary_df.to_csv(summary_path, index=False)
    order_times_df.to_csv(times_path, index=False)
    order_conveyor_df.to_csv(conveyor_path, index=False)

    print("\n" + "=" * 70)
    print("Comparison complete.")
    print(f"Summary: {summary_path}")
    print(f"Order times (per order per run): {times_path}")
    print(f"Order->conveyor per run: {conveyor_path}")
    flawed = summary_df[summary_df['flawed_run']]
    if len(flawed) > 0:
        print("\n*** FLAWED RUNS (did not complete all orders; items stuck on belt / no space to load): ***")
        print(flawed[['run_id', 'order_sequencing', 'tote_sequencing', 'item_sequencing', 'num_orders', 'total_orders_expected']].to_string(index=False))
        if (flawed['tote_sequencing'] == 'fifo').any():
            print("\n  Why FIFO tote runs often fail: FIFO loads totes by ID (0,1,2,...) without regard to which"
                  " orders are active, so the belt fills with items that may not match other conveyors' orders;"
                  " those items circulate and block loading. Smart tote sequencing prioritizes totes needed by"
                  " current orders, so more orders complete.")
    print("\nSummary (total_time, avg_order_time by run):")
    print(summary_df[['run_id', 'order_sequencing', 'tote_sequencing', 'item_sequencing', 'total_time', 'avg_order_time', 'num_orders', 'all_orders_completed']].to_string(index=False))
    return summary_df, order_times_df, order_conveyor_df


if __name__ == '__main__':
    rep_num = int(os.environ.get('REPLICATION', 1))

    raw_dir = os.environ.get('DATA_RAW_DIR', 'Data/raw')
    order_dir = os.environ.get('DATA_ORDER_SEQUENCING_DIR', 'Data/order_sequencing')
    comp_dir = os.environ.get('DATA_COMPARISON_DIR', 'Data/comparison')
    main(
        raw_data_dir=raw_dir,
        order_sequencing_dir=order_dir,
        comparison_dir=comp_dir,
        rep_num=rep_num,
    )
