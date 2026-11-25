import os
from pathlib import Path
from threading import Lock
from uuid import uuid4

from dotenv import load_dotenv
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# Load the local settings before importing modules that use the database.
PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

from analyze import analyze_dataset, load_dataset, save_analysis
from database.database import fetch_all
from generate_insights import generate_insights, save_insights
from upload_dataset import register_uploaded_dataset
import generate_report as report_module
import visualize_dataset as visualization_module


# Protect existing modules that use shared global state.
VISUALIZATION_LOCK = Lock()
AGENT_LOCK = Lock()


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Autonomous Data Analyst",
    page_icon="📊",
    layout="wide",
)

st.title("Autonomous Data Analyst")
st.write("Upload, clean, analyze, and explore your datasets.")


# --------------------------------------------------
# DATASET HELPERS
# --------------------------------------------------

def get_datasets():
    """Return registered datasets from PostgreSQL."""
    query = """
        SELECT
            dataset_id,
            dataset_name,
            file_type,
            total_rows,
            total_columns,
            uploaded_at,
            cleaned_file_path
        FROM datasets
        ORDER BY uploaded_at DESC, dataset_id DESC;
    """
    return fetch_all(query)


def get_hidden_dataset_ids():
    """Read dataset IDs to hide from the local .env setting."""
    raw_ids = os.getenv("HIDDEN_DATASET_IDS", "")
    hidden_ids = set()

    for value in raw_ids.split(","):
        value = value.strip()
        if value.isdigit():
            hidden_ids.add(int(value))

    return hidden_ids


def load_selected_dataset(dataset_id):
    """Load a dataset using the existing analysis module."""
    df, dataset = load_dataset(dataset_id)

    if df is None or dataset is None:
        raise ValueError("The selected dataset could not be loaded.")

    return df, dataset


def make_state_key(prefix, dataset_id):
    """Create a Streamlit session-state key for a dataset."""
    return f"{prefix}_{dataset_id}"


# --------------------------------------------------
# SIDEBAR: UPLOAD AND DATASET SELECTION
# --------------------------------------------------

st.sidebar.header("Dataset")

with st.sidebar.form("upload_dataset_form", clear_on_submit=True):
    uploaded_file = st.file_uploader(
        "Upload a CSV or Excel file",
        type=["csv", "xlsx", "xls"],
    )
    upload_clicked = st.form_submit_button("Upload dataset")

if upload_clicked:
    if uploaded_file is None:
        st.sidebar.warning("Choose a file first.")
    else:
        try:
            with st.spinner("Uploading dataset..."):
                uploaded_dataset = register_uploaded_dataset(
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                )

            st.session_state["selected_dataset_id"] = int(
                uploaded_dataset["dataset_id"]
            )
            st.session_state["upload_success_message"] = (
                f"Uploaded {uploaded_dataset['dataset_name']} successfully."
            )
            st.rerun()

        except Exception as error:
            st.sidebar.error(f"Upload failed: {error}")

if "upload_success_message" in st.session_state:
    st.sidebar.success(
        st.session_state.pop("upload_success_message")
    )


try:
    datasets = get_datasets()
    hidden_dataset_ids = get_hidden_dataset_ids()

    datasets = [
        dataset
        for dataset in datasets
        if int(dataset["dataset_id"]) not in hidden_dataset_ids
    ]

except Exception as error:
    st.error(f"Could not load the dataset list: {error}")
    st.stop()

if not datasets:
    st.info("Upload a dataset to get started.")
    st.stop()

dataset_by_id = {
    int(dataset["dataset_id"]): dataset
    for dataset in datasets
}

dataset_ids = list(dataset_by_id.keys())

# Clear a prior selection if it has since been hidden or removed.
if (
    "selected_dataset_id" in st.session_state
    and st.session_state["selected_dataset_id"] not in dataset_ids
):
    del st.session_state["selected_dataset_id"]


def dataset_label(dataset_id):
    dataset = dataset_by_id[dataset_id]
    return f"#{dataset_id} — {dataset['dataset_name']}"


selected_dataset_id = st.sidebar.selectbox(
    "Choose a dataset",
    options=dataset_ids,
    format_func=dataset_label,
    key="selected_dataset_id",
)

selected_dataset = dataset_by_id[selected_dataset_id]

try:
    df, loaded_dataset = load_selected_dataset(selected_dataset_id)
except Exception as error:
    st.error(f"Could not load the selected dataset: {error}")
    st.stop()

st.sidebar.caption(
    f"{len(df):,} rows × {len(df.columns):,} columns"
)

if selected_dataset.get("cleaned_file_path"):
    st.sidebar.caption("Using the cleaned dataset.")
else:
    st.sidebar.caption("Using the original dataset.")


# --------------------------------------------------
# MAIN CONTENT
# --------------------------------------------------

