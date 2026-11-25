
import psycopg2
from psycopg2.extras import RealDictCursor

from database.config import get_db_config


# ==================================================
# DATABASE CONFIGURATION
# ==================================================

DB_CONFIG = get_db_config()
# ==================================================
# DATABASE CONNECTION
# ==================================================

def get_connection():
    """
    Establish and return a PostgreSQL connection.
    """

    try:
        connection = psycopg2.connect(**DB_CONFIG)
        return connection

    except psycopg2.Error as e:
        print("Database connection error:", e)
        raise


# ==================================================
# CHECK DATABASE CONNECTION
# ==================================================

def check_connection():
    """
    Check whether PostgreSQL is accessible.
    """

    connection = None

    try:
        connection = get_connection()

        cursor = connection.cursor()

        cursor.execute("SELECT version();")
        version = cursor.fetchone()

        print("PostgreSQL connected successfully!")
        print("Database:", DB_CONFIG["database"])
        print("Version:", version[0])

        cursor.close()

        return True

    except Exception as e:
        print("Connection failed:", e)
        return False

    finally:
        if connection:
            connection.close()


# ==================================================
# INSERT DATA
# ==================================================

def execute_query(query, values=None):
    """
    Execute INSERT, UPDATE or DELETE queries.
    """

    connection = None

    try:
        connection = get_connection()

        with connection.cursor() as cursor:
            cursor.execute(query, values)

            # Get returned value if the query uses RETURNING
            result = None

            if cursor.description:
                result = cursor.fetchone()

        connection.commit()

        return result

    except Exception as e:

        if connection:
            connection.rollback()

        print("Query execution failed:", e)
        raise

    finally:
        if connection:
            connection.close()


# ==================================================
# FETCH ONE RECORD
# ==================================================

def fetch_one(query, values=None):
    """
    Retrieve one record from PostgreSQL.
    """

    connection = None

    try:
        connection = get_connection()

        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, values)
            result = cursor.fetchone()

        return dict(result) if result else None

    except Exception as e:
        print("Fetch error:", e)
        raise

    finally:
        if connection:
            connection.close()


# ==================================================
# FETCH MULTIPLE RECORDS
# ==================================================

def fetch_all(query, values=None):
    """
    Retrieve multiple records from PostgreSQL.
    """

    connection = None

    try:
        connection = get_connection()

        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, values)
            results = cursor.fetchall()

        return [dict(row) for row in results]

    except Exception as e:
        print("Fetch error:", e)
        raise

    finally:
        if connection:
            connection.close()


# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    check_connection()
