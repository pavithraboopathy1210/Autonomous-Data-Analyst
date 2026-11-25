import os
import json
from pathlib import Path

import pandas as pd
from psycopg2.extras import RealDictCursor

from database.database import get_connection


# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent


# --------------------------------------------------
# RESOLVE DATASET PATH
# --------------------------------------------------

def resolve_dataset_path(stored_path):
    """Resolve an absolute or project-relative path stored in PostgreSQL."""

    path = Path(stored_path).expanduser()

    if not path.is_absolute():
        path = BASE_DIR / path

    return path.resolve()


# --------------------------------------------------
# LOAD DATASET FROM DATABASE
# --------------------------------------------------

def load_dataset(dataset_id):
    connection = None

    try:
        connection = get_connection()

        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT
                    dataset_id,
                    dataset_name,
                    file_path,
                    cleaned_file_path,
                    file_type
                FROM datasets
                WHERE dataset_id = %s;
            """

            cursor.execute(query, (dataset_id,))
            dataset = cursor.fetchone()

        if not dataset:
            print("Dataset not found!")
            return None, None

        cleaned_path_value = dataset.get("cleaned_file_path")

        if cleaned_path_value:
            file_path = resolve_dataset_path(cleaned_path_value)
            dataset_source = "cleaned"

            if not file_path.is_file():
                print("The cleaned dataset path is saved in PostgreSQL, but the file does not exist:")
                print(file_path)
                print("Please run clean_dataset.py again for this dataset.")
                return None, None
        else:
            file_path = resolve_dataset_path(dataset["file_path"])
            dataset_source = "original"

            print("No cleaned file path is registered for this dataset.")
            print("The original uploaded dataset will be analyzed.")

        if not file_path.is_file():
            print("Dataset file does not exist:", file_path)
            return None, None

        print("\nLoading dataset:", dataset["dataset_name"])
        print("Dataset source:", dataset_source)
        print("File path:", file_path)

        extension = file_path.suffix.lower()

        if extension == ".csv":
            df = pd.read_csv(file_path)
        elif extension in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path)
        else:
            print("Unsupported file format!")
            return None, None

        dataset["loaded_file_path"] = str(file_path)
        dataset["dataset_source"] = dataset_source

        return df, dataset

    except Exception as error:
        print("Dataset loading error:", error)
        return None, None

    finally:
        if connection:
            connection.close()


# --------------------------------------------------
# DATASET ANALYSIS
# --------------------------------------------------

def analyze_dataset(df):
    total_rows = len(df)
    total_columns = len(df.columns)

    missing_values = df.isnull().sum()
    duplicate_rows = int(df.duplicated().sum())

    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.tolist()

    column_details = {}

    for column in df.columns:
        column_details[column] = {
            "data_type": str(df[column].dtype),
            "missing_values": int(missing_values[column]),
            "missing_percentage": round(
                float(missing_values[column] / total_rows * 100), 2
            ) if total_rows > 0 else 0,
            "unique_values": int(df[column].nunique())
        }

    numeric_summary = df[numeric_columns].describe().to_dict()
    categorical_summary = df[categorical_columns].describe().to_dict()

    results = {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "duplicate_rows": duplicate_rows,
        "total_missing_values": int(missing_values.sum()),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "column_details": column_details,
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary
    }

    return results


# --------------------------------------------------
# DISPLAY ANALYSIS RESULTS
# --------------------------------------------------

def display_results(results):
    print("\n" + "=" * 50)
    print("       DATASET ANALYSIS REPORT")
    print("=" * 50)

    print("\n1. GENERAL INFORMATION")
    print("Total Rows:", results["total_rows"])
    print("Total Columns:", results["total_columns"])

    print("\n2. DATA QUALITY")
    print("Missing Values:", results["total_missing_values"])
    print("Duplicate Rows:", results["duplicate_rows"])

    print("\n3. NUMERIC COLUMNS")
    print(results["numeric_columns"])

    print("\n4. CATEGORICAL COLUMNS")
    print(results["categorical_columns"])

    print("\n5. COLUMN DETAILS")
    for column, details in results["column_details"].items():
        print("\nColumn:", column)
        for key, value in details.items():
            print(f"{key}: {value}")

    print("\n6. NUMERIC SUMMARY")
    if results["numeric_summary"]:
        print(pd.DataFrame(results["numeric_summary"]).to_string())
    else:
        print("No numeric columns found.")

    print("\n7. CATEGORICAL SUMMARY")
    if results["categorical_summary"]:
        print(pd.DataFrame(results["categorical_summary"]).to_string())
    else:
        print("No categorical columns found.")

    print("\n" + "=" * 50)


# --------------------------------------------------
# SAVE ANALYSIS IN POSTGRESQL
# --------------------------------------------------

def save_analysis(dataset_id, results):
    connection = None

    try:
        connection = get_connection()

        with connection.cursor() as cursor:
            query = """
                INSERT INTO analysis_history
                (dataset_id, analysis_type, analysis_result)
                VALUES (%s, %s, %s::jsonb);
            """

            cursor.execute(
                query,
                (
                    dataset_id,
                    "Basic Dataset Analysis",
                    json.dumps(results, default=str, allow_nan=False)
                )
            )

        connection.commit()
        print("\nAnalysis results saved successfully!")

    except Exception as error:
        if connection:
            connection.rollback()
        print("Error saving analysis:", error)

    finally:
        if connection:
            connection.close()


# --------------------------------------------------
# MAIN FUNCTION
# --------------------------------------------------

def main():
    print("\nAUTONOMOUS DATA ANALYST")
    print("----------------------")

    dataset_id = input("Enter Dataset ID: ").strip()

    if not dataset_id.isdigit():
        print("Please enter a valid numeric Dataset ID.")
        return

    dataset_id = int(dataset_id)
    df, dataset = load_dataset(dataset_id)

    if df is None:
        return

    print("\nDataset loaded successfully!")
    results = analyze_dataset(df)
    results["dataset_source"] = dataset["dataset_source"]
    results["source_file_path"] = dataset["loaded_file_path"]

    display_results(results)
    save_analysis(dataset_id, results)


if __name__ == "__main__":
    main()
