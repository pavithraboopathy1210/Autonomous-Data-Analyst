
def get_dataset_overview(df):
    overview = {
        "total_rows": df.shape[0],
        "total_columns": df.shape[1],
        "column_names": df.columns.tolist(),
        "data_types": df.dtypes.astype(str).to_dict()
    }

    return overview

def get_missing_values(df):
    missing = df.isnull().sum()

    missing_report = {
        "total_missing_values": int(missing.sum()),
        "missing_by_column": missing[missing > 0].to_dict(),
        "missing_percentage": (
            (missing / len(df)) * 100
        )[missing > 0].round(2).to_dict()
    }

    return missing_report

def get_duplicate_count(df):
    duplicate_count = df.duplicated().sum()

    duplicate_report = {
        "total_duplicates": int(duplicate_count),
        "duplicate_rows": df[df.duplicated()].to_dict(orient="records")
    }

    return duplicate_report

def get_statistical_summary(df):

    numerical_df = df.select_dtypes(include="number")

    if numerical_df.empty:
        return {}

    summary = numerical_df.describe()

    return summary.to_dict()



def profile_dataset(df):

    report = {
        "overview": get_dataset_overview(df),
        "missing_values": get_missing_values(df),
        "duplicates": get_duplicate_count(df),
        "statistics": get_statistical_summary(df)
    }

    return report
