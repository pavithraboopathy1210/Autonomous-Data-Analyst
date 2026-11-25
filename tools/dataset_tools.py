
import json
import pandas as pd
from typing import Literal
from langchain_core.tools import tool


active_df = None


def set_active_dataset(df):
    global active_df
    active_df = df.copy()


def get_dataset():
    if active_df is None:
        raise ValueError("No dataset is currently loaded.")
    return active_df


def make_json_safe(value):
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [make_json_safe(v) for v in value]

    if isinstance(value, tuple):
        return [make_json_safe(v) for v in value]

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        value = value.item()

    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()

    return value


def to_json(data):
    return json.dumps(
        make_json_safe(data),
        allow_nan=False,
        default=str
    )


@tool
def dataset_overview_tool():
    """Get the dataset row count, column count, column names,
    data types, missing values, and duplicate row count."""

    df = get_dataset()

    result = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "column_names": list(df.columns),
        "data_types": df.dtypes.astype(str).to_dict(),
        "missing_values": int(df.isnull().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum())
    }

    return to_json(result)


@tool
def missing_values_tool():
    """Get missing value counts and percentages for every column."""

    df = get_dataset()

    missing_count = df.isnull().sum()
    missing_percentage = (missing_count / len(df)) * 100

    result = {
        column: {
            "missing_count": int(missing_count[column]),
            "missing_percentage": round(float(missing_percentage[column]), 2)
        }
        for column in df.columns
    }

    return to_json(result)


@tool
def numerical_summary_tool(column: str):
    """Get count, mean, median, standard deviation, minimum,
    maximum, and quartiles for a numerical column."""

    df = get_dataset()

    if column not in df.columns:
        return f"Column '{column}' does not exist."

    numeric_data = pd.to_numeric(df[column], errors="coerce").dropna()

    if numeric_data.empty:
        return f"Column '{column}' has no valid numerical values."

    result = {
        "column": column,
        "count": int(numeric_data.count()),
        "mean": float(numeric_data.mean()),
        "median": float(numeric_data.median()),
        "standard_deviation": float(numeric_data.std()),
        "minimum": float(numeric_data.min()),
        "maximum": float(numeric_data.max()),
        "25_percentile": float(numeric_data.quantile(0.25)),
        "50_percentile": float(numeric_data.quantile(0.50)),
        "75_percentile": float(numeric_data.quantile(0.75))
    }

    return to_json(result)


@tool
def grouped_analysis_tool(
    group_column: str,
    value_column: str,
    operation: Literal["sum", "mean", "count", "max", "min"]
):
    """Perform sum, mean, count, maximum, or minimum calculations
    on a value column grouped by another column."""

    df = get_dataset()

    if group_column not in df.columns:
        return f"Column '{group_column}' does not exist."

    if value_column not in df.columns:
        return f"Column '{value_column}' does not exist."

    grouped = df.groupby(group_column, dropna=False)[value_column]

    if operation == "sum":
        result = grouped.sum()
    elif operation == "mean":
        result = grouped.mean()
    elif operation == "count":
        result = grouped.count()
    elif operation == "max":
        result = grouped.max()
    elif operation == "min":
        result = grouped.min()
    else:
        return "Unsupported operation."

    return to_json(result.to_dict())


@tool
def correlation_tool(column1: str, column2: str):
    """Calculate Pearson correlation between two numerical columns."""

    df = get_dataset()

    if column1 not in df.columns or column2 not in df.columns:
        return "One or both specified columns do not exist."

    first = pd.to_numeric(df[column1], errors="coerce")
    second = pd.to_numeric(df[column2], errors="coerce")

    correlation = first.corr(second)

    if pd.isna(correlation):
        return "Correlation could not be calculated for these columns."

    result = {
        "column1": column1,
        "column2": column2,
        "pearson_correlation": float(correlation)
    }

    return to_json(result)


@tool
def frequency_analysis_tool(column: str):
    """Get the most frequent values and their counts in a column."""

    df = get_dataset()

    if column not in df.columns:
        return f"Column '{column}' does not exist."

    frequencies = df[column].value_counts(dropna=False).head(20)

    result = {
        str(key): int(value)
        for key, value in frequencies.items()
    }

    return to_json(result)


@tool
def highest_value_record_tool(column: str = "sales_amount"):
    """Find the individual dataset record with the highest value
    in a numerical column. Returns the actual row and its details.
    Use this for questions about the highest individual sale,
    transaction, order, or record. Do not use grouped totals."""

    df = get_dataset()

    if column not in df.columns:
        return f"Column '{column}' does not exist."

    numeric_data = pd.to_numeric(df[column], errors="coerce")

    if numeric_data.notna().sum() == 0:
        return f"Column '{column}' has no valid numerical values."

    position = numeric_data.argmax()
    record = df.iloc[position].to_dict()

    result = {
        "column": column,
        "highest_value": float(numeric_data.iloc[position]),
        "record_position": int(position) + 1,
        "record_details": record
    }

    return to_json(result)


dataset_tools = [
    dataset_overview_tool,
    missing_values_tool,
    numerical_summary_tool,
    grouped_analysis_tool,
    correlation_tool,
    frequency_analysis_tool,
    highest_value_record_tool
]
