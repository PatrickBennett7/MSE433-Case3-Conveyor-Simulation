import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import subprocess
import time

# --- Page Config ---
st.set_page_config(page_title="Conveyor Simulation Dashboard", layout="wide")
st.title("Conveyor Belt Order Fulfillment Dashboard")

# ── Helper: pick the best completed run ──────────────────────────────────────
def get_best_run(summary: pd.DataFrame) -> int:
    completed = summary[summary["all_orders_completed"] == True]
    if completed.empty:
        return int(summary.loc[summary["avg_order_time"].idxmin(), "run_id"])
    return int(completed.loc[completed["avg_order_time"].idxmin(), "run_id"])


# ── Helper: derive item-level release events from solution_output ─────────────
def build_item_events(solution_output: pd.DataFrame,
                      order_times: pd.DataFrame) -> pd.DataFrame:
    """
    solution_output rows correspond to orders (one row per order, in order index).
    Columns: conv_num, circle, pentagon, trapezoid, triangle, star, moon, heart, cross
    order_times has: order_num, completion_time, conveyor

    We spread each order's items evenly between first_item_time and completion_time.
    first_item_time = completion_time - fulfillment_duration (approximated as
    completion_time - (items * avg_gap)).  For simplicity we space items equally
    within a fixed window ending at completion_time.
    """
    item_types = ["circle", "pentagon", "trapezoid", "triangle", "star", "moon", "heart", "cross"]
    rows = []
    for idx, sol_row in solution_output.iterrows():
        order_idx = idx + 1          # 1-based order number
        match = order_times[order_times["order_num"] == order_idx]
        if match.empty:
            continue
        ct = float(match.iloc[0]["completion_time"])
        belt = int(match.iloc[0]["conveyor"])

        # collect items for this order
        items = []
        for it in item_types:
            count = int(sol_row.get(it, 0))
            items.extend([it] * count)

        n = len(items)
        if n == 0:
            continue
        # spread release times: last item at completion_time, earlier items spaced by 7.5 s
        for k, item in enumerate(items):
            release_time = ct - (n - 1 - k) * 7.5
            rows.append({
                "order_num": order_idx,
                "belt": belt,
                "item_type": item,
                "release_time": release_time,
                "completion_time": ct,
            })

    return pd.DataFrame(rows)


# ── Helper: build fulfillment durations ──────────────────────────────────────
def build_durations(order_times: pd.DataFrame, item_events: pd.DataFrame) -> pd.DataFrame:
    """Duration = last item release time − first item release time per order."""
    if item_events.empty:
        return pd.DataFrame(columns=["order_num", "duration"])
    grp = item_events.groupby("order_num")["release_time"]
    dur = (grp.max() - grp.min()).reset_index()
    dur.columns = ["order_num", "duration"]
    dur["order_num"] = dur["order_num"].astype(int)
    return dur.sort_values("order_num")


# ── Helper: items per order ───────────────────────────────────────────────────
def build_items_per_order(item_events: pd.DataFrame) -> pd.DataFrame:
    if item_events.empty:
        return pd.DataFrame(columns=["order_num", "count"])
    cnt = item_events.groupby("order_num").size().reset_index(name="count")
    cnt["order_num"] = cnt["order_num"].astype(int)
    return cnt.sort_values("order_num")


# ── Helper: item type frequency ───────────────────────────────────────────────
def build_item_freq(item_events: pd.DataFrame) -> pd.DataFrame:
    if item_events.empty:
        return pd.DataFrame(columns=["item_type", "count"])
    freq = item_events.groupby("item_type").size().reset_index(name="count")
    return freq.sort_values("count", ascending=False)


# ── Helper: items released per belt ──────────────────────────────────────────
def build_belt_counts(item_events: pd.DataFrame) -> pd.DataFrame:
    if item_events.empty:
        return pd.DataFrame(columns=["belt", "count"])
    cnt = item_events.groupby("belt").size().reset_index(name="count")
    cnt["belt"] = "Belt " + cnt["belt"].astype(str)
    return cnt.sort_values("belt")


# ── Shared styling constants ─────────────────────────────────────────────────
CHART_TITLE_STYLE = dict(font=dict(size=14, color="black"), x=0.5, xanchor="center")

BLACK_AXIS = dict(
    color="black",
    linecolor="black",
    linewidth=1,
    showline=True,
    ticks="outside",
    tickcolor="black",
    tickfont=dict(color="black"),
    title=dict(font=dict(color="black")),
    title_font=dict(color="black", size=12),
    gridcolor="rgba(0,0,0,0.12)",
    showgrid=True,
    zeroline=False,
)

