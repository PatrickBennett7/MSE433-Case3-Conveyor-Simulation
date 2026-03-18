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
import time
import subprocess


# The name of the .venv registered as a Jupyter kernel
KERNEL_NAME = "venv_m3"

# Run configuration, modify as needed
REPLICATIONS = 25
CLEAR_OUTPUTS = True        # True = wipe prior comparison outputs (Data/comparison/*.csv) during run setup
FORCE_REGEN = True          # True = Re-run the raw-data generator
SRC_COUNT_DICT = {          # Fix the number of orders/totes/itemtypes. Set to empty dict to randomize this.
    "n_orders": str(11),
    "n_totes": str(14),
    "n_itemtypes": str(8),
}

# Global vars (do not change unless necessary)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_RAW = os.path.join(SCRIPT_DIR, 'Data', 'raw')
DATA_ORDER_SEQUENCING = os.path.join(SCRIPT_DIR, 'Data', 'order_sequencing')
DATA_COMPARISON = os.path.join(SCRIPT_DIR, 'Data', 'comparison')


def run_python_file(env, base_name: str):
    """Run either a .py script or a .ipynb notebook, preferring .py if available.

    Args:
        base_name: script/notebook base name (without extension) relative to SCRIPT_DIR.

    Returns:
        True if execution succeeded; False otherwise.
    """

    py_path = os.path.join(SCRIPT_DIR, base_name + '.py')
    nb_path = os.path.join(SCRIPT_DIR, base_name + '.ipynb')

    # Prefer a standalone .py script when available
    if os.path.isfile(py_path):
        print(f"  Running {os.path.basename(py_path)} ...")
        try:
            subprocess.run(
                [sys.executable, py_path],
                cwd=SCRIPT_DIR,
                check=True,
                capture_output=True,
                timeout=300,
                env=env,
            )
            print(f"  Done: {os.path.basename(py_path)}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"  Error running {os.path.basename(py_path)}: {e}")
            if e.stderr:
                print(e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr)
            return False
        except FileNotFoundError:
            print("  Error: python not found. Run with the Python that has pandas installed.")
            return False
        except subprocess.TimeoutExpired:
            print(f"  Error: {os.path.basename(py_path)} timed out.")
            return False

    # Otherwise try notebook
    if not os.path.isfile(nb_path):
        print(f"  Skip: {base_name}.ipynb not found.")
        return False

    print(f"  Running {os.path.basename(nb_path)} ...")
    try:
        subprocess.run(
            [sys.executable, '-m', 'jupyter', 'nbconvert', '--execute', '--to', 'notebook', '--inplace', "--ExecutePreprocessor.kernel_name=venv_m3", nb_path],
            cwd=SCRIPT_DIR,
            check=True,
            capture_output=True,
            timeout=300,
        )
        print(f"  Done: {os.path.basename(nb_path)}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Error running {os.path.basename(nb_path)}: {e}")
        if e.stderr:
            print(e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr)
        return False
    except FileNotFoundError:
        print("  Error: jupyter not found. Install with: pip install jupyter nbconvert")
        return False
    except subprocess.TimeoutExpired:
        print(f"  Error: {os.path.basename(nb_path)} timed out.")
        return False


def setup_pipeline(clear_outputs: bool = True):
    """Set up the directory layout and generate required input data.

    This is intended to run once per workspace, then multiple replications can
    be executed without re-running the data generator or order sequencing.

    If clear_outputs is True, remove existing CSV outputs in Data/comparison/
    """

    print("=" * 70)
    print("Setup: Data generator + Order sequencing")
    print("=" * 70)

    # Create folder layout
    for d in (DATA_RAW, DATA_ORDER_SEQUENCING, DATA_COMPARISON):
        os.makedirs(d, exist_ok=True)
        print(f"  Using {d}")

    if clear_outputs:
        print("\n[0/2] Clearing prior outputs from Data/comparison/")
        for fname in os.listdir(DATA_COMPARISON):
            if fname.lower().endswith('.csv'):
                path = os.path.join(DATA_COMPARISON, fname)
                try:
                    os.remove(path)
                except OSError:
                    pass
    
    return True


def run_data_generator(rep_num: int, env, force_regen: bool = False,):
    """Re-generate raw data for a given replication (seed varies per rep)."""
    
    existing_raw = all(os.path.isfile(os.path.join(DATA_RAW, fn)) for fn in (
        'order_itemtypes.csv',
        'order_quantities.csv',
        'orders_totes.csv',
    ))
    if not force_regen and existing_raw:
        print('  Skipping data generator (raw data already exists). Set FORCE_DATA_GENERATION=1 to re-run.')
    else:
            
        print("\n" + "=" * 70)
        print(f"Data generation for replication {rep_num}")
        print("=" * 70)

        env['N_ORDERS']    = SRC_COUNT_DICT["n_orders"]
        env['N_TOTES']     = SRC_COUNT_DICT["n_totes"]
        env['N_ITEMTYPES'] = SRC_COUNT_DICT["n_itemtypes"]

        print("\n[1/2] Data generator (src/MSE433_M3_data_generator.*) -> Data/raw/")
        if not run_python_file(env, 'src/MSE433_M3_data_generator'):
            print("  Data generation failed.")
            return False
    
    print("\n[2/2] Order sequencing (src/order_sequence.*) -> Data/order_sequencing/")
    if not run_python_file(env, 'src/order_sequence'):
        print("  Order sequencing failed.")
        return False
    return True


def run_replication(rep_num: int, env):
    """Run the simulation & comparison steps for a single replication."""
    print("\n" + "=" * 70)
    print(f"Replication {rep_num}: FIFO simulation -> Comparison")
    print("=" * 70)

    env['DATA_RAW_DIR'] = DATA_RAW
    env['DATA_ORDER_SEQUENCING_DIR'] = DATA_ORDER_SEQUENCING
    env['DATA_COMPARISON_DIR'] = DATA_COMPARISON

    # # 3. FIFO simulation
    # print("\n[1/2] FIFO simulation (simulation_just_FIFO.*) -> Data/comparison/")
    # t0 = time.perf_counter()
    # fifo_ok = run_python_file(env, 'simulation_just_FIFO')
    # t1 = time.perf_counter()
    # print(f"  Step time: {t1 - t0:.3f}s")
    # if not fifo_ok:
    #     print("  Warning: FIFO simulation failed; comparison will skip run_id=1.")

    # 4. Comparison
    print("\n[1/1] Comparison (src/compare_methods.py) -> Data/comparison/")
    compare_script = os.path.join(SCRIPT_DIR, 'src/compare_methods.py')
    t0 = time.perf_counter()
    try:
        r = subprocess.run(
            [sys.executable, compare_script],
            cwd=SCRIPT_DIR,
            env=env,
        )
        t1 = time.perf_counter()
        print(f"  Step time: {t1 - t0:.3f}s")
        if r.returncode != 0:
            print(f"  Error: compare_methods.py exited with code {r.returncode}")
            return False
    except FileNotFoundError:
        t1 = time.perf_counter()
        print(f"  Step time: {t1 - t0:.3f}s")
        print("  Error: 'python' not found in PATH, or pandas missing in that Python.")
        print("  Run from conda base and use:  python run_all.py   (no full path to python)")
        return False

    print("\n" + "=" * 70)
    print("Replication complete. Outputs in Data/comparison/")
    print("  comparison_summary.csv, comparison_order_times.csv, comparison_order_conveyor.csv")
    print("=" * 70)
    return True


if __name__ == '__main__':
    env = os.environ.copy()
    env['KERNEL'] = KERNEL_NAME

    if not setup_pipeline(clear_outputs=CLEAR_OUTPUTS):
        sys.exit(1)
    
    for rep in range(1, REPLICATIONS + 1):
        env['REPLICATION_NUM'] = str(rep)
        if not run_data_generator(rep, env=env, force_regen=FORCE_REGEN):
            sys.exit(1)

        if not run_replication(rep, env):
            sys.exit(1)
    sys.exit(0)
