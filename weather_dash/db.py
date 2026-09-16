import os
import psycopg
from psycopg.rows import dict_row

# Configure Database connection from environment variables
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/weather_dash"
)

def get_connection():
    """
    Establish and return a standard connection to the PostgreSQL database.
    """
    return psycopg.connect(DATABASE_URL)

def get_dict_connection():
    """
    Establish and return a connection with dict_row factory enabled
    to fetch database rows as dictionaries, matching our API representation needs.
    """
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
