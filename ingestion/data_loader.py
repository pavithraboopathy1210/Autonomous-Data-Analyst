
import pandas as pd
import os

def load_dataset(file_path):

    if not os.path.exists(file_path):
        raise FileNotFoundError("Dataset file does not exist")

    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == ".csv":
        df = pd.read_csv(file_path)

    elif file_extension in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path)

    else:
        raise ValueError("Unsupported file format. Use CSV or Excel.")

    if df.empty:
        raise ValueError("The uploaded dataset is empty")

    return df