(
    overview_tab,
    cleaning_tab,
    analysis_tab,
    insights_tab,
    charts_tab,
    chat_tab,
    report_tab,
) = st.tabs(
    [
        "Overview",
        "Cleaning",
        "Analysis",
        "AI Insights",
        "Visualizations",
        "AI Chat",
        "Report",
    ]
)


# --------------------------------------------------
# OVERVIEW
# --------------------------------------------------

with overview_tab:
    st.subheader("Dataset overview")

    missing_count = int(df.isna().sum().sum())
    duplicate_count = int(df.duplicated().sum())

    metric_columns = st.columns(4)
    metric_columns[0].metric("Rows", f"{len(df):,}")
    metric_columns[1].metric("Columns", f"{len(df.columns):,}")
    metric_columns[2].metric("Missing values", f"{missing_count:,}")
    metric_columns[3].metric("Duplicate rows", f"{duplicate_count:,}")

    st.markdown("#### Preview")
    st.dataframe(df.head(100), use_container_width=True)

    st.markdown("#### Column details")
    column_details = pd.DataFrame(
        {
            "Column": df.columns.astype(str),
            "Data type": [str(dtype) for dtype in df.dtypes],
            "Missing values": [
                int(df[column].isna().sum())
                for column in df.columns
            ],
            "Unique values": [
                int(df[column].nunique(dropna=True))
                for column in df.columns
            ],
        }
    )
    st.dataframe(column_details, use_container_width=True)

    with st.expander("Statistical summary"):
        st.dataframe(
            df.describe(include="all").transpose(),
            use_container_width=True,
        )


# --------------------------------------------------
# CLEANING
# --------------------------------------------------

with cleaning_tab:
    st.subheader("Clean dataset")
    st.write(
        "Run the existing cleaning workflow. It removes duplicate rows, "
        "standardizes supported fields, validates data, saves a cleaned CSV, "
        "and records a cleaning report."
    )

    cleaning_state_key = make_state_key(
        "cleaning_report",
        selected_dataset_id,
    )

    if st.button(
        "Run cleaning",
        key=make_state_key("run_cleaning", selected_dataset_id),
    ):
        try:
            from clean_dataset import clean_dataset

            with st.spinner("Cleaning dataset..."):
                cleaning_report = clean_dataset(selected_dataset_id)

            st.session_state[cleaning_state_key] = cleaning_report
            st.success("Cleaning completed.")
            st.rerun()

        except Exception as error:
            st.error(f"Cleaning failed: {error}")

    if cleaning_state_key in st.session_state:
        st.markdown("#### Latest cleaning report")
        st.json(st.session_state[cleaning_state_key])


# --------------------------------------------------
# ANALYSIS
# --------------------------------------------------

with analysis_tab:
    st.subheader("Dataset analysis")

    analysis_state_key = make_state_key(
        "analysis_results",
        selected_dataset_id,
    )

    if st.button(
        "Run analysis",
        key=make_state_key("run_analysis", selected_dataset_id),
    ):
        try:
            with st.spinner("Analyzing dataset..."):
                results = analyze_dataset(df)
                save_analysis(selected_dataset_id, results)

            st.session_state[analysis_state_key] = results
            st.success(
                "Analysis completed. The existing module was asked to "
                "save the results to PostgreSQL."
            )

        except Exception as error:
            st.error(f"Analysis failed: {error}")

    if analysis_state_key in st.session_state:
        results = st.session_state[analysis_state_key]

        st.metric("Total rows", f"{results['total_rows']:,}")
        st.metric("Total columns", f"{results['total_columns']:,}")
        st.metric(
            "Missing values",
            f"{results['total_missing_values']:,}",
        )
        st.metric("Duplicate rows", f"{results['duplicate_rows']:,}")

        with st.expander("Column details"):
            st.json(results["column_details"])

        with st.expander("Numerical summary"):
            st.dataframe(
                pd.DataFrame(results["numeric_summary"]),
                use_container_width=True,
            )

        with st.expander("Categorical summary"):
            st.dataframe(
                pd.DataFrame(results["categorical_summary"]),
                use_container_width=True,
            )


# --------------------------------------------------
# AUTOMATED INSIGHTS
# --------------------------------------------------

with insights_tab:
    st.subheader("Automated business insights")

    insights_state_key = make_state_key(
        "generated_insights",
        selected_dataset_id,
    )

    if st.button(
        "Generate insights",
        key=make_state_key("run_insights", selected_dataset_id),
    ):
        try:
            with st.spinner("Generating insights..."):
                insights = generate_insights(df.copy())
                save_insights(selected_dataset_id, insights)

            st.session_state[insights_state_key] = insights
            st.success("Insights generated.")

        except Exception as error:
            st.error(f"Could not generate insights: {error}")

    if insights_state_key in st.session_state:
        for insight in st.session_state[insights_state_key]:
            st.markdown(f"- {insight}")


