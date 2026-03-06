"""
Run the full pipeline in order:
  1. Data generator (MSE433_M3_data_generator.ipynb)  -> writes Data/raw/
  2. Order sequencing (order_sequence.ipynb)            -> reads Data/raw/, writes Data/order_sequencing/
  3. FIFO simulation (simulation_just_FIFO.ipynb)      -> reads Data/raw/, writes Data/comparison/
  4. Comparison (compare_methods.py)                   -> reads Data/raw/, Data/order_sequencing/, Data/comparison/
                                                         -> writes Data/comparison/

Folder layout:
  Data/raw/                  -- order_itemtypes.csv, order_quantities.csv, orders_totes.csv
  Data/order_sequencing/     -- algorithm1_*.csv, algorithm1b_*.csv, algorithm2_*.csv, algorithm3_*.csv, algorithm4_*.csv
  Data/comparison/           -- simulation_just_FIFO_*.csv, solution_output.csv, comparison_summary.csv, comparison_order_times.csv, comparison_order_conveyor.csv

Run with the Python that has pandas and jupyter (e.g. from conda base):
  python run_all.py
Avoid using a full path to a different Python (e.g. /opt/homebrew/bin/python3.11) or the comparison step may fail with "No module named 'pandas'".
"""

import os
import sys
import subprocess


KERNEL_NAME = "venv_m3"
REPLICATIONS = 1

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_RAW = os.path.join(SCRIPT_DIR, 'Data', 'raw')
DATA_ORDER_SEQUENCING = os.path.join(SCRIPT_DIR, 'Data', 'order_sequencing')
DATA_COMPARISON = os.path.join(SCRIPT_DIR, 'Data', 'comparison')


def run_notebook(nb_name: str):
    """
    Execute a Jupyter notebook with nbconvert. Returns True on success.

    Args:
        nb_name: notebook filepath
    """
    nb_path = os.path.join(SCRIPT_DIR, nb_name)
    if not os.path.isfile(nb_path):
        print(f"  Skip: {nb_name} not found.")
        return False
    print(f"  Running {nb_name} ...")
    try:
        subprocess.run(
            [sys.executable, '-m', 'jupyter', 'nbconvert', '--execute', '--to', 'notebook', '--inplace', "--ExecutePreprocessor.kernel_name=venv_m3", nb_path],
            cwd=SCRIPT_DIR,
            check=True,
            capture_output=True,
            timeout=300,
        )
        print(f"  Done: {nb_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Error running {nb_name}: {e}")
        if e.stderr:
            print(e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr)
        return False
    except FileNotFoundError:
        print("  Error: jupyter not found. Install with: pip install jupyter nbconvert")
        return False
    except subprocess.TimeoutExpired:
        print(f"  Error: {nb_name} timed out.")
        return False


def run_one_replication(rep_num: int, env):
    """
    Args:
        rep_num: the replication number
    """
    print("=" * 70)
    print("Pipeline: Data generator -> Order sequencing -> FIFO simulation -> Comparison")
    print("=" * 70)

    # Update replication number
    env['REPLICATION_NUM'] = str(rep)

    # Create folder layout
    for d in (DATA_RAW, DATA_ORDER_SEQUENCING, DATA_COMPARISON):
        os.makedirs(d, exist_ok=True)
        print(f"  Using {d}")

    # 1. Data generator
    print("\n[1/4] Data generator (MSE433_M3_data_generator.ipynb) -> Data/raw/")
    if not run_notebook('MSE433_M3_data_generator.ipynb'):
        print("  Pipeline stopped: data generator failed.")
        return 1

    # 2. Order sequencing
    print("\n[2/4] Order sequencing (order_sequence.ipynb) -> Data/order_sequencing/")
    if not run_notebook('order_sequence.ipynb'):
        print("  Pipeline stopped: order sequencing failed.")
        return 1

    # 3. FIFO simulation
    print("\n[3/4] FIFO simulation (simulation_just_FIFO.ipynb) -> Data/comparison/")
    if not run_notebook('simulation_just_FIFO.ipynb'):
        print("  Warning: FIFO simulation failed; comparison will skip run_id=1.")

    # 4. Comparison (run in subprocess with 'python' from PATH so conda/env with pandas is used)
    print("\n[4/4] Comparison (compare_methods.py) -> Data/comparison/")
    env['DATA_RAW_DIR'] = DATA_RAW
    env['DATA_ORDER_SEQUENCING_DIR'] = DATA_ORDER_SEQUENCING
    env['DATA_COMPARISON_DIR'] = DATA_COMPARISON
    compare_script = os.path.join(SCRIPT_DIR, 'compare_methods.py')
    try:
        r = subprocess.run(
            [sys.executable, compare_script],
            cwd=SCRIPT_DIR,
            env=env,
        )
        if r.returncode != 0:
            print(f"  Error: compare_methods.py exited with code {r.returncode}")
            return 1
    except FileNotFoundError:
        print("  Error: 'python' not found in PATH, or pandas missing in that Python.")
        print("  Run from conda base and use:  python run_all.py   (no full path to python)")
        return 1

    print("\n" + "=" * 70)
    print("Pipeline complete. Outputs in Data/comparison/")
    print("  comparison_summary.csv, comparison_order_times.csv, comparison_order_conveyor.csv")
    print("=" * 70)
    return 0


if __name__ == '__main__':    
    env = os.environ.copy()
    env['KERNEL'] = KERNEL_NAME

    for rep in range(1, REPLICATIONS+1):
        run_one_replication(rep, env)
    sys.exit()
