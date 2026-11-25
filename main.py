import subprocess
import sys
from pathlib import Path


# ==================================================
# PROJECT CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent


# ==================================================
# MODULE EXECUTION
# ==================================================

def run_module(module_name):

    module_path = BASE_DIR / module_name

    if not module_path.exists():
        print(f"\nError: {module_name} was not found!")
        return

    print("\n" + "=" * 55)
    print(f"RUNNING: {module_name.upper()}")
    print("=" * 55)

    try:
        result = subprocess.run(
            [sys.executable, str(module_path)],
            cwd=BASE_DIR
        )

        if result.returncode == 0:
            print(f"\n{module_name} completed.")
        elif result.returncode in (-2, 130):
            print(f"\n{module_name} was interrupted by the user.")
        else:
            print(
                f"\n{module_name} stopped with "
                f"exit code {result.returncode}."
            )

    except KeyboardInterrupt:
        print("\nModule execution interrupted.")

    except Exception as error:
        print(f"\nError while running {module_name}: {error}")


# ==================================================
# MAIN MENU
# ==================================================

def display_menu():

    print("\n")
    print("=" * 55)
    print("          AUTONOMOUS DATA ANALYST")
    print("=" * 55)

    print("\nDATA MANAGEMENT")
    print("1. Upload Dataset")
    print("2. Clean Dataset")

    print("\nDATA ANALYSIS")
    print("3. Analyze Dataset")
    print("4. Generate Visualizations")
    print("5. Generate AI Insights")

    print("\nAI QUESTION ANSWERING")
    print("6. Ask Questions About Dataset")

    print("\nREPORT GENERATION")
    print("7. Generate Analysis Report")

    print("\nSYSTEM")
    print("8. Exit")

    print("=" * 55)


# ==================================================
# MAIN FUNCTION
# ==================================================

def main():

    modules = {
        "1": "upload_dataset.py",
        "2": "clean_dataset.py",
        "3": "analyze.py",
        "4": "visualize_dataset.py",
        "5": "generate_insights.py",
        "6": "ask_question.py",
        "7": "generate_report.py"
    }

    while True:

        display_menu()

        try:
            choice = input("\nEnter your choice (1-8): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nInput closed. Exiting Autonomous Data Analyst.")
            break

        if choice == "8":
            print("\nThank you for using Autonomous Data Analyst!")
            break

        elif choice in modules:
            run_module(modules[choice])

            try:
                input("\nPress Enter to return to the main menu...")
            except (EOFError, KeyboardInterrupt):
                print("\nReturning to the main menu was interrupted. Exiting safely.")
                break

        else:
            print("\nInvalid choice! Please enter a number from 1 to 8.")


# ==================================================
# PROGRAM ENTRY POINT
# ==================================================

if __name__ == "__main__":
    main()
