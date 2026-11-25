
import pandas as pd
from pathlib import Path

from database.database import get_connection
from agents.data_analyst_agent import (
    create_data_analyst_agent,
    ask_agent
)


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

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT dataset_name, file_path, cleaned_file_path
                FROM datasets
                WHERE dataset_id = %s
                """,
                (dataset_id,)
            )

            result = cursor.fetchone()

        if result is None:
            raise ValueError("Dataset ID not found!")

        dataset_name, original_file_path, cleaned_file_path = result

        # Prefer cleaned dataset
        if cleaned_file_path and str(cleaned_file_path).strip():

            file_path = Path(cleaned_file_path)
            dataset_source = "cleaned"

        else:

            file_path = Path(original_file_path)
            dataset_source = "original (cleaned file not available)"

        if not file_path.is_absolute():
            file_path = BASE_DIR / file_path

        if not file_path.exists():
            raise FileNotFoundError(
                f"Dataset not found: {file_path}"
            )

        # Read dataset
        if file_path.suffix.lower() == ".csv":

            df = pd.read_csv(file_path)

        elif file_path.suffix.lower() in [".xlsx", ".xls"]:

            df = pd.read_excel(file_path)

        else:

            raise ValueError("Unsupported file format!")

        return df, dataset_name, dataset_source, file_path

    finally:
        connection.close()


# --------------------------------------------------
# 2. SAVE CHAT HISTORY
# --------------------------------------------------

def save_chat(dataset_id, session_id, role, message):

    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO chat_history
                (dataset_id, session_id, role, message)
                VALUES (%s, %s, %s, %s)
                """,
                (dataset_id, session_id, role, message)
            )

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:
        connection.close()


# --------------------------------------------------
# 3. MAIN PROGRAM
# --------------------------------------------------

def main():

    print("=" * 55)
    print("       AUTONOMOUS DATA ANALYST")
    print("       AI DATA QUESTION ANSWERING")
    print("=" * 55)

    try:

        dataset_id = int(
            input("\nEnter Dataset ID: ")
        )

        # Load dataset
        df, dataset_name, dataset_source, file_path = load_dataset(
            dataset_id
        )

        print(f"\nDataset loaded: {dataset_name}")
        print(f"Dataset source: {dataset_source}")
        print(f"File path: {file_path}")
        print(f"Rows: {len(df)}")
        print(f"Columns: {len(df.columns)}")

        # Create autonomous AI agent
        print("\nInitializing autonomous AI analyst...")

        agent = create_data_analyst_agent(df)

        print("AI analyst is ready!")

        session_id = f"dataset_{dataset_id}_session"

        print("\nYou can now ask questions about your dataset.")
        print("Type 'exit' to stop.")

        # Question-answering loop
        while True:

            try:

                question = input(
                    "\nAsk your question: "
                ).strip()

            except EOFError:

                print("\nInput closed. Exiting.")
                break

            if question.lower() == "exit":

                print(
                    "\nThank you for using Autonomous Data Analyst!"
                )

                break

            if not question:

                print("Please enter a question.")
                continue

            try:

                # Save user question
                save_chat(
                    dataset_id,
                    session_id,
                    "user",
                    question
                )

                # Get answer from autonomous agent
                print("\nAnalyzing your question...")

                answer = ask_agent(
                    agent,
                    question
                )

                # Display answer
                print("\n" + "=" * 55)
                print("          AI DATA ANALYST ANSWER")
                print("=" * 55)

                print(answer)

                # Save AI response
                save_chat(
                    dataset_id,
                    session_id,
                    "assistant",
                    answer
                )

                print("\nConversation saved successfully!")

            except Exception as error:

                print(
                    f"\nQuestion processing error: {error}"
                )

    except KeyboardInterrupt:

        print("\n\nProgram interrupted by user.")

    except Exception as error:

        print(f"\nError: {error}")


# --------------------------------------------------
# 4. PROGRAM ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    main()