# --------------------------------------------------
# VISUALIZATIONS
# --------------------------------------------------

with charts_tab:
    st.subheader("Dataset visualizations")

    if st.button(
        "Generate visualizations",
        key=make_state_key("run_visualizations", selected_dataset_id),
    ):
        try:
            with st.spinner("Generating charts..."):
                with VISUALIZATION_LOCK:
                    visualization_module.set_output_folder(
                        selected_dataset_id
                    )
                    visualization_module.clear_old_charts()

                    (
                        numeric_columns,
                        categorical_columns,
                        date_columns,
                    ) = visualization_module.identify_columns(df)

                    visualization_module.create_bar_chart(
                        df,
                        categorical_columns,
                        numeric_columns,
                    )
                    visualization_module.create_histogram(
                        df,
                        numeric_columns,
                    )
                    visualization_module.create_line_chart(
                        df,
                        date_columns,
                        numeric_columns,
                    )
                    visualization_module.create_scatter_plot(
                        df,
                        numeric_columns,
                    )
                    visualization_module.create_correlation_heatmap(
                        df,
                        numeric_columns,
                    )
                    visualization_module.create_location_or_category_chart(
                        df
                    )

            st.success("Visualization generation finished.")

        except Exception as error:
            st.error(f"Could not generate visualizations: {error}")

    chart_folder = (
        Path(visualization_module.VISUALIZATION_BASE_FOLDER)
        / f"dataset_{selected_dataset_id}"
    )

    if chart_folder.exists():
        chart_files = [
            chart_folder / filename
            for filename in visualization_module.CHART_FILES
            if (chart_folder / filename).is_file()
        ]

        if chart_files:
            for chart_path in chart_files:
                st.image(
                    str(chart_path),
                    caption=chart_path.stem.replace("_", " ").title(),
                    use_container_width=True,
                )
        else:
            st.info("No charts exist for this dataset yet.")
    else:
        st.info("Generate visualizations to display charts here.")


# --------------------------------------------------
# AI CHAT
# --------------------------------------------------

with chat_tab:
    st.subheader("Ask questions about this dataset")

    chat_states = st.session_state.setdefault("chat_states", {})
    dataset_chat_key = str(selected_dataset_id)

    if dataset_chat_key not in chat_states:
        chat_states[dataset_chat_key] = {
            "session_id": str(uuid4()),
            "agent": None,
            "messages": [],
        }

    chat_state = chat_states[dataset_chat_key]

    for message in chat_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input(
        "Ask a question about the selected dataset",
        key=make_state_key("chat_input", selected_dataset_id),
    )

    if question:
        chat_state["messages"].append(
            {"role": "user", "content": question}
        )

        try:
            with st.spinner("Analyzing your question..."):
                with AGENT_LOCK:
                    from agents.data_analyst_agent import (
                        ask_agent,
                        create_data_analyst_agent,
                    )
                    from ask_question import save_chat
                    from tools.dataset_tools import set_active_dataset

                    if chat_state["agent"] is None:
                        chat_state["agent"] = create_data_analyst_agent(
                            df.copy()
                        )

                    set_active_dataset(df.copy())

                    save_chat(
                        selected_dataset_id,
                        chat_state["session_id"],
                        "user",
                        question,
                    )

                    answer = ask_agent(
                        chat_state["agent"],
                        question,
                        thread_id=chat_state["session_id"],
                    )

                    save_chat(
                        selected_dataset_id,
                        chat_state["session_id"],
                        "assistant",
                        answer,
                    )

            chat_state["messages"].append(
                {"role": "assistant", "content": answer}
            )
            st.rerun()

        except Exception as error:
            st.error(f"Could not answer the question: {error}")


# --------------------------------------------------
# HTML REPORT
# --------------------------------------------------

with report_tab:
    st.subheader("Analysis report")

    report_path = (
        Path(report_module.REPORT_FOLDER)
        / f"dataset_report_{selected_dataset_id}.html"
    )

    if st.button(
        "Generate HTML report",
        key=make_state_key("run_report", selected_dataset_id),
    ):
        try:
            with st.spinner("Generating report..."):
                report_module.generate_report(selected_dataset_id)

            if report_path.is_file():
                st.success("HTML report generated.")
            else:
                st.error(
                    "The report module finished, but the expected report "
                    "file was not found."
                )

        except Exception as error:
            st.error(f"Could not generate the report: {error}")

    if report_path.is_file():
        report_html = report_path.read_text(encoding="utf-8")

        st.download_button(
            "Download HTML report",
            data=report_html,
            file_name=report_path.name,
            mime="text/html",
            key=make_state_key("download_report", selected_dataset_id),
        )

        with st.expander("Preview report", expanded=True):
            components.html(
                report_html,
                height=900,
                scrolling=True,
            )
    else:
        st.info("Generate the report to preview or download it.")