
import os
import json
import html
import pandas as pd

from pathlib import Path
from datetime import datetime

from database.database import get_connection


# ==================================================
# PROJECT PATHS
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_FOLDER = BASE_DIR / "uploads"
REPORT_FOLDER = BASE_DIR / "reports"
VISUALIZATION_FOLDER = BASE_DIR / "visualizations"

REPORT_FOLDER.mkdir(exist_ok=True)


# ==================================================
# DATABASE: GET DATASET
# ==================================================

def get_dataset(dataset_id):

    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT dataset_id, dataset_name, file_path,
                   cleaned_file_path, file_type,
                   total_rows, total_columns, uploaded_at
            FROM datasets
            WHERE dataset_id = %s
            """,
            (dataset_id,)
        )

        return cursor.fetchone()

    finally:
        if cursor:
            cursor.close()

        connection.close()


# ==================================================
# LOAD DATASET
# ==================================================

def load_dataset(file_path):

    path = Path(file_path)

    if not path.is_absolute():
        path = BASE_DIR / path

    if not path.exists():
        path = UPLOAD_FOLDER / Path(file_path).name

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset file not found: {file_path}"
        )

    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)

    elif path.suffix.lower() in [".xlsx", ".xls"]:
        return pd.read_excel(path)

    raise ValueError("Unsupported file format")


# ==================================================
# DATABASE: GET ANALYSIS HISTORY
# ==================================================

def get_analysis_history(dataset_id):

    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT analysis_type, analysis_result, created_at
            FROM analysis_history
            WHERE dataset_id = %s
            ORDER BY created_at DESC
            """,
            (dataset_id,)
        )

        return cursor.fetchall()

    finally:
        if cursor:
            cursor.close()

        connection.close()


# ==================================================
# FORMAT VALUES
# ==================================================

def format_value(value):

    if value is None:
        return "Not available"

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, int):
        return f"{value:,}"

    if isinstance(value, float):

        if pd.isna(value):
            return "Not available"

        return f"{value:,.2f}"

    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%d-%m-%Y %H:%M:%S")

    return str(value)


# ==================================================
# HTML TABLE GENERATOR
# ==================================================

def create_table(data):

    if data is None or data.empty:
        return "<p>No information available.</p>"

    display_data = data.copy()

    for column in display_data.columns:

        if pd.api.types.is_numeric_dtype(display_data[column]):
            display_data[column] = display_data[column].apply(
                format_value
            )

    return display_data.to_html(
        classes="data-table",
        border=0,
        escape=True,
        index=True
    )


# ==================================================
# CONVERT DATABASE JSON RESULT
# ==================================================

def parse_analysis_result(result):

    if isinstance(result, str):

        try:
            return json.loads(result)

        except (json.JSONDecodeError, TypeError):
            return result

    return result


# ==================================================
# RENDER ANALYSIS HISTORY VALUES
# ==================================================

def render_history_value(value, depth=0):

    if depth > 5:
        return "<p>Additional nested information omitted.</p>"

    if isinstance(value, dict):

        if not value:
            return "<p>No details available.</p>"

        rows = ""

        for key, item in value.items():

            rows += f"""
            <tr>
                <td class="history-key">
                    {html.escape(str(key).replace("_", " ").title())}
                </td>
                <td>
                    {render_history_value(item, depth + 1)}
                </td>
            </tr>
            """

        return f"""
        <table class="history-table">
            <tbody>
                {rows}
            </tbody>
        </table>
        """

    if isinstance(value, list):

        if not value:
            return "<p>No records available.</p>"

        if all(isinstance(item, dict) for item in value):

            rendered_items = ""

            for index, item in enumerate(value, start=1):

                rendered_items += f"""
                <div class="history-list-item">
                    <h4>Record {index}</h4>
                    {render_history_value(item, depth + 1)}
                </div>
                """

            return rendered_items

        list_items = ""

        for item in value[:100]:

            list_items += f"""
            <li>
                {render_history_value(item, depth + 1)}
            </li>
            """

        if len(value) > 100:
            list_items += """
            <li>Additional items omitted from this report.</li>
            """

        return f"""
        <ul class="history-list">
            {list_items}
        </ul>
        """

    return html.escape(format_value(value))


# ==================================================
# GET AUTOMATED INSIGHTS
# ==================================================

def extract_insights(history):

    insights = []
    seen_insights = set()

    for analysis_type, result, created_at in history:

        if "insight" not in str(analysis_type).lower():
            continue

        result = parse_analysis_result(result)

        if isinstance(result, dict):

            saved_insights = result.get("insights", [])

            if isinstance(saved_insights, list):

                for insight in saved_insights:

                    insight_key = str(insight).strip()

                    if insight_key and insight_key not in seen_insights:

                        insights.append(insight)
                        seen_insights.add(insight_key)

    return insights


# ==================================================
# GET DATASET-SPECIFIC VISUALIZATIONS
# ==================================================

def get_visualizations(dataset_id):

    dataset_visualization_folder = (
        VISUALIZATION_FOLDER / f"dataset_{dataset_id}"
    )

    if not dataset_visualization_folder.exists():
        return []

    preferred_order = [
        "bar_chart.png",
        "revenue_by_city.png",
        "revenue_by_category.png",
        "line_chart.png",
        "histogram.png",
        "scatter_plot.png",
        "correlation_heatmap.png"
    ]

    images = []

    for filename in preferred_order:

        image_path = dataset_visualization_folder / filename

        if image_path.exists():
            images.append(image_path)

    for image_path in sorted(
        dataset_visualization_folder.glob("*.png")
    ):

        if image_path not in images:
            images.append(image_path)

    return images


# ==================================================
# GENERATE VISUALIZATION HTML
# ==================================================

def create_visualization_html(images):

    if not images:
        return """
        <p>
            No visualization images found for this dataset.
            Run visualize_dataset.py using this Dataset ID
            to generate charts.
        </p>
        """

    visualization_html = ""

    for image_path in images:

        relative_path = os.path.relpath(
            image_path,
            REPORT_FOLDER
        ).replace(os.sep, "/")

        image_name = html.escape(
            image_path.stem.replace("_", " ").title()
        )

        visualization_html += f"""
        <div class="chart-card">

            <h3>{image_name}</h3>

            <img
                src="{html.escape(relative_path, quote=True)}"
                alt="{image_name}"
            >

        </div>
        """

    return visualization_html


# ==================================================
# GENERATE INSIGHTS HTML
# ==================================================

def create_insights_html(insights):

    if not insights:
        return "<p>No automated insights found.</p>"

    result = '<ul class="insight-list">'

    for insight in insights:

        result += f"""
        <li>{html.escape(str(insight))}</li>
        """

    result += "</ul>"

    return result


# ==================================================
# GENERATE HISTORY HTML
# ==================================================

def create_history_html(history):

    if not history:
        return "<p>No previous analysis records found.</p>"

    history_html = ""

    for analysis_type, result, created_at in history:

        result = parse_analysis_result(result)

        details_html = render_history_value(result)

        history_html += f"""
        <div class="history-card">

            <h3>
                {html.escape(str(analysis_type).replace("_", " ").title())}
            </h3>

            <p class="history-date">
                Created: {html.escape(format_value(created_at))}
            </p>

            <div class="history-content">
                {details_html}
            </div>

        </div>
        """

    return history_html


# ==================================================
# MAIN REPORT GENERATOR
# ==================================================

