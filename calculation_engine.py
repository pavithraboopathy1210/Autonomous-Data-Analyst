
import re
import pandas as pd


def find_column(df, possible_names):
    """Find a dataset column using case-insensitive matching."""
    column_map = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for name in possible_names:
        if name.lower() in column_map:
            return column_map[name.lower()]

    return None


def get_numeric_series(df, column):
    return pd.to_numeric(df[column], errors="coerce").dropna()


def make_result(calculation, result, columns_used, value=None):
    return {
        "calculation": calculation,
        "result": result,
        "columns_used": columns_used,
        "value": value
    }


def calculate_answer(df, question):

    if df is None or df.empty:
        return make_result(
            "Dataset validation",
            "The dataset is empty.",
            []
        )

    question = question.lower().strip()

    if not question:
        return None

    amount_column = find_column(
        df,
        ["sales_amount", "purchase_amount", "revenue", "total_amount"]
    )

    quantity_column = find_column(
        df,
        ["quantity", "qty", "units_sold", "product_quantity"]
    )

    city_column = find_column(df, ["city"])
    product_column = find_column(df, ["product"])
    category_column = find_column(df, ["category"])
    payment_column = find_column(
        df,
        ["payment_method", "payment_type", "payment"]
    )

    # --------------------------------------------------
    # 1. TOTAL NUMBER OF RECORDS
    # --------------------------------------------------

    if any(phrase in question for phrase in [
        "total records",
        "number of records",
        "number of rows",
        "how many records",
        "how many rows",
        "total number of records"
    ]):

        return make_result(
            "Record count",
            f"Total records: {len(df)}",
            [],
            len(df)
        )

    # --------------------------------------------------
    # 2. MISSING VALUES
    # --------------------------------------------------

    if "missing value" in question or "missing values" in question:

        missing = int(df.isnull().sum().sum())

        return make_result(
            "Missing value count",
            f"Total missing values: {missing}",
            [],
            missing
        )

    # --------------------------------------------------
    # 3. DUPLICATE RECORDS
    # --------------------------------------------------

    if "duplicate" in question:

        duplicates = int(df.duplicated().sum())

        return make_result(
            "Duplicate record count",
            f"Total duplicate records: {duplicates}",
            [],
            duplicates
        )

    # --------------------------------------------------
    # 4. TOTAL QUANTITY SOLD
    # --------------------------------------------------

    if quantity_column and any(phrase in question for phrase in [
        "total quantity",
        "total units",
        "quantity sold",
        "units sold",
        "how many products sold",
        "total products sold"
    ]):

        quantity = get_numeric_series(df, quantity_column)
        total_quantity = float(quantity.sum())

        return make_result(
            "Total quantity sold",
            f"Total quantity sold: {total_quantity:g}",
            [quantity_column],
            total_quantity
        )

    # --------------------------------------------------
    # 5. TOTAL SALES / REVENUE
    # --------------------------------------------------

    if amount_column:

        amount = get_numeric_series(df, amount_column)

        if any(phrase in question for phrase in [
            "total sales",
            "total revenue",
            "overall sales",
            "overall revenue",
            "sum of sales",
            "sum of revenue"
        ]):

            total = float(amount.sum())

            return make_result(
                "Total sales / revenue",
                f"Total {amount_column}: {total:.2f}",
                [amount_column],
                total
            )

        # --------------------------------------------------
        # 6. AVERAGE SALES / REVENUE
        # --------------------------------------------------

        if any(phrase in question for phrase in [
            "average sales",
            "average revenue",
            "average purchase amount",
            "average sales amount",
            "mean sales",
            "mean revenue"
        ]):

            average = float(amount.mean())

            return make_result(
                "Average sales",
                f"Average {amount_column}: {average:.2f}",
                [amount_column],
                average
            )

        # --------------------------------------------------
        # 7. HIGHEST / LOWEST TRANSACTION
        # --------------------------------------------------

        if any(phrase in question for phrase in [
            "highest transaction",
            "maximum transaction",
            "largest transaction",
            "highest purchase amount",
            "largest purchase"
        ]):

            highest = float(amount.max())

            return make_result(
                "Highest transaction",
                f"Highest transaction: {highest:.2f}",
                [amount_column],
                highest
            )

        if any(phrase in question for phrase in [
            "lowest transaction",
            "minimum transaction",
            "smallest transaction",
            "lowest purchase amount",
            "smallest purchase"
        ]):

            lowest = float(amount.min())

            return make_result(
                "Lowest transaction",
                f"Lowest transaction: {lowest:.2f}",
                [amount_column],
                lowest
            )

    # --------------------------------------------------
    # 8. CORRELATION BETWEEN NUMERIC COLUMNS
    # --------------------------------------------------

    if "correlation" in question or "relationship between" in question:

        numeric_columns = df.select_dtypes(
            include="number"
        ).columns.tolist()

        mentioned_columns = []

        for column in numeric_columns:
            if column.lower() in question:
                mentioned_columns.append(column)

        if len(mentioned_columns) >= 2:

            first_column = mentioned_columns[0]
            second_column = mentioned_columns[1]

            first_values = pd.to_numeric(
                df[first_column],
                errors="coerce"
            )

            second_values = pd.to_numeric(
                df[second_column],
                errors="coerce"
            )

            valid = pd.concat(
                [first_values, second_values],
                axis=1
            ).dropna()

            if len(valid) < 2:
                return make_result(
                    "Correlation analysis",
                    "Not enough valid data to calculate correlation.",
                    [first_column, second_column]
                )

            correlation = float(
                valid.iloc[:, 0].corr(valid.iloc[:, 1])
            )

            return make_result(
                "Correlation analysis",
                (
                    f"Correlation between {first_column} and "
                    f"{second_column}: {correlation:.4f}"
                ),
                [first_column, second_column],
                correlation
            )

    # --------------------------------------------------
    # 9. PERCENTAGE OF A CATEGORY
    # --------------------------------------------------

    if "percentage" in question or "percent" in question:

        categorical_columns = df.select_dtypes(
            include=["object", "category"]
        ).columns.tolist()

        for column in categorical_columns:

            if column.lower() not in question:
                continue

            values = df[column].dropna().astype(str).unique()

            for category_value in values:

                if category_value.lower() in question:

                    total_valid = int(df[column].notna().sum())

                    if total_valid == 0:
                        continue

                    matching = int(
                        (
                            df[column].astype(str).str.lower()
                            == category_value.lower()
                        ).sum()
                    )

                    percentage = matching / total_valid * 100

                    return make_result(
                        f"Percentage of {category_value}",
                        (
                            f"{category_value}: {matching} out of "
                            f"{total_valid} records "
                            f"({percentage:.2f}%)"
                        ),
                        [column],
                        percentage
                    )

    # --------------------------------------------------
    # 10. MOST / LEAST FREQUENT CATEGORY
    # --------------------------------------------------

    frequency_phrases = [
        "most frequently",
        "most common",
        "most popular",
        "used most",
        "highest frequency",
        "highest number of orders",
        "most number of orders",
        "most orders",
        "most transactions",
        "highest count",
        "highest number"
    ]

    lowest_frequency_phrases = [
        "least frequently",
        "least common",
        "least popular",
        "lowest frequency",
        "fewest orders",
        "lowest count",
        "least number"
    ]

    frequency_requested = any(
        phrase in question for phrase in frequency_phrases
    )

    lowest_frequency_requested = any(
        phrase in question for phrase in lowest_frequency_phrases
    )

    if frequency_requested or lowest_frequency_requested:

        group_columns = [
            ("payment method", payment_column),
            ("payment", payment_column),
            ("city", city_column),
            ("product", product_column),
            ("category", category_column)
        ]

        selected_column = None

        for keyword, column in group_columns:
            if keyword in question and column is not None:
                selected_column = column
                break

        if selected_column:

            counts = df[selected_column].dropna().value_counts()

            if not counts.empty:

                if lowest_frequency_requested:
                    name = counts.idxmin()
                    count = int(counts.min())
                    operation = "Least frequent"
                else:
                    name = counts.idxmax()
                    count = int(counts.max())
                    operation = "Most frequent"

                return make_result(
                    f"{operation} {selected_column}",
                    (
                        f"{operation} {selected_column}: {name}. "
                        f"Count: {count}"
                    ),
                    [selected_column],
                    count
                )

    # --------------------------------------------------
    # 11. GROUPED AVERAGE
    # --------------------------------------------------

    if amount_column and any(phrase in question for phrase in [
        "average by",
        "average for each",
        "highest average",
        "lowest average",
        "average sales by",
        "average sales for each",
        "average revenue by"
    ]):

        group_columns = [
            ("product", product_column),
            ("category", category_column),
            ("city", city_column)
        ]

        selected_column = None

        for keyword, column in group_columns:
            if keyword in question and column is not None:
                selected_column = column
                break

        if selected_column:

            temp = df[[selected_column, amount_column]].copy()

            temp[amount_column] = pd.to_numeric(
                temp[amount_column],
                errors="coerce"
            )

            temp = temp.dropna(
                subset=[selected_column, amount_column]
            )

            grouped = temp.groupby(selected_column)[
                amount_column
            ].mean()

            if not grouped.empty:

                if "lowest" in question:
                    name = grouped.idxmin()
                    value = float(grouped.min())
                    operation = "Lowest"
                else:
                    name = grouped.idxmax()
                    value = float(grouped.max())
                    operation = "Highest"

                return make_result(
                    f"{operation} average sales by {selected_column}",
                    (
                        f"{operation} average sales {selected_column}: "
                        f"{name}. Average {amount_column}: {value:.2f}"
                    ),
                    [selected_column, amount_column],
                    value
                )

    # --------------------------------------------------
    # 12. HIGHEST / LOWEST REVENUE BY GROUP
    # --------------------------------------------------

    if amount_column:

        group_columns = [
            ("product", product_column),
            ("category", category_column),
            ("city", city_column)
        ]

        for keyword, column in group_columns:

            if column is None or keyword not in question:
                continue

            # Avoid treating order-count questions as revenue questions.
            if any(word in question for word in [
                "number of orders",
                "number of transactions",
                "most orders",
                "highest count",
                "how many orders"
            ]):
                break

            temp = df[[column, amount_column]].copy()

            temp[amount_column] = pd.to_numeric(
                temp[amount_column],
                errors="coerce"
            )

            temp = temp.dropna(
                subset=[column, amount_column]
            )

            grouped = temp.groupby(column)[amount_column].sum()

            if grouped.empty:
                continue

            if any(word in question for word in [
                "lowest", "minimum", "least", "smallest"
            ]):
                name = grouped.idxmin()
                value = float(grouped.min())
                operation = "Lowest"
            else:
                name = grouped.idxmax()
                value = float(grouped.max())
                operation = "Highest"

            return make_result(
                f"{operation} revenue by {column}",
                (
                    f"{operation} revenue {column}: {name}. "
                    f"Total {amount_column}: {value:.2f}"
                ),
                [column, amount_column],
                value
            )

    # --------------------------------------------------
    # 13. MOST ORDERS BY CITY / PRODUCT / CATEGORY
    # --------------------------------------------------

    if any(phrase in question for phrase in [
        "number of orders",
        "how many orders",
        "most orders",
        "highest number of orders",
        "number of transactions",
        "most transactions"
    ]):

        group_columns = [
            ("city", city_column),
            ("product", product_column),
            ("category", category_column)
        ]

        for keyword, column in group_columns:

            if column is not None and keyword in question:

                counts = df[column].dropna().value_counts()

                if not counts.empty:

                    name = counts.idxmax()
                    count = int(counts.max())

                    return make_result(
                        f"Order count by {column}",
                        (
                            f"Highest number of orders by {column}: "
                            f"{name}. Orders: {count}"
                        ),
                        [column],
                        count
                    )

    # --------------------------------------------------
    # 14. ORDERS BY DAY OF WEEK
    # --------------------------------------------------

    if "day of the week" in question or "weekday" in question:

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

            day_counts = dates.dropna().dt.day_name().value_counts()

            if not day_counts.empty:

                day = day_counts.idxmax()
                count = int(day_counts.max())

                return make_result(
                    "Orders by day of week",
                    f"Most orders occurred on {day}: {count} orders.",
                    [date_column],
                    count
                )

    # --------------------------------------------------
    # 15. MONTHLY SALES ANALYSIS
    # --------------------------------------------------

    if amount_column and (
        "month" in question or "monthly" in question
    ):

        date_columns = [
            column for column in df.columns
            if "date" in column.lower()
        ]

        if date_columns:

            date_column = date_columns[0]

            temp = df[[date_column, amount_column]].copy()

            temp["_date"] = pd.to_datetime(
                temp[date_column],
                errors="coerce",
                format="mixed"
            )

            temp[amount_column] = pd.to_numeric(
                temp[amount_column],
                errors="coerce"
            )

            temp = temp.dropna(
                subset=["_date", amount_column]
            )

            monthly = temp.groupby(
                temp["_date"].dt.to_period("M")
            )[amount_column].sum()

            if not monthly.empty:

                if any(word in question for word in [
                    "lowest", "least", "minimum"
                ]):
                    month = monthly.idxmin()
                    value = float(monthly.min())
                    operation = "Lowest"
                else:
                    month = monthly.idxmax()
                    value = float(monthly.max())
                    operation = "Highest"

                return make_result(
                    "Monthly sales analysis",
                    (
                        f"{operation} sales month: {month}. "
                        f"Total sales: {value:.2f}"
                    ),
                    [date_column, amount_column],
                    value
                )

    # --------------------------------------------------
    # 16. AVERAGE OF OTHER NUMERIC COLUMNS
    # --------------------------------------------------

    if "average" in question or "mean" in question:

        numeric_columns = df.select_dtypes(
            include="number"
        ).columns.tolist()

        for column in numeric_columns:

            if column.lower() in question:

                values = get_numeric_series(df, column)

                if not values.empty:

                    average = float(values.mean())

                    return make_result(
                        f"Average {column}",
                        f"Average {column}: {average:.2f}",
                        [column],
                        average
                    )

    # --------------------------------------------------
    # NO SUPPORTED CALCULATION
    # --------------------------------------------------

    return None
