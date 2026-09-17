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

def list_all_wilayah() -> list[dict]:
    """
    Retrieves all registered wilayah zones.
    """
    with get_dict_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nama_wilayah, max_rainfall_mm, max_wind_speed_kph FROM wilayah ORDER BY id ASC")
            return cur.fetchall()

def record_weather(data: WeatherCreate) -> dict:
    """
    Inserts a weather update. Validates that the target wilayah exists first.
    """
    with get_dict_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM wilayah WHERE id = %s", (data.wilayah_id,))
            if not cur.fetchone():
                raise ValueError("Operational zone (wilayah) does not exist")
            
            cur.execute("""
                INSERT INTO weather_updates (wilayah_id, rainfall_mm, wind_speed_kph, temperature_c)
                VALUES (%s, %s, %s, %s)
                RETURNING id, wilayah_id, rainfall_mm, wind_speed_kph, temperature_c, recorded_at
            """, (data.wilayah_id, data.rainfall_mm, data.wind_speed_kph, data.temperature_c))
            result = cur.fetchone()
            conn.commit()
            return result

