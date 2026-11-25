import os
import re
import json

import pandas as pd
import numpy as np

from database.database import get_connection


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def clean_dataset(dataset_id):
    """Clean a registered dataset, save it, and return its cleaning report."""
    print("\nAUTONOMOUS DATA ANALYST")
    print("----------------------")
    print("ADVANCED DATA CLEANING MODULE")

    # 1. LOAD DATASET DETAILS FROM POSTGRESQL
    conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT dataset_name, file_path
            FROM datasets
            WHERE dataset_id = %s
            """,
            (dataset_id,),
        )
        dataset = cursor.fetchone()

        if dataset is None:
            raise ValueError(f"Dataset ID {dataset_id} was not found.")

        dataset_name, file_path = dataset
    finally:
        conn.close()

    # 2. LOAD CSV OR EXCEL
    if not os.path.isabs(file_path):
        file_path = os.path.join(BASE_DIR, file_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file was not found: {file_path}")

    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".csv":
        df = pd.read_csv(file_path)
    elif extension in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format. Use CSV or Excel.")

    original_rows = len(df)
    original_columns = len(df.columns)

    # Convert empty strings and whitespace-only values to missing values.
    for column in df.select_dtypes(include=["object"]).columns:
        df[column] = df[column].apply(
            lambda value: np.nan
            if isinstance(value, str) and not value.strip()
            else value
        )

    print(f"\nDataset loaded successfully: {dataset_name}")
    print("Original Rows:", original_rows)
    print("Original Columns:", original_columns)

    # 3. INITIAL MISSING VALUE REPORT
    print("\nMISSING VALUE REPORT")
    print("--------------------")

    missing_report = df.isnull().sum().to_dict()

    for column, count in missing_report.items():
        print(f"{column}: {count}")

    # 4. REMOVE DUPLICATES
    print("\nDUPLICATE RECORDS")
    print("-----------------")

    duplicate_count = int(df.duplicated().sum())
    df = df.drop_duplicates().copy()

    print("Duplicates removed:", duplicate_count)

    # 5. INVALID NUMERICAL DATA VALIDATION
    print("\nINVALID DATA VALIDATION")
    print("-----------------------")

    invalid_report = {}

    if "age" in df.columns:
        df["age"] = pd.to_numeric(df["age"], errors="coerce")

        invalid_age = (df["age"] < 0) | (df["age"] > 120)
        invalid_age_count = int(invalid_age.sum())
        df.loc[invalid_age, "age"] = np.nan

        invalid_report["age"] = {
            "invalid_values": invalid_age_count,
            "valid_range": "0 to 120",
            "action": "Replaced with missing values",
        }

        print("Invalid age values:", invalid_age_count)

    if "purchase_amount" in df.columns:
        df["purchase_amount"] = pd.to_numeric(
            df["purchase_amount"],
            errors="coerce",
        )

        invalid_amount = df["purchase_amount"] < 0
        invalid_amount_count = int(invalid_amount.sum())
        df.loc[invalid_amount, "purchase_amount"] = np.nan

        invalid_report["purchase_amount"] = {
            "invalid_values": invalid_amount_count,
            "valid_range": "0 or greater",
            "action": "Replaced with missing values",
        }

        print("Invalid purchase amounts:", invalid_amount_count)

    # 6. DATE STANDARDIZATION
    print("\nDATE STANDARDIZATION")
    print("--------------------")

    def parse_date(value):
        if pd.isna(value):
            return pd.NaT

        if isinstance(value, (pd.Timestamp, np.datetime64)):
            return pd.to_datetime(value, errors="coerce")

        value = str(value).strip()

        date_formats = [
            (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
            (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y"),
            (r"^\d{2}-\d{2}-\d{4}$", "%m-%d-%Y"),
            (r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$", "%d %b %Y"),
        ]

        for pattern, date_format in date_formats:
            if re.match(pattern, value):
                return pd.to_datetime(
                    value,
                    format=date_format,
                    errors="coerce",
                )

        return pd.NaT

    date_columns = []

    # Detect date columns using column names.
    for column in df.columns:
        if any(
            keyword in str(column).lower()
            for keyword in ["date", "time"]
        ):
            date_columns.append(column)

    # Detect date columns using their values.
    for column in df.select_dtypes(include=["object"]).columns:
        if column in date_columns:
            continue

        non_missing = df[column].dropna()

        if len(non_missing) == 0:
            continue

        parsed_values = non_missing.apply(parse_date)
        success_rate = parsed_values.notna().mean()

        if success_rate >= 0.80:
            date_columns.append(column)

    date_cleaning_report = {}

    for column in date_columns:
        original_values = df[column]
        missing_before = int(original_values.isna().sum())
        parsed_values = original_values.apply(parse_date)

        invalid_count = int(
            (original_values.notna() & parsed_values.isna()).sum()
        )
        converted_count = int(parsed_values.notna().sum())

        df[column] = parsed_values

        date_cleaning_report[column] = {
            "converted_values": converted_count,
            "invalid_values": invalid_count,
            "missing_values_before": missing_before,
            "standardized_format": "YYYY-MM-DD",
        }

        print(f"\nColumn: {column}")
        print("Successfully converted:", converted_count)
        print("Invalid dates:", invalid_count)
        print("Missing dates:", missing_before)

    if not date_columns:
        print("No date columns detected.")

    # 7. NUMERICAL MISSING VALUE HANDLING
    print("\nNUMERICAL MISSING VALUES")
    print("------------------------")

    numeric_columns = df.select_dtypes(include=["number"]).columns
    numeric_fill_report = {}

    for column in numeric_columns:
        missing_count = int(df[column].isnull().sum())

        if missing_count > 0:
            median_value = df[column].median()

            if pd.notna(median_value):
                df[column] = df[column].fillna(median_value)
                numeric_fill_report[column] = {
                    "method": "Median",
                    "filled_values": missing_count,
                    "median_value": float(median_value),
                }

    if numeric_fill_report:
        print(numeric_fill_report)
    else:
        print("No numerical values needed filling.")

    # 8. CATEGORICAL MISSING VALUE HANDLING
    print("\nCATEGORICAL MISSING VALUES")
    print("--------------------------")

    categorical_columns = [
        column
        for column in df.select_dtypes(
            include=["object", "category"]
        ).columns
        if column not in date_columns
        and column not in ["email", "customer_id"]
    ]

    categorical_fill_report = {}

    for column in categorical_columns:
        missing_count = int(df[column].isnull().sum())

        if missing_count > 0:
            mode_values = df[column].mode(dropna=True)

            if not mode_values.empty:
                mode_value = mode_values.iloc[0]
                df[column] = df[column].fillna(mode_value)
                categorical_fill_report[column] = {
                    "method": "Mode",
                    "filled_values": missing_count,
                }
            else:
                categorical_fill_report[column] = {
                    "method": "Not filled",
                    "filled_values": 0,
                }

    if categorical_fill_report:
        print(categorical_fill_report)
    else:
        print("No categorical values needed filling.")

    # 9. TEXT STANDARDIZATION
    print("\nTEXT STANDARDIZATION")
    print("--------------------")

    text_columns = df.select_dtypes(
        include=["object", "category"]
    ).columns

    for column in text_columns:
        df[column] = df[column].apply(
            lambda value: value.strip()
            if isinstance(value, str)
            else value
        )

    if "city" in df.columns:
        df["city"] = df["city"].apply(
            lambda value: value.title()
            if isinstance(value, str)
            else value
        )

    if "product" in df.columns:
        df["product"] = df["product"].apply(
            lambda value: value.title()
            if isinstance(value, str)
            else value
        )

    if "gender" in df.columns:
        gender_mapping = {
            "male": "Male",
            "m": "Male",
            "female": "Female",
            "f": "Female",
        }

        df["gender"] = df["gender"].apply(
            lambda value: gender_mapping.get(
                value.lower(), value.title()
            )
            if isinstance(value, str)
            else value
        )

    if "customer_status" in df.columns:
        status_mapping = {
            "active": "Active",
            "inactive": "Inactive",
        }

        df["customer_status"] = df["customer_status"].apply(
            lambda value: status_mapping.get(
                value.lower(), value.title()
            )
            if isinstance(value, str)
            else value
        )

    if "email" in df.columns:
        df["email"] = df["email"].apply(
            lambda value: value.lower()
            if isinstance(value, str)
            else value
        )

    print("Text standardization completed!")

    # 10. ADVANCED DATA QUALITY VALIDATION
    print("\nADVANCED DATA QUALITY VALIDATION")
    print("--------------------------------")

    advanced_validation_report = {}

    # Email validation.
    print("\nEMAIL VALIDATION")
    print("----------------")

    email_report = {}

    if "email" in df.columns:
        email_pattern = (
            r"^[A-Za-z0-9._%+-]+@"
            r"[A-Za-z0-9.-]+\."
            r"[A-Za-z]{2,}$"
        )

        email_present = df["email"].notna()
        valid_email = df["email"].astype("string").str.fullmatch(
            email_pattern,
            na=False,
        )
        invalid_email = email_present & ~valid_email
        invalid_email_count = int(invalid_email.sum())

        df.loc[invalid_email, "email"] = np.nan

        valid_email_count = int((email_present & valid_email).sum())
        missing_email_count = int(df["email"].isna().sum())

        email_report = {
            "valid_emails": valid_email_count,
            "invalid_emails": invalid_email_count,
            "missing_emails_after_validation": missing_email_count,
            "action": "Invalid email addresses replaced with missing values",
        }

        print("Valid emails:", valid_email_count)
        print("Invalid emails:", invalid_email_count)
        print("Missing emails:", missing_email_count)
    else:
        print("Email column not found.")

    advanced_validation_report["email_validation"] = email_report

    # Customer ID validation.
    print("\nCUSTOMER ID VALIDATION")
    print("----------------------")

    customer_id_report = {}

    if "customer_id" in df.columns:
        missing_id_count = int(df["customer_id"].isna().sum())
        repeated_id_count = int(
            df.loc[
                df["customer_id"].notna(),
                "customer_id",
            ].duplicated().sum()
        )
        unique_id_count = int(df["customer_id"].nunique())

        customer_id_report = {
            "missing_customer_ids": missing_id_count,
            "repeated_customer_id_records": repeated_id_count,
            "unique_customer_ids": unique_id_count,
            "action": (
                "Repeated IDs reported but not removed because customers "
                "may have multiple purchases"
            ),
        }

        print("Missing customer IDs:", missing_id_count)
        print("Repeated customer ID records:", repeated_id_count)
        print("Unique customer IDs:", unique_id_count)
    else:
        print("Customer ID column not found.")

    advanced_validation_report["customer_id_validation"] = customer_id_report

    # Category validation.
    print("\nCATEGORY VALIDATION")
    print("-------------------")

    category_validation_report = {}

    allowed_categories = {
        "gender": ["Male", "Female"],
        "customer_status": ["Active", "Inactive"],
    }

    for column, allowed_values in allowed_categories.items():
        if column not in df.columns:
            continue

        unexpected_mask = (
            df[column].notna()
            & ~df[column].isin(allowed_values)
        )
        unexpected_count = int(unexpected_mask.sum())
        unexpected_values = (
            df.loc[unexpected_mask, column]
            .astype(str)
            .unique()
            .tolist()
        )

        category_validation_report[column] = {
            "allowed_values": allowed_values,
            "unexpected_value_count": unexpected_count,
            "unexpected_values": unexpected_values[:10],
            "action": (
                "Unexpected values reported but not automatically changed"
            ),
        }

        print(f"\n{column}:")
        print("Allowed values:", allowed_values)
        print("Unexpected values:", unexpected_count)
        print("Examples:", unexpected_values[:10])

    advanced_validation_report["category_validation"] = (
        category_validation_report
    )

    # 11. OUTLIER DETECTION USING IQR
    print("\nOUTLIER REPORT")
    print("--------------")

    outlier_report = {}
    numeric_columns = df.select_dtypes(include=["number"]).columns

    for column in numeric_columns:
        q1 = df[column].quantile(0.25)
        q3 = df[column].quantile(0.75)

        if pd.isna(q1) or pd.isna(q3):
            outlier_report[column] = {
                "outlier_count": 0,
                "lower_limit": None,
                "upper_limit": None,
            }
            print(f"{column}: Cannot calculate")
            continue

        iqr = q3 - q1
        lower_limit = q1 - (1.5 * iqr)
        upper_limit = q3 + (1.5 * iqr)

        outliers = df[
            (df[column] < lower_limit)
            | (df[column] > upper_limit)
        ]

        outlier_report[column] = {
            "outlier_count": int(len(outliers)),
            "lower_limit": float(lower_limit),
            "upper_limit": float(upper_limit),
        }

        print(f"{column}: {len(outliers)}")

    print("Outliers are detected but not automatically removed.")

    # 12. DATA QUALITY SCORE
    print("\nDATA QUALITY SCORE")
    print("------------------")

    total_cells = int(df.shape[0] * df.shape[1])
    remaining_missing = int(df.isnull().sum().sum())

    unexpected_category_count = sum(
        item["unexpected_value_count"]
        for item in category_validation_report.values()
    )

    invalid_quality_cells = (
        remaining_missing + unexpected_category_count
    )

    if total_cells > 0:
        data_quality_score = round(
            max(
                0,
                (total_cells - invalid_quality_cells)
                / total_cells
                * 100,
            ),
            2,
        )
    else:
        data_quality_score = 0.0

    data_quality_report = {
        "total_cells": total_cells,
        "remaining_missing_cells": remaining_missing,
        "unexpected_category_values": unexpected_category_count,
        "data_quality_score": data_quality_score,
        "score_formula": (
            "(Total cells - Missing cells - Unexpected category values) "
            "/ Total cells * 100"
        ),
    }

    print("Total cells:", total_cells)
    print("Remaining missing cells:", remaining_missing)
    print("Unexpected category values:", unexpected_category_count)
    print("Data Quality Score:", str(data_quality_score) + "%")

    # 13. SAVE CLEANED DATASET
    cleaned_folder = os.path.join(BASE_DIR, "cleaned_data")
    os.makedirs(cleaned_folder, exist_ok=True)

    filename = os.path.splitext(dataset_name)[0]
    cleaned_filename = filename + "_cleaned.csv"
    cleaned_file_path = os.path.join(cleaned_folder, cleaned_filename)

    df.to_csv(cleaned_file_path, index=False)

    relative_cleaned_path = os.path.relpath(
        cleaned_file_path,
        BASE_DIR,
    )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE datasets
            SET cleaned_file_path = %s
            WHERE dataset_id = %s
            """,
            (relative_cleaned_path, dataset_id),
        )
        conn.commit()
        print("\nCleaned dataset path saved in PostgreSQL!")
    except Exception as error:
        conn.rollback()
        print("Error saving cleaned dataset path:", error)
        raise
    finally:
        conn.close()

    print("\nCLEANED DATASET SAVED")
    print("---------------------")
    print("File path:", cleaned_file_path)

    # 14. GENERATE CLEANING REPORT
    cleaning_report = {
        "dataset_name": dataset_name,
        "original_rows": int(original_rows),
        "final_rows": int(len(df)),
        "original_columns": int(original_columns),
        "duplicates_removed": duplicate_count,
        "missing_values_before": {
            column: int(count)
            for column, count in missing_report.items()
        },
        "invalid_data_report": invalid_report,
        "date_standardization_report": date_cleaning_report,
        "numerical_missing_values_filled": numeric_fill_report,
        "categorical_missing_values_filled": categorical_fill_report,
        "advanced_validation_report": advanced_validation_report,
        "outlier_report": outlier_report,
        "data_quality_report": data_quality_report,
        "remaining_missing_values": remaining_missing,
        "cleaned_file_path": os.path.abspath(cleaned_file_path),
        "cleaning_status": "Completed",
    }

    # 15. SAVE REPORT IN POSTGRESQL
    conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO analysis_history
            (dataset_id, analysis_type, analysis_result)
            VALUES (%s, %s, %s)
            """,
            (
                dataset_id,
                "Advanced Data Quality Report",
                json.dumps(cleaning_report),
            ),
        )
        conn.commit()
        print("\nCleaning report saved in PostgreSQL!")
    except Exception as error:
        conn.rollback()
        print("Error saving cleaning report:", error)
    finally:
        conn.close()

    # 16. FINAL SUMMARY
    print("\n=============================================")
    print("       DATA CLEANING COMPLETED")
    print("=============================================")

    print("Original Rows:", original_rows)
    print("Final Rows:", len(df))
    print("Duplicates Removed:", duplicate_count)
    print("Remaining Missing Values:", remaining_missing)
    print("Invalid Data Report:", invalid_report)
    print("Date Standardization Report:", date_cleaning_report)
    print("Advanced Validation Report:", advanced_validation_report)
    print("DATA QUALITY SCORE:", str(data_quality_score) + "%")
    print("Cleaned File:", cleaned_file_path)
    print("=============================================")

    return cleaning_report


def main():
    try:
        dataset_id = int(input("\nEnter Dataset ID: ").strip())
        clean_dataset(dataset_id)
    except ValueError as error:
        print("Cleaning error:", error)


if __name__ == "__main__":
    main()