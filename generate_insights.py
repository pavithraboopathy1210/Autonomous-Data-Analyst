
import pandas as pd
import json
from pathlib import Path

from database.database import get_connection


# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent


# --------------------------------------------------
# 1. LOAD DATASET FROM POSTGRESQL
# --------------------------------------------------

def load_dataset(dataset_id):

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT dataset_name, file_path, cleaned_file_path
            FROM datasets
            WHERE dataset_id = %s
            """,
            (dataset_id,)
        )

        result = cursor.fetchone()
        cursor.close()

        if result is None:
            raise ValueError("Dataset ID not found!")

        dataset_name, original_file_path, cleaned_file_path = result

        # Prefer the cleaned dataset when it is available.
        if cleaned_file_path:
            file_path = Path(cleaned_file_path)
            dataset_source = "cleaned"
        else:
            file_path = Path(original_file_path)
            dataset_source = "original"

        if not file_path.is_absolute():
            file_path = BASE_DIR / file_path

        if not file_path.exists():
            raise FileNotFoundError(
                f"Dataset file not found: {file_path}"
            )

        if file_path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)

        elif file_path.suffix.lower() in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path)

        else:
            raise ValueError("Unsupported file format!")

        print(f"\nDataset loaded: {dataset_name}")
        print(f"Dataset source: {dataset_source}")
        print(f"File path: {file_path}")

        return df, dataset_name

    finally:
        connection.close()


# --------------------------------------------------
# 2. GENERATE AUTOMATED INSIGHTS
# --------------------------------------------------

def generate_insights(df):

    insights = []

    # Remove unnecessary spaces from column names
    df.columns = df.columns.astype(str).str.strip()

    total_rows = len(df)
    total_columns = len(df.columns)

    insights.append(
        f"The dataset contains {total_rows} rows "
        f"and {total_columns} columns."
    )

    # --------------------------------------------------
    # IDENTIFY NUMERIC COLUMNS
    # --------------------------------------------------

    numeric_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    # Identify monetary column
    amount_column = None

    for column in ["sales_amount", "purchase_amount"]:
        if column in df.columns:
            amount_column = column
            break

    # Convert monetary column to numeric if necessary
    if amount_column:

        df[amount_column] = pd.to_numeric(
            df[amount_column],
            errors="coerce"
        )

        valid_amounts = df[amount_column].dropna()

        if not valid_amounts.empty:

            total_amount = valid_amounts.sum()
            average_amount = valid_amounts.mean()
            highest_amount = valid_amounts.max()

            insights.append(
                f"Total {amount_column.replace('_', ' ')} "
                f"is {total_amount:.2f}."
            )

            insights.append(
                f"Average {amount_column.replace('_', ' ')} "
                f"is {average_amount:.2f}."
            )

            insights.append(
                f"Highest transaction amount is "
                f"{highest_amount:.2f}."
            )

    # --------------------------------------------------
    # 3. FIND TOP-PERFORMING CATEGORIES
    # --------------------------------------------------

    if amount_column:

        category_columns = [
            "product",
            "category",
            "city"
        ]

        for column in category_columns:

            if column not in df.columns:
                continue

            grouped_data = (
                df.dropna(subset=[column, amount_column])
                .groupby(column)[amount_column]
                .sum()
                .sort_values(ascending=False)
            )

            if not grouped_data.empty:

                top_name = grouped_data.index[0]
                top_value = grouped_data.iloc[0]

                insights.append(
                    f"{top_name} has the highest "
                    f"total {amount_column.replace('_', ' ')} "
                    f"among the {column} values, "
                    f"with {top_value:.2f}."
                )

    # --------------------------------------------------
    # 4. NUMERIC COLUMN ANALYSIS
    # --------------------------------------------------

    for column in numeric_columns:

        if column == amount_column:
            continue

        values = pd.to_numeric(
            df[column],
            errors="coerce"
        ).dropna()

        if values.empty:
            continue

        insights.append(
            f"Average {column.replace('_', ' ')} "
            f"is {values.mean():.2f}."
        )

    # --------------------------------------------------
    # 5. MONTHLY TREND ANALYSIS
    # --------------------------------------------------

    date_columns = [
        column for column in df.columns
        if "date" in column.lower()
    ]

    if date_columns:

        date_column = date_columns[0]

        dates = pd.to_datetime(
            df[date_column],
            errors="coerce",
            format="mixed"
        )

        valid_dates = dates.notna()

        if valid_dates.any():

            date_data = df.loc[valid_dates].copy()

            date_data["_month"] = dates[valid_dates].dt.to_period("M")

            if amount_column:

                monthly_data = (
                    date_data.groupby("_month")[amount_column]
                    .sum()
                    .sort_index()
                )

                if not monthly_data.empty:

                    highest_month = monthly_data.idxmax()
                    highest_month_value = monthly_data.max()

                    insights.append(
                        f"The highest sales month is "
                        f"{highest_month}, with "
                        f"{highest_month_value:.2f}."
                    )

            else:

                monthly_data = (
                    date_data.groupby("_month")
                    .size()
                    .sort_index()
                )

                if not monthly_data.empty:

                    highest_month = monthly_data.idxmax()

                    insights.append(
                        f"The highest number of records "
                        f"occurred in {highest_month}, "
                        f"with {monthly_data.max()} records."
                    )

    # --------------------------------------------------
    # 6. MISSING VALUE OBSERVATION
    # --------------------------------------------------

    missing_values = int(df.isnull().sum().sum())

    insights.append(
        f"The dataset contains {missing_values} "
        f"missing values."
    )

    return insights


# --------------------------------------------------
# 7. SAVE INSIGHTS IN POSTGRESQL
# --------------------------------------------------

def save_insights(dataset_id, insights):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        result = {
            "total_insights": len(insights),
            "insights": insights
        }

        cursor.execute(
            """
            INSERT INTO analysis_history
            (dataset_id, analysis_type, analysis_result)
            VALUES (%s, %s, %s::jsonb)
            """,
            (
                dataset_id,
                "Automated Data Insights",
                json.dumps(result)
            )
        )

        connection.commit()
        cursor.close()

        print("\nInsights saved successfully in PostgreSQL!")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# --------------------------------------------------
# 8. MAIN PROGRAM
# --------------------------------------------------

def main():

    print("=" * 55)
    print("       AUTONOMOUS DATA ANALYST")
    print("          AUTOMATED INSIGHTS")
    print("=" * 55)

    try:

        dataset_id = int(
            input("\nEnter Dataset ID: ")
        )

        # Load dataset
        df, dataset_name = load_dataset(dataset_id)

        # Generate insights
        insights = generate_insights(df)

        # Display insights
        print("\n" + "=" * 55)
        print("             GENERATED INSIGHTS")
        print("=" * 55)

        for number, insight in enumerate(insights, start=1):

            print(f"\n{number}. {insight}")

        # Save results
        save_insights(dataset_id, insights)

        print("\n" + "=" * 55)
        print("       AUTOMATED INSIGHTS COMPLETED!")
        print("=" * 55)

    except ValueError as error:

        print(f"\nInput error: {error}")

    except Exception as error:

        print(f"\nError: {error}")


if __name__ == "__main__":
    main()
