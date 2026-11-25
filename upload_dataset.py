import io
import os

import pandas as pd

from database.database import get_connection


# --------------------------------------------------
# UPLOAD DIRECTORY
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --------------------------------------------------
# REUSABLE DATASET UPLOAD FUNCTION
# --------------------------------------------------

def register_uploaded_dataset(file_name, file_bytes):
    """
    Save uploaded CSV or Excel bytes and register the dataset in PostgreSQL.

    Returns a dictionary containing the new dataset's ID and metadata.
    Raises an exception if validation, file reading, or database insertion fails.
    """
    file_name = os.path.basename(file_name)
    file_extension = os.path.splitext(file_name)[1].lower()

    if file_extension not in [".csv", ".xlsx", ".xls"]:
        raise ValueError("Only CSV and Excel files are supported.")

    if not file_bytes:
        raise ValueError("The uploaded file is empty.")

    file_bytes = bytes(file_bytes)
    file_buffer = io.BytesIO(file_bytes)

    if file_extension == ".csv":
        df = pd.read_csv(file_buffer)
    else:
        df = pd.read_excel(file_buffer)

    name, extension = os.path.splitext(file_name)
    destination = os.path.join(UPLOAD_FOLDER, file_name)
    counter = 1

    while os.path.exists(destination):
        new_name = f"{name}_{counter}{extension}"
        destination = os.path.join(UPLOAD_FOLDER, new_name)
        counter += 1

    connection = None
    cursor = None

    try:
        with open(destination, "wb") as saved_file:
            saved_file.write(file_bytes)

        stored_path = os.path.relpath(destination, BASE_DIR)
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO datasets
            (
                dataset_name,
                file_path,
                file_type,
                total_rows,
                total_columns
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING dataset_id;
            """,
            (
                os.path.basename(destination),
                stored_path,
                file_extension.replace(".", "").upper(),
                len(df),
                len(df.columns),
            ),
        )

        dataset_id = cursor.fetchone()[0]
        connection.commit()

        return {
            "dataset_id": dataset_id,
            "dataset_name": os.path.basename(destination),
            "file_path": stored_path,
            "file_type": file_extension.replace(".", "").upper(),
            "total_rows": len(df),
            "total_columns": len(df.columns),
        }

    except Exception:
        if connection:
            connection.rollback()

        if os.path.exists(destination):
            os.remove(destination)

        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# --------------------------------------------------
# COMMAND-LINE DATASET UPLOAD
# --------------------------------------------------

def upload_dataset():
    try:
        file_path = input(
            "Enter CSV or Excel file path: "
        ).strip().strip('"')

        if not os.path.isfile(file_path):
            print("Error: File does not exist!")
            return

        file_name = os.path.basename(file_path)

        with open(file_path, "rb") as source_file:
            file_bytes = source_file.read()

        dataset = register_uploaded_dataset(file_name, file_bytes)

        print("\n================================")
        print("DATASET UPLOADED SUCCESSFULLY!")
        print("================================")
        print("Dataset ID:", dataset["dataset_id"])
        print("Dataset Name:", dataset["dataset_name"])
        print("File Type:", dataset["file_type"])
        print("Total Rows:", dataset["total_rows"])
        print("Total Columns:", dataset["total_columns"])
        print("Stored Path:", dataset["file_path"])

    except Exception as error:
        print("\nDataset upload failed!")
        print("Error:", error)


# --------------------------------------------------
# MAIN
# --------------------------------------------------

if __name__ == "__main__":
    upload_dataset()