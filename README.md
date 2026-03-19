# M3: Warehousing

This project simulates a four-belt conveyor sortation system for e-commerce order fulfillment. It compares heuristics for three decisions: **order sequencing** (which orders go to which belt), **tote sequencing** (which tote to load next), and **item sequencing** (order of items released from each tote). The pipeline generates random order/tote data, runs several order-assignment algorithms, then simulates all combinations of order × tote × item heuristics and writes comparison metrics. Results support statistical analysis and physical conveyor testing.

## Project structure

| Path                       | Description                                                                                                                                                          |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Root**                   | `run_all.py` (main pipeline), `dashboard.py` (Streamlit analytics), `statistical_analysis.ipynb` (comparison analysis)                                               |
| **src/**                   | `MSE433_M3_data_generator.py`, `order_sequence.py`, `simulation_just_FIFO.py`, `compare_methods.py`. See `src/README_order_sequence.md` for order-algorithm details. |
| **Data/raw/**              | Generated CSVs: `order_itemtypes.csv`, `order_quantities.csv`, `orders_totes.csv`                                                                                    |
| **Data/order_sequencing/** | Generated order-assignment CSVs (one per algorithm)                                                                                                                  |
| **Data/comparison/**       | Outputs: `comparison_summary.csv`, `comparison_order_times.csv`, `comparison_order_conveyor.csv`                                                                     |

**Pipeline flow:** Data generator → Order sequencing → Comparison. Run `run_all.py` from the repo root; it uses the `src/` scripts and the `Data/` paths above.

## Setup

### Requirements

- python 3.11+
- Jupyter extension in VSCode (if needed)

### Dev Setup (One-Time)

1. In root, create venv

   ```bash
   python -m venv .venv
   ```

2. Activate .venv

   ```bash
   # For Mac:
   source .venv/bin/activate

   # For Windows:
   .venv\Scripts\Activate
   ```

3. Install requirements

   ```bash
   pip install -r requirements.txt
   ```

4. Register the .venv as a Jupyter kernel

   ```
   python -m ipykernel install --user --name venv_m3 --display-name "Python (venv_m3)"
   ```

   Note: this can be removed anytime through the command `jupyter kernelspec uninstall venv_m3`

## Run the Program

1. Activate your .venv if you haven't already.
2. Configure the variables at the top of the `run_all.py` file as desired and modify as needed. E.g.:

   ```py
   REPLICATIONS = 25
   FORCE_REGEN = False        # True = Re-run the raw-data generator
   CLEAR_OUTPUTS = True       # True = wipe prior comparison outputs) during run setup

   # Fix the number of orders/totes/itemtypes. Set to empty dict to randomize this
   SRC_COUNT_DICT = {
       "n_orders": str(11),
       "n_totes": str(14),
       "n_itemtypes": str(8),
   }
   ```

3. Run `python run_all.py`

## Statistical Analysis

Run the `statistical_analysis.ipynb` notebook to analyze the `comparison_summary.csv` outputted from the `run_all.py` program.

1. Activate your .venv if you haven't already.
2. Ensure you have the output data from the `run_all.py` program to analyze (see [Run the Program](#run-the-program) above)
3. Go to the `statistical_analysis.ipynb`, select your venv kernel, and run the program.
   - Note: you may need to install the `Jupyter` VScode extension.

## Run the Streamlit Dashboard

1. Run the analytics dashboard

   ```bash
   streamlit run dashboard.py
   ```

2. When redirected to the Streamlit dashboard on your browser, click the `Run Simulation` button to trigger the dashboard. Graphs can take up to 3 minutes to load
