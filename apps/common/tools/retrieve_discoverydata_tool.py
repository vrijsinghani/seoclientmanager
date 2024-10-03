import os
import psycopg2
from typing import Optional, List
from dotenv import load_dotenv

from crewai_tools import tool

# Load environment variables from .env file
load_dotenv()

@tool("PostgreSQL DiscoveryData Retrieval")
def pg_data_retrieval_tool(
    company_name: str,
) -> List[dict]:
    """
    A tool to retrieve discovery data for a prospective client based on company name from database, useful for company background and expectations.

    To use this tool, provide the following input:
    - company_name: The name of the company to filter the data

    The tool will return the queried data as a list of dictionaries.
    """
    try:
        db_protocol = os.environ.get("DB_PROTOCOL")
        db_username = os.environ.get("DB_USERNAME")
        db_password = os.environ.get("DB_PASSWORD")
        db_host = os.environ.get("DB_HOST")
        db_name = os.environ.get("DB_NAME")
        table_name = os.environ.get("DB_DISCOVERY")

        conn = psycopg2.connect(
            f"{db_protocol}://{db_username}:{db_password}@{db_host}/{db_name}"
        )
        cursor = conn.cursor()

        # Get the field names from the database table
        cursor.execute(f"SELECT * FROM {table_name} WHERE 1=0")
        field_names = [desc[0] for desc in cursor.description]

        query = f"SELECT * FROM {table_name} WHERE company_name like '{company_name}'"
        cursor.execute(query)
        result = cursor.fetchall()

        if result:
            # Convert the result to a list of dictionaries
            data = [dict(zip(field_names, row)) for row in result]
            return data
        else:
            return []

    except (Exception, psycopg2.Error) as e:
        return [{"error": str(e)}]

    finally:
        # Close the database connection
        if conn:
            cursor.close()
            conn.close()
