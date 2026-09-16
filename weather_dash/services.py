import psycopg
from datetime import datetime
from weather_dash.db import get_dict_connection
from weather_dash.models import WilayahCreate, WeatherCreate, DispatchAssessRequest

def register_wilayah(data: WilayahCreate) -> dict:
    """
    Inserts a new operational zone (wilayah) into the database.
    Matches POST /api/v1/wilayah logic.
    """
    with get_dict_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO wilayah (nama_wilayah, max_rainfall_mm, max_wind_speed_kph)
                VALUES (%s, %s, %s)
                RETURNING id, nama_wilayah, max_rainfall_mm, max_wind_speed_kph
            """, (data.nama_wilayah.lower().strip(), data.max_rainfall_mm, data.max_wind_speed_kph))
            result = cur.fetchone()
            conn.commit()
            return result

