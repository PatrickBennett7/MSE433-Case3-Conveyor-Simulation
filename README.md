# M3: Warehousing

## Run the Program

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

### Run the Program
1. Activate your .venv if you haven't already.
2. Configure the variables at the top of the `run_all.py` file as desired.

    ```py
    # Modify as needed. E.g.:
    REPLICATIONS = 25
    FORCE_REGEN = False   # True = Re-run the raw-data generator
    CLEAR_OUTPUTS = True  # True = wipe prior comparison outputs) during run setup
    ```
3. Run `python run_all.py`

### Run Streamlit Dashboard
1. Run the analytics dashboard
   
    ```bash
    streamlit run dashboard.py
    ```
3. When redirected to the Streamlit dashboard on your browser, click the `Run Simulation` button to trigger the dashboard. Graphs can take up to 3 minutes to load