def generate_report(dataset_id):

    print("\nGenerating professional dataset report...")

    # --------------------------------------------------
    # GET DATASET INFORMATION
    # --------------------------------------------------

    dataset = get_dataset(dataset_id)

    if dataset is None:
        print("Dataset ID not found!")
        return

    (
        dataset_id,
        dataset_name,
        original_file_path,
        cleaned_file_path,
        file_type,
        stored_rows,
        stored_columns,
        uploaded_at
    ) = dataset

    # --------------------------------------------------
    # SELECT CLEANED DATASET
    # --------------------------------------------------

    if cleaned_file_path:

        file_path = cleaned_file_path
        dataset_source = "Cleaned Dataset"

    else:

        file_path = original_file_path
        dataset_source = "Original Dataset"

    # --------------------------------------------------
    # LOAD DATASET
    # --------------------------------------------------

    df = load_dataset(file_path)

    print(f"\nDataset loaded: {dataset_name}")
    print(f"Dataset source: {dataset_source}")
    print(f"File path: {file_path}")
    print(f"Rows loaded: {len(df)}")
    print(f"Columns loaded: {len(df.columns)}")

    if df.empty:
        print("Dataset is empty. Cannot generate report.")
        return

    # --------------------------------------------------
    # GET ANALYSIS HISTORY
    # --------------------------------------------------

    history = get_analysis_history(dataset_id)

    # --------------------------------------------------
    # DATASET ANALYSIS
    # --------------------------------------------------

    total_rows = len(df)
    total_columns = len(df.columns)

    missing_values = df.isnull().sum()
    total_missing = int(missing_values.sum())

    duplicate_count = int(df.duplicated().sum())

    numerical_columns = df.select_dtypes(
        include="number"
    )

    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    )

    numerical_summary = numerical_columns.describe().round(2)

    # --------------------------------------------------
    # CATEGORICAL SUMMARY
    # --------------------------------------------------

    categorical_summary = {}

    for column in categorical_columns.columns:

        unique_count = df[column].nunique(dropna=True)

        if unique_count <= 20:

            categorical_summary[column] = (
                df[column]
                .value_counts(dropna=False)
                .head(5)
                .to_dict()
            )

    # --------------------------------------------------
    # KEY METRICS
    # --------------------------------------------------

    total_revenue = None
    average_discount = None

    sales_column = None

    for candidate in [
        "sales_amount",
        "revenue",
        "total_sales",
        "total_amount",
        "amount",
        "purchase_amount"
    ]:

        for column in df.columns:

            if str(column).strip().lower() == candidate:
                sales_column = column
                break

        if sales_column:
            break

    if sales_column:

        sales = pd.to_numeric(
            df[sales_column],
            errors="coerce"
        )

        total_revenue = sales.sum()

    discount_column = next(
        (
            column for column in df.columns
            if str(column).strip().lower() == "discount_percent"
        ),
        None
    )

    if discount_column:

        discounts = pd.to_numeric(
            df[discount_column],
            errors="coerce"
        )

        average_discount = discounts.mean()

    # --------------------------------------------------
    # MISSING VALUE TABLE
    # --------------------------------------------------

    missing_df = missing_values[
        missing_values > 0
    ].reset_index()

    missing_df.columns = [
        "Column",
        "Missing Values"
    ]

    if missing_df.empty:

        missing_html = """
        <p class="success-message">
            No missing values found in the dataset.
        </p>
        """

    else:

        missing_html = create_table(missing_df)

    # --------------------------------------------------
    # NUMERICAL SUMMARY
    # --------------------------------------------------

    if numerical_summary.empty:

        numerical_html = "<p>No numerical columns found.</p>"

    else:

        numerical_html = create_table(numerical_summary)

    # --------------------------------------------------
    # CATEGORICAL SUMMARY
    # --------------------------------------------------

    categorical_html = ""

    for column, values in categorical_summary.items():

        summary_df = pd.DataFrame(
            list(values.items()),
            columns=["Value", "Count"]
        )

        categorical_html += f"""
        <div class="category-section">

            <h3>{html.escape(str(column).replace("_", " ").title())}</h3>

            {create_table(summary_df)}

        </div>
        """

    if not categorical_html:
        categorical_html = "<p>No suitable categorical columns found.</p>"

    # --------------------------------------------------
    # COLUMN INFORMATION
    # --------------------------------------------------

    column_df = pd.DataFrame({
        "Column Name": df.columns,
        "Data Type": df.dtypes.astype(str).values,
        "Missing Values": missing_values.values,
        "Unique Values": [
            df[column].nunique(dropna=True)
            for column in df.columns
        ]
    })

    column_html = create_table(column_df)

    # --------------------------------------------------
    # AUTOMATED INSIGHTS
    # --------------------------------------------------

    insights = extract_insights(history)

    insights_html = create_insights_html(insights)

    # --------------------------------------------------
    # DATASET-SPECIFIC VISUALIZATIONS
    # --------------------------------------------------

    images = get_visualizations(dataset_id)

    visualization_html = create_visualization_html(images)

    # --------------------------------------------------
    # PREVIOUS ANALYSIS HISTORY
    # --------------------------------------------------

    history_html = create_history_html(history)

    # --------------------------------------------------
    # KEY METRICS HTML
    # --------------------------------------------------

    revenue_html = ""

    if total_revenue is not None:

        revenue_html = f"""
        <div class="metric-card">

            <span>Total Revenue</span>

            <h2>{format_value(total_revenue)}</h2>

        </div>
        """

    discount_html = ""

    if average_discount is not None:

        discount_html = f"""
        <div class="metric-card">

            <span>Average Discount</span>

            <h2>{average_discount:.2f}%</h2>

        </div>
        """

    # --------------------------------------------------
    # CREATE COMPLETE HTML REPORT
    # --------------------------------------------------

    report_html = f"""
<!DOCTYPE html>

<html>

<head>

    <meta charset="UTF-8">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Autonomous Data Analyst Report</title>

    <style>

        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: Arial, sans-serif;
            background: #f1f4f8;
            margin: 0;
            padding: 25px;
            color: #263238;
            line-height: 1.5;
        }}

        .container {{
            max-width: 1150px;
            margin: auto;
            background: white;
            padding: 35px;
            border-radius: 12px;
        }}

        .header {{
            text-align: center;
            padding: 25px;
            background: #17365d;
            color: white;
            border-radius: 10px;
        }}

        .header h1 {{
            margin: 0 0 8px;
        }}

        .header p {{
            color: #dce6f1;
            margin: 0;
        }}

        .report-info {{
            margin-top: 25px;
            padding: 20px;
            background: #f5f8fb;
            border-radius: 8px;
            border: 1px solid #e1e7ee;
        }}

        .report-info p {{
            margin: 9px 0;
        }}

        .section {{
            margin-top: 38px;
        }}

        .section h2 {{
            color: #17365d;
            border-bottom: 2px solid #dce3eb;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}

        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}

        .metric-card {{
            background: #eaf2f8;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            overflow-wrap: anywhere;
        }}

        .metric-card span {{
            color: #526779;
            font-weight: bold;
        }}

        .metric-card h2 {{
            color: #17365d;
            border: none;
            margin: 10px 0 0;
            padding: 0;
            font-size: 23px;
        }}

        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 13px;
        }}

        .data-table th,
        .data-table td {{
            padding: 11px;
            border: 1px solid #dce3eb;
            text-align: left;
            overflow-wrap: anywhere;
        }}

        .data-table th {{
            background: #24527a;
            color: white;
        }}

        .data-table tr:nth-child(even) {{
            background: #f4f7fa;
        }}

        .insight-list {{
            padding-left: 25px;
        }}

        .insight-list li {{
            padding: 11px;
            margin-bottom: 9px;
            background: #f4f7fa;
            border-left: 4px solid #24527a;
            line-height: 1.6;
        }}

        .success-message {{
            padding: 15px;
            background: #eaf6ed;
            color: #246b38;
            border-radius: 6px;
        }}

        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 20px;
        }}

        .chart-card {{
            padding: 15px;
            border: 1px solid #dce3eb;
            border-radius: 8px;
            text-align: center;
            background: white;
            min-width: 0;
        }}

        .chart-card h3 {{
            color: #24527a;
            font-size: 16px;
        }}

        .chart-card img {{
            width: 100%;
            height: auto;
            object-fit: contain;
        }}

        .history-card {{
            padding: 20px;
            margin: 18px 0;
            background: #f5f8fb;
            border-left: 4px solid #24527a;
            border-radius: 6px;
        }}

        .history-card h3 {{
            color: #17365d;
            margin-top: 0;
        }}

        .history-date {{
            color: #718096;
            font-size: 13px;
        }}

        .history-content {{
            margin-top: 15px;
            overflow-wrap: anywhere;
        }}

        .history-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            background: white;
        }}

        .history-table td {{
            padding: 10px;
            border: 1px solid #dce3eb;
            vertical-align: top;
        }}

        .history-key {{
            width: 30%;
            font-weight: bold;
            color: #24527a;
            background: #edf2f7;
        }}

        .history-list {{
            padding-left: 25px;
        }}

        .history-list li {{
            margin: 7px 0;
            line-height: 1.5;
        }}

        .history-list-item {{
            background: white;
            border: 1px solid #dce3eb;
            padding: 12px;
            margin: 12px 0;
            border-radius: 5px;
        }}

        .history-list-item h4 {{
            margin: 0 0 8px;
            color: #24527a;
        }}

        .print-button {{
            display: block;
            margin: 25px auto;
            padding: 13px 25px;
            background: #24527a;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 15px;
            cursor: pointer;
        }}

        .print-button:hover {{
            background: #17365d;
        }}

        .footer {{
            text-align: center;
            margin-top: 45px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #718096;
            font-size: 13px;
        }}

        @media(max-width: 700px) {{

            body {{
                padding: 8px;
            }}

            .container {{
                padding: 15px;
            }}

            .chart-grid {{
                grid-template-columns: 1fr;
            }}

            .data-table {{
                font-size: 12px;
            }}

            .data-table th,
            .data-table td {{
                padding: 7px;
            }}

        }}

        @media print {{

            @page {{
                size: A4;
                margin: 15mm;
            }}

            body {{
                background: white;
                padding: 0;
                font-size: 10pt;
            }}

            .container {{
                max-width: none;
                padding: 0;
                border-radius: 0;
            }}

            .print-button {{
                display: none;
            }}

            .header {{
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }}

            .metric-card,
            .history-card,
            .chart-card,
            .success-message,
            .insight-list li,
            .history-key,
            .data-table th {{
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }}

            .section h2,
            .category-section h3,
            .history-card h3 {{
                break-after: avoid;
                page-break-after: avoid;
            }}

            .metric-card,
            .chart-card,
            .history-card,
            .category-section,
            .history-list-item {{
                break-inside: avoid;
                page-break-inside: avoid;
            }}

            .data-table tr {{
                break-inside: avoid;
                page-break-inside: avoid;
            }}

            .chart-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}

            .chart-card img {{
                max-height: 230px;
                width: 100%;
                object-fit: contain;
            }}

            .history-table {{
                font-size: 9pt;
            }}

            .footer {{
                margin-top: 25px;
            }}

        }}

    </style>

</head>

<body>

    <div class="container">

        <div class="header">

            <h1>Autonomous Data Analyst</h1>

            <p>Intelligent Dataset Analysis Report</p>

        </div>

        <button
            class="print-button"
            onclick="window.print()"
        >
            Print / Save as PDF
        </button>

        <div class="report-info">

            <h2>Dataset Information</h2>

            <p><b>Dataset ID:</b> {dataset_id}</p>

            <p><b>Dataset Name:</b> {html.escape(str(dataset_name))}</p>

            <p><b>Dataset Source:</b> {html.escape(dataset_source)}</p>

            <p><b>File Type:</b> {html.escape(str(file_type))}</p>

            <p><b>Uploaded At:</b> {html.escape(format_value(uploaded_at))}</p>

        </div>

        <div class="section">

            <h2>1. Dataset Overview</h2>

            <div class="metrics">

                <div class="metric-card">
                    <span>Total Rows</span>
                    <h2>{total_rows:,}</h2>
                </div>

                <div class="metric-card">
                    <span>Total Columns</span>
                    <h2>{total_columns:,}</h2>
                </div>

                <div class="metric-card">
                    <span>Missing Values</span>
                    <h2>{total_missing:,}</h2>
                </div>

                <div class="metric-card">
                    <span>Duplicate Records</span>
                    <h2>{duplicate_count:,}</h2>
                </div>

                {revenue_html}

                {discount_html}

            </div>

        </div>

        <div class="section">

            <h2>2. Dataset Column Details</h2>

            {column_html}

        </div>

        <div class="section">

            <h2>3. Missing Value Analysis</h2>

            {missing_html}

        </div>

        <div class="section">

            <h2>4. Numerical Analysis</h2>

            {numerical_html}

        </div>

        <div class="section">

            <h2>5. Categorical Analysis</h2>

            {categorical_html}

        </div>

        <div class="section">

            <h2>6. Automated Business Insights</h2>

            {insights_html}

        </div>

        <div class="section">

            <h2>7. Data Visualizations</h2>

            <div class="chart-grid">

                {visualization_html}

            </div>

        </div>

        <div class="section">

            <h2>8. Previous Analysis History</h2>

            {history_html}

        </div>

        <div class="footer">

            <p><b>Autonomous Data Analyst</b></p>

            <p>
                Generated on:
                {datetime.now().strftime("%d-%m-%Y %H:%M:%S")}
            </p>

            <p>Automated analysis powered by Python and Gemini AI</p>

        </div>

    </div>

</body>

</html>
"""

    # --------------------------------------------------
    # SAVE REPORT
    # --------------------------------------------------

    report_path = REPORT_FOLDER / f"dataset_report_{dataset_id}.html"

    with open(report_path, "w", encoding="utf-8") as file:
        file.write(report_html)

    print("\n" + "=" * 55)
    print("REPORT GENERATED SUCCESSFULLY!")
    print("=" * 55)

    print(f"\nDataset ID: {dataset_id}")
    print(f"Dataset Source: {dataset_source}")
    print(f"Total Rows: {total_rows:,}")
    print(f"Total Columns: {total_columns:,}")
    print(f"Missing Values: {total_missing:,}")
    print(f"Duplicate Records: {duplicate_count:,}")
    print(f"Automated Insights: {len(insights)}")
    print(f"Visualizations: {len(images)}")

    print(f"\nReport Location:\n{report_path}")

    print("\nOpen the HTML report in Chrome.")
    print("Use 'Print / Save as PDF' to export it as PDF.")

    print("=" * 55)


# ==================================================
# MAIN PROGRAM
# ==================================================

if __name__ == "__main__":

    print("=" * 55)
    print("       AUTONOMOUS DATA ANALYST")
    print("       PROFESSIONAL REPORT GENERATION")
    print("=" * 55)

    try:

        dataset_id = int(input("\nEnter Dataset ID: "))

        generate_report(dataset_id)

    except ValueError:

        print("\nPlease enter a valid Dataset ID.")

    except Exception as error:

        print("\nError generating report:", error)
