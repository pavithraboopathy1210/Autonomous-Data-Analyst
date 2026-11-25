
import os
import pandas as pd
import matplotlib.pyplot as plt

from database.database import get_connection


# ==================================================
# CONFIGURATION
# ==================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VISUALIZATION_BASE_FOLDER = os.path.join(BASE_DIR, "visualizations")
OUTPUT_FOLDER = VISUALIZATION_BASE_FOLDER

os.makedirs(VISUALIZATION_BASE_FOLDER, exist_ok=True)

CHART_FILES = [
    "bar_chart.png",
    "histogram.png",
    "line_chart.png",
    "scatter_plot.png",
    "correlation_heatmap.png",
    "revenue_by_city.png",
    "revenue_by_category.png"
]


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def set_output_folder(dataset_id):
    global OUTPUT_FOLDER

    OUTPUT_FOLDER = os.path.join(
        VISUALIZATION_BASE_FOLDER,
        f"dataset_{dataset_id}"
    )

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def find_column(df, candidates):
    column_lookup = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for candidate in candidates:
        if candidate.lower() in column_lookup:
            return column_lookup[candidate.lower()]

    return None


def get_numeric_columns(df):
    numeric_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    excluded_words = [
        "id",
        "order_id",
        "customer_id",
        "serial",
        "index"
    ]

    return [
        column for column in numeric_columns
        if str(column).strip().lower() not in excluded_words
    ]


def get_sales_column(df):
    return find_column(
        df,
        [
            "sales_amount",
            "revenue",
            "total_sales",
            "total_amount",
            "amount",
            "purchase_amount"
        ]
    )


# ==================================================
# LOAD DATASET
# ==================================================

