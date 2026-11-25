# Autonomous Data Analyst

A Streamlit application for uploading, cleaning, analyzing, and exploring datasets with PostgreSQL and Gemini.

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your own PostgreSQL and Gemini settings. Never commit `.env`.
4. Start the application:

   ```powershell
   python -m streamlit run app.py
   ```

Uploaded datasets, cleaned files, reports, and visualizations are stored locally and are excluded from Git.