def chart_layout(title: str, height: int = 300, extra: dict = None) -> dict:
    """Return a consistent update_layout dict for all sub-charts."""
    base = dict(
        title=dict(text=title, **CHART_TITLE_STYLE),
        height=height,
        margin=dict(l=50, r=30, t=50, b=50),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        xaxis=BLACK_AXIS.copy(),
        yaxis=BLACK_AXIS.copy(),
        font=dict(color="black"),
    )
    if extra:
        for k, v in extra.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                base[k] = {**base[k], **v}
            else:
                base[k] = v
    return base


# ── Colour palette (matches reference image) ──────────────────────────────────
BELT_COLORS = {
    "Belt 1": "#4C72B0",
    "Belt 2": "#DD8452",
    "Belt 3": "#55A868",
    "Belt 4": "#C44E52",
}
ORDER_COLORS = px.colors.qualitative.Set2

# ═════════════════════════════════════════════════════════════════════════════
# 1. SIMULATION CONTROL
# ═════════════════════════════════════════════════════════════════════════════
if st.button("Run Simulation", type="primary", use_container_width=False):
    try:
        with st.spinner("Running simulation…"):
            subprocess.run(["python", "run_all.py"], check=True)
            st.success("Simulation completed successfully!")
        time.sleep(1)

        comparison_summary  = pd.read_csv("Data/comparison/comparison_summary.csv")
        order_times         = pd.read_csv("Data/comparison/comparison_order_times.csv")
        order_conveyor      = pd.read_csv("Data/comparison/comparison_order_conveyor.csv")
        solution_output     = pd.read_csv("Data/comparison/solution_output.csv")

        st.session_state["comparison_summary"] = comparison_summary
        st.session_state["order_times"]        = order_times
        st.session_state["order_conveyor"]     = order_conveyor
        st.session_state["solution_output"]    = solution_output

        # ── Show best algorithm immediately after success ──────────────────
        _best_id    = get_best_run(comparison_summary)
        _best_label = comparison_summary.loc[
            comparison_summary["run_id"] == _best_id, "run_label"
        ].iloc[0]
        st.info(f"Best performing algorithm: **{_best_label}**  (run_id = {_best_id})")
    except subprocess.CalledProcessError as e:
        st.error(f"Simulation failed: {e}")

# ── Dev convenience: auto-load from /mnt paths if available ──────────────────
import os, pathlib
if "comparison_summary" not in st.session_state:
    _paths = {
        "comparison_summary":  "Data/comparison/comparison_summary.csv",
        "order_times":         "Data/comparison/comparison_order_times.csv",
        "order_conveyor":      "Data/comparison/comparison_order_conveyor.csv",
        "solution_output":     "Data/comparison/solution_output.csv",
    }
    if all(pathlib.Path(p).exists() for p in _paths.values()):
        for k, p in _paths.items():
            st.session_state[k] = pd.read_csv(p)

# ═════════════════════════════════════════════════════════════════════════════
# 2. KPI METRICS
# ═════════════════════════════════════════════════════════════════════════════
st.subheader("Key Performance Indicators")
kpi1, kpi2, kpi3 = st.columns(3)
if "comparison_summary" in st.session_state:
    summary = st.session_state["comparison_summary"]
    completed = summary[summary["all_orders_completed"] == True]
    best_avg      = completed["avg_order_time"].min() if not completed.empty else float("nan")
    best_makespan = summary["total_time"].min()
    # Avg conveyor utilization for best run:
    # Each belt is sequential and all items released at t=0, so a belt is active
    # from t=0 until its last order completes. Utilization = last_completion / makespan.
    # Average this across all belts that had at least one order.
    _best_id_kpi = get_best_run(summary)
    _makespan    = summary.loc[summary["run_id"] == _best_id_kpi, "total_time"].iloc[0]
    _ot_kpi      = st.session_state["order_times"][
        st.session_state["order_times"]["run_id"] == _best_id_kpi
    ]
    if not _ot_kpi.empty and _makespan > 0:
        _belt_last = _ot_kpi.groupby("conveyor")["completion_time"].max()
        avg_conv_util = (_belt_last / _makespan).mean() * 100
    else:
        avg_conv_util = float("nan")
    with kpi1:
        st.metric("Best Avg Order Time",  f"{best_avg:.2f}s" if not pd.isna(best_avg) else "N/A")
    with kpi2:
        st.metric("Best Makespan",        f"{best_makespan:.2f}s")
    with kpi3:
        st.metric("Avg Conveyor Utilization", f"{avg_conv_util:.1f}%" if not pd.isna(avg_conv_util) else "N/A")