def load_dataset(dataset_id):
    connection = None

    try:
        connection = get_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT dataset_name, file_path, cleaned_file_path
                FROM datasets
                WHERE dataset_id = %s;
                """,
                (dataset_id,)
            )

            dataset = cursor.fetchone()

        if not dataset:
            print("Dataset not found!")
            return None

        dataset_name, original_file_path, cleaned_file_path = dataset

        if cleaned_file_path:
            selected_file_path = cleaned_file_path
            dataset_source = "cleaned"
        else:
            selected_file_path = original_file_path
            dataset_source = "original (not cleaned yet)"

        if os.path.isabs(selected_file_path):
            full_path = selected_file_path
        else:
            full_path = os.path.join(BASE_DIR, selected_file_path)

        if not os.path.exists(full_path) and not cleaned_file_path:
            full_path = os.path.join(
                BASE_DIR,
                "uploads",
                os.path.basename(selected_file_path)
            )

        if not os.path.exists(full_path):
            print("Dataset file not found:", full_path)

            if cleaned_file_path:
                print(
                    "The cleaned path exists in PostgreSQL, "
                    "but the file was not found."
                )

            return None

        extension = os.path.splitext(full_path)[1].lower()

        if extension == ".csv":
            df = pd.read_csv(full_path)

        elif extension in [".xlsx", ".xls"]:
            df = pd.read_excel(full_path)

        else:
            print("Unsupported file format!")
            return None

        print("\nDataset loaded:", dataset_name)
        print("Dataset source:", dataset_source)
        print("File path:", full_path)

        return df

    except Exception as error:
        print("Error loading dataset:", error)
        return None

    finally:
        if connection:
            connection.close()


# ==================================================
# IDENTIFY COLUMN TYPES
# ==================================================

def identify_columns(df):
    numeric_columns = get_numeric_columns(df)

    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.tolist()

    date_columns = []

    for column in categorical_columns:
        converted = pd.to_datetime(
            df[column],
            errors="coerce"
        )

        if len(df) > 0 and converted.notna().mean() >= 0.8:
            date_columns.append(column)

    categorical_columns = [
        column for column in categorical_columns
        if column not in date_columns
    ]

    return numeric_columns, categorical_columns, date_columns


# ==================================================
# REMOVE OLD CHARTS FOR THIS DATASET ONLY
# ==================================================

def clear_old_charts():
    for filename in CHART_FILES:
        path = os.path.join(OUTPUT_FOLDER, filename)

        if os.path.exists(path):
            os.remove(path)


# ==================================================
# BAR CHART
# ==================================================

def create_bar_chart(df, categorical_columns, numeric_columns):
    sales_column = get_sales_column(df)

    if not sales_column:
        print("Bar chart skipped: no sales/revenue column found.")
        return

    category_column = find_column(
        df,
        ["product", "category", "city", "payment_method"]
    )

    if not category_column:
        suitable_categories = [
            column for column in categorical_columns
            if df[column].nunique(dropna=True) <= 50
        ]

        if suitable_categories:
            category_column = suitable_categories[0]

    if not category_column:
        print("Bar chart skipped: no suitable category column.")
        return

    chart_df = df[[category_column, sales_column]].copy()

    chart_df[sales_column] = pd.to_numeric(
        chart_df[sales_column],
        errors="coerce"
    )

    chart_df = chart_df.dropna(subset=[sales_column])

    chart_data = (
        chart_df.groupby(category_column, dropna=False)[sales_column]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    if chart_data.empty:
        print("Bar chart skipped: no valid data.")
        return

    plt.figure(figsize=(11, 6))
    chart_data.plot(kind="bar")

    plt.title(
        f"Top 10 {category_column.title()} by Revenue",
        fontsize=14
    )
    plt.xlabel(category_column.title())
    plt.ylabel("Total Revenue")
    plt.xticks(rotation=40, ha="right")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()

    path = os.path.join(OUTPUT_FOLDER, "bar_chart.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    print("Revenue bar chart saved:", path)


# ==================================================
# HISTOGRAM
# ==================================================

def create_histogram(df, numeric_columns):
    sales_column = get_sales_column(df)

    if sales_column:
        column = sales_column
    elif numeric_columns:
        column = numeric_columns[0]
    else:
        print("Histogram skipped: no numeric columns.")
        return

    values = pd.to_numeric(
        df[column],
        errors="coerce"
    ).dropna()

    if values.empty:
        print("Histogram skipped: no valid numeric values.")
        return

    plt.figure(figsize=(9, 5))

    plt.hist(
        values,
        bins=20,
        edgecolor="black"
    )

    plt.title(f"Distribution of {column}", fontsize=14)
    plt.xlabel(column)
    plt.ylabel("Frequency")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()

    path = os.path.join(OUTPUT_FOLDER, "histogram.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    print("Histogram saved:", path)


# ==================================================
# LINE CHART
# ==================================================

def create_line_chart(df, date_columns, numeric_columns):
    sales_column = get_sales_column(df)

    if not date_columns:
        print("Line chart skipped: no date column found.")
        return

    if not sales_column:
        if numeric_columns:
            sales_column = numeric_columns[0]
        else:
            print("Line chart skipped: no numeric column found.")
            return

    date_column = find_column(
        df,
        ["order_date", "transaction_date", "purchase_date", "date"]
    )

    if not date_column:
        date_column = date_columns[0]

    chart_df = df[[date_column, sales_column]].copy()

    chart_df[date_column] = pd.to_datetime(
        chart_df[date_column],
        errors="coerce"
    )

    chart_df[sales_column] = pd.to_numeric(
        chart_df[sales_column],
        errors="coerce"
    )

    chart_df = chart_df.dropna()

    if chart_df.empty:
        print("Line chart skipped: no valid date records.")
        return

    chart_data = (
        chart_df.groupby(
            chart_df[date_column].dt.to_period("M")
        )[sales_column]
        .sum()
        .sort_index()
    )

    if chart_data.empty:
        print("Line chart skipped: no monthly data.")
        return

    plt.figure(figsize=(11, 5))

    plt.plot(
        chart_data.index.astype(str),
        chart_data.values,
        marker="o",
        linewidth=2
    )

    plt.title("Monthly Revenue Trend", fontsize=14)
    plt.xlabel("Month")
    plt.ylabel("Total Revenue")
    plt.xticks(rotation=45)
    plt.grid(alpha=0.25)
    plt.tight_layout()

    path = os.path.join(OUTPUT_FOLDER, "line_chart.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    print("Monthly revenue chart saved:", path)


# ==================================================
# SCATTER PLOT
# ==================================================

def create_scatter_plot(df, numeric_columns):
    quantity_column = find_column(
        df,
        ["quantity", "units_sold"]
    )

    sales_column = get_sales_column(df)

    if quantity_column and sales_column:
        x_column = quantity_column
        y_column = sales_column

    elif len(numeric_columns) >= 2:
        x_column = numeric_columns[0]
        y_column = numeric_columns[1]

    else:
        print(
            "Scatter plot skipped: "
            "two suitable numeric columns required."
        )
        return

    chart_df = df[[x_column, y_column]].copy()

    chart_df[x_column] = pd.to_numeric(
        chart_df[x_column],
        errors="coerce"
    )

    chart_df[y_column] = pd.to_numeric(
        chart_df[y_column],
        errors="coerce"
    )

    chart_df = chart_df.dropna()

    if chart_df.empty:
        print("Scatter plot skipped: no valid records.")
        return

    plt.figure(figsize=(9, 5))

    plt.scatter(
        chart_df[x_column],
        chart_df[y_column],
        alpha=0.6
    )

    plt.title(f"{y_column} vs {x_column}", fontsize=14)
    plt.xlabel(x_column)
    plt.ylabel(y_column)
    plt.grid(alpha=0.25)
    plt.tight_layout()

    path = os.path.join(OUTPUT_FOLDER, "scatter_plot.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    print("Scatter plot saved:", path)


# ==================================================
# CORRELATION HEATMAP
# ==================================================

def create_correlation_heatmap(df, numeric_columns):
    if len(numeric_columns) < 2:
        print("Heatmap skipped: two numeric columns required.")
        return

    correlation = df[numeric_columns].corr()

    if correlation.empty:
        print("Heatmap skipped: correlation could not be calculated.")
        return

    plt.figure(figsize=(10, 7))

    image = plt.imshow(
        correlation,
        cmap="coolwarm",
        vmin=-1,
        vmax=1
    )

    plt.colorbar(image, label="Correlation")

    plt.xticks(
        range(len(correlation.columns)),
        correlation.columns,
        rotation=45,
        ha="right"
    )

    plt.yticks(
        range(len(correlation.columns)),
        correlation.columns
    )

    for i in range(len(correlation.columns)):
        for j in range(len(correlation.columns)):
            value = correlation.iloc[i, j]

            if pd.notna(value):
                plt.text(
                    j,
                    i,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    fontsize=8
                )

    plt.title("Numerical Feature Correlation", fontsize=14)
    plt.tight_layout()

    path = os.path.join(
        OUTPUT_FOLDER,
        "correlation_heatmap.png"
    )

    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    print("Correlation heatmap saved:", path)


# ==================================================
# CITY / CATEGORY REVENUE CHART
# ==================================================

def create_location_or_category_chart(df):
    sales_column = get_sales_column(df)

    if not sales_column:
        print("City/category chart skipped: no revenue column found.")
        return

    city_column = find_column(
        df,
        ["city", "location", "town"]
    )

    category_column = find_column(
        df,
        ["category", "product"]
    )

    if city_column:
        group_column = city_column
        filename = "revenue_by_city.png"
        title = "Revenue by City"

    elif category_column:
        group_column = category_column
        filename = "revenue_by_category.png"
        title = f"Revenue by {category_column.title()}"

    else:
        print("City/category chart skipped: no suitable column found.")
        return

    chart_df = df[[group_column, sales_column]].copy()

    chart_df[sales_column] = pd.to_numeric(
        chart_df[sales_column],
        errors="coerce"
    )

    chart_df = chart_df.dropna(subset=[sales_column])

    chart_data = (
        chart_df.groupby(group_column, dropna=False)[sales_column]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    if chart_data.empty:
        print("City/category chart skipped: no valid data.")
        return

    plt.figure(figsize=(10, 6))
    chart_data.sort_values().plot(kind="barh")

    plt.title(title, fontsize=14)
    plt.xlabel("Total Revenue")
    plt.ylabel(group_column.title())
    plt.grid(axis="x", alpha=0.25)
    plt.tight_layout()

    path = os.path.join(OUTPUT_FOLDER, filename)
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()

    print("Additional revenue chart saved:", path)


# ==================================================
# MAIN FUNCTION
# ==================================================

def main():
    print("\nAUTONOMOUS DATA ANALYST")
    print("----------------------")
    print("DATA VISUALIZATION MODULE")

    dataset_id = input("\nEnter Dataset ID: ").strip()

    if not dataset_id.isdigit():
        print("Please enter a valid dataset ID.")
        return

    dataset_id = int(dataset_id)

    df = load_dataset(dataset_id)

    if df is None:
        return

    if df.empty:
        print("Dataset is empty. Cannot generate visualizations.")
        return

    # Create a separate output folder for this dataset.
    set_output_folder(dataset_id)

    numeric, categorical, dates = identify_columns(df)

    print("\nIdentified Columns")
    print("------------------")
    print("Numeric:", numeric)
    print("Categorical:", categorical)
    print("Date:", dates)

    print("\nRemoving old charts for this dataset...")
    clear_old_charts()

    print("\nGenerating visualizations...\n")

    create_bar_chart(df, categorical, numeric)
    create_histogram(df, numeric)
    create_line_chart(df, dates, numeric)
    create_scatter_plot(df, numeric)
    create_correlation_heatmap(df, numeric)
    create_location_or_category_chart(df)

    generated_count = sum(
        os.path.exists(os.path.join(OUTPUT_FOLDER, filename))
        for filename in CHART_FILES
    )

    print("\nVisualization process completed!")
    print("Charts generated:", generated_count)
    print("Charts are stored in:", OUTPUT_FOLDER)


if __name__ == "__main__":
    main()