else:
    st.warning("Run the simulation to see metrics.")

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# DERIVE FILTERED DATA FOR BEST RUN
# ═════════════════════════════════════════════════════════════════════════════
if "comparison_summary" in st.session_state:
    summary         = st.session_state["comparison_summary"]
    best_run_id     = get_best_run(summary)
    best_run_label  = summary.loc[summary["run_id"] == best_run_id, "run_label"].iloc[0]

    ot_best = st.session_state["order_times"][
        st.session_state["order_times"]["run_id"] == best_run_id
    ].copy()
    oc_best = st.session_state["order_conveyor"][
        st.session_state["order_conveyor"]["run_id"] == best_run_id
    ].copy()

    # Merge conveyor assignment into order_times for labelling
    ot_best = ot_best.sort_values("order_num").reset_index(drop=True)
    ot_best["order_label"] = "O" + ot_best["order_num"].astype(str)

    # Build item-level events from solution_output (if available)
    if "solution_output" in st.session_state:
        item_events = build_item_events(
            st.session_state["solution_output"], ot_best
        )
    else:
        item_events = pd.DataFrame()

    has_items = not item_events.empty

    # ── Completion times for dashed vertical lines ──────────────────────────
    completion_times = ot_best["completion_time"].tolist()
    order_labels     = ot_best["order_label"].tolist()

    # ═══════════════════════════════════════════════════════════════════════
    # 3. MAIN TIMELINE (Full width)
    # ═══════════════════════════════════════════════════════════════════════
    if has_items:
        fig_timeline = go.Figure()

        # One trace per belt so the legend works
        for belt_num in sorted(item_events["belt"].unique()):
            bdf  = item_events[item_events["belt"] == belt_num]
            bkey = f"Belt {belt_num}"
            fig_timeline.add_trace(go.Scatter(
                x=bdf["release_time"],
                y=[f"Belt {belt_num}"] * len(bdf),
                mode="markers",
                marker=dict(
                    size=12,
                    color=BELT_COLORS.get(bkey, "#888"),
                    line=dict(width=1, color="white"),
                ),
                text=bdf["item_type"],
                hovertemplate="<b>%{text}</b><br>Time: %{x:.1f}s<extra></extra>",
                name=bkey,
            ))

        # Dashed red verticals for order completions
        for ct, lbl in zip(completion_times, order_labels):
            fig_timeline.add_vline(
                x=ct,
                line=dict(color="red", dash="dash", width=1),
                annotation_text=lbl,
                annotation_position="top",
                annotation_font=dict(color="red", size=9),
            )

        fig_timeline.update_layout(
            title=dict(
                text="Item Release Timeline by Conveyor Belt  (red dashes = order completions)",
                font=dict(size=14, color="black"), x=0.5, xanchor="center",
            ),
            height=280,
            margin=dict(l=20, r=20, t=45, b=30),
            xaxis={**BLACK_AXIS, "title": "Time (s)"},
            yaxis={**BLACK_AXIS, "categoryorder": "array",
                   "categoryarray": ["Belt 4","Belt 3","Belt 2","Belt 1"],
                   "title": None},
            legend=dict(
                orientation="v", x=1.01, y=1,
                font=dict(color="black"),
                bordercolor="black", borderwidth=1,
            ),
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="black"),
        )
        st.plotly_chart(fig_timeline, use_container_width=True)
    else:
        st.info("Upload solution_output.csv to render the item timeline.")

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════
    # 4. SIX CHARTS  (2 rows × 3 columns)
    # ═══════════════════════════════════════════════════════════════════════
    row1_col1, row1_col2, row1_col3 = st.columns(3)
    row2_col1, row2_col2, row2_col3 = st.columns(3)

    # ── Chart 1: Items Released per Belt ────────────────────────────────────
    with row1_col1:
        belt_counts = build_belt_counts(item_events) if has_items else pd.DataFrame()
        if not belt_counts.empty:
            fig = px.bar(
                belt_counts, x="belt", y="count",
                color="belt",
                color_discrete_map=BELT_COLORS,
                text="count",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(**chart_layout("Items Released per Belt",
                extra={"yaxis": {"title": "Count",
                                 "range": [0, belt_counts["count"].max() * 1.2]},
                       "xaxis": {"title": None}}))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No item data")

    # ── Chart 2: Item Type Frequency ─────────────────────────────────────────
    with row1_col2:
        freq = build_item_freq(item_events) if has_items else pd.DataFrame()
        if not freq.empty:
            fig = px.bar(
                freq, y="item_type", x="count",
                orientation="h",
                text="count",
                color="item_type",
                color_discrete_sequence=px.colors.qualitative.Dark2,
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(**chart_layout("Item Type Frequency",
                extra={"yaxis": {"title": None, "categoryorder": "total ascending"},
                       "xaxis": {"title": "Count",
                                 "range": [0, freq["count"].max() * 1.25]}}))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No item data")

  # ── Chart 3: Order Completion Times ──────────────────────────────────────
    with row1_col3:
        ot_plot = ot_best.copy()
        ot_plot["completion_time"] = pd.to_numeric(ot_plot["completion_time"], errors="coerce")
        # Collapse to one row per order to avoid stacked segments
        ot_plot = ot_plot.groupby("order_label", sort=False)["completion_time"].max().reset_index()
        ot_plot = ot_plot.sort_values("order_label")

        y_max = ot_plot["completion_time"].max() * 1.08
        fig = go.Figure()
        for i, row in ot_plot.iterrows():
            fig.add_trace(go.Bar(
                x=[row["order_label"]],
                y=[row["completion_time"]],
                text=[f"{row['completion_time']:.0f}s"],
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color="white", size=11),
                marker_color=ORDER_COLORS[i % len(ORDER_COLORS)],
                showlegend=False,
            ))
        fig.update_layout(
            **chart_layout("Order Completion Times",
                extra={"xaxis": {"title": "Orders"},
                       "yaxis": {"title": "Time (s)", "range": [0, y_max]}}),
            barmode="group",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Chart 4: Order Fulfilment Duration ───────────────────────────────────
    with row2_col1:
        dur = build_durations(ot_best, item_events) if has_items else pd.DataFrame()
        if not dur.empty:
            dur["order_label"] = "O" + dur["order_num"].astype(str)
            fig = px.bar(
                dur, x="order_label", y="duration",
                color="order_label",
                color_discrete_sequence=ORDER_COLORS,
                text=dur["duration"].apply(lambda v: f"{v:.1f}s"),
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(**chart_layout(
                "Order Fulfilment Duration<br><sup>(last item − first item time)</sup>",
                extra={"xaxis": {"title": None},
                       "yaxis": {"title": "Duration (s)",
                                 "range": [0, dur["duration"].max() * 1.2]}}))
            st.plotly_chart(fig, use_container_width=True)
        else:
            fig = px.bar(
                ot_best, x="order_label", y="completion_time",
                color="order_label",
                color_discrete_sequence=ORDER_COLORS,
                text=ot_best["completion_time"].apply(lambda v: f"{v:.1f}s"),
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(**chart_layout(
                "Order Fulfilment Duration<br><sup>(last item − first item time)</sup>",
                extra={"xaxis": {"title": None},
                       "yaxis": {"title": "Time (s)",
                                 "range": [0, ot_best["completion_time"].max() * 1.2]}}))
            st.plotly_chart(fig, use_container_width=True)

    # ── Chart 5: Items per Order ──────────────────────────────────────────────
    with row2_col2:
        ipo = build_items_per_order(item_events) if has_items else pd.DataFrame()
        if not ipo.empty:
            ipo["order_label"] = "O" + ipo["order_num"].astype(str)
            fig = px.bar(
                ipo, x="order_label", y="count",
                color="order_label",
                color_discrete_sequence=ORDER_COLORS,
                text="count",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(**chart_layout("Items per Order",
                extra={"xaxis": {"title": None},
                       "yaxis": {"title": "# Items",
                                 "range": [0, ipo["count"].max() * 1.2]}}))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No item data")

    # ── Chart 6: Cumulative Items Released Over Time ──────────────────────────
    with row2_col3:
        if has_items:
            cum = item_events.sort_values("release_time").copy()
            cum["cum_items"] = range(1, len(cum) + 1)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=cum["release_time"], y=cum["cum_items"],
                mode="lines",
                line=dict(color="#4C72B0", width=2),
                fill="tozeroy",
                fillcolor="rgba(76,114,176,0.15)",
            ))
            for ct, lbl in zip(completion_times, order_labels):
                fig.add_vline(
                    x=ct,
                    line=dict(color="red", dash="dash", width=1),
                    annotation_text=lbl,
                    annotation_position="top",
                    annotation_font=dict(color="red", size=8),
                )
            fig.update_layout(**chart_layout("Cumulative Items Released Over Time",
                extra={"xaxis": {"title": "Time (s)"},
                       "yaxis": {"title": "Cumulative Items"}}))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No item data")

    st.divider()

else:
    st.info("Press **Run Simulation** to load results.")