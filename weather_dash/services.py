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

def get_weather_history(wilayah_id: int | None = None, limit: int = 50) -> list[dict]:
    """
    Fetches historic weather snapshot log records.
    """
    with get_dict_connection() as conn:
        with conn.cursor() as cur:
            if wilayah_id:
                cur.execute("""
                    SELECT id, wilayah_id, rainfall_mm, wind_speed_kph, temperature_c, recorded_at 
                    FROM weather_updates 
                    WHERE wilayah_id = %s 
                    ORDER BY recorded_at DESC 
                    LIMIT %s
                """, (wilayah_id, limit))
            else:
                cur.execute("""
                    SELECT id, wilayah_id, rainfall_mm, wind_speed_kph, temperature_c, recorded_at 
                    FROM weather_updates 
                    ORDER BY recorded_at DESC 
                    LIMIT %s
                """, (limit,))
            return cur.fetchall()

def assess_dispatch(data: DispatchAssessRequest) -> dict:
    """
    Assesses routing dispatch risk and logs the result in dispatch_logs.
    Raises ValueError if Surat Jalan is duplicated or if route zones are invalid.
    """
    with get_dict_connection() as conn:
        with conn.cursor() as cur:
            # Check duplicate Surat Jalan
            cur.execute("SELECT id FROM dispatch_logs WHERE surat_jalan_code = %s", (data.surat_jalan_code,))
            if cur.fetchone():
                raise ValueError("Surat Jalan assessment has already been logged previously")

            # Load operational thresholds
            cur.execute("SELECT * FROM wilayah WHERE id IN (%s, %s)", (data.route_from_id, data.route_to_id))
            zones = {row["id"]: row for row in cur.fetchall()}

            if data.route_from_id not in zones:
                raise ValueError("Origin zone (route_from_id) is invalid or not registered")
            if data.route_to_id not in zones:
                raise ValueError("Destination zone (route_to_id) is invalid or not registered")

            # Get weather snapshots
            weather_snapshots = {}
            for zone_id in [data.route_from_id, data.route_to_id]:
                cur.execute("""
                    SELECT rainfall_mm, wind_speed_kph 
                    FROM weather_updates 
                    WHERE wilayah_id = %s 
                    ORDER BY recorded_at DESC 
                    LIMIT 1
                """, (zone_id,))
                update = cur.fetchone()
                if update:
                    weather_snapshots[zone_id] = update
                else:
                    weather_snapshots[zone_id] = {"rainfall_mm": 0.0, "wind_speed_kph": 0.0}

            # Compare thresholds
            breaches = []
            for zone_id, zone_config in zones.items():
                reading = weather_snapshots[zone_id]
                if float(reading["rainfall_mm"]) > float(zone_config["max_rainfall_mm"]):
                    breaches.append(
                        f"{zone_config['nama_wilayah'].upper()} rainfall of {reading['rainfall_mm']}mm "
                        f"exceeded safety limit of {zone_config['max_rainfall_mm']}mm"
                    )
                if float(reading["wind_speed_kph"]) > float(zone_config["max_wind_speed_kph"]):
                    breaches.append(
                        f"{zone_config['nama_wilayah'].upper()} wind speed of {reading['wind_speed_kph']}kph "
                        f"exceeded safety limit of {zone_config['max_wind_speed_kph']}kph"
                    )

            status = "BAHAYA" if breaches else "AMAN"
            notes = " | ".join(breaches) if breaches else "Safe dispatch conditions met."

            # Write log entry
            cur.execute("""
                INSERT INTO dispatch_logs (route_from_id, route_to_id, driver_name, surat_jalan_code, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING assessed_at
            """, (data.route_from_id, data.route_to_id, data.driver_name, data.surat_jalan_code, status, notes))
            log_result = cur.fetchone()
            conn.commit()

            return {
                "status": status,
                "notes": notes,
                "assessed_at": log_result["assessed_at"]
            }

def quick_check(from_id: int, to_id: int) -> dict:
    """
    Read-only safety scan utility for ERP dispatch modules without logging audits.
    Raises ValueError if zones are invalid.
    """
    with get_dict_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM wilayah WHERE id IN (%s, %s)", (from_id, to_id))
            zones = {row["id"]: row for row in cur.fetchall()}

            if from_id not in zones:
                raise ValueError("Origin zone is invalid or not registered")
            if to_id not in zones:
                raise ValueError("Destination zone is invalid or not registered")

            breaches = []
            for zone_id in [from_id, to_id]:
                zone_config = zones[zone_id]
                cur.execute("""
                    SELECT rainfall_mm, wind_speed_kph 
                    FROM weather_updates 
                    WHERE wilayah_id = %s 
                    ORDER BY recorded_at DESC 
                    LIMIT 1
                """, (zone_id,))
                reading = cur.fetchone()
                if not reading:
                    reading = {"rainfall_mm": 0.0, "wind_speed_kph": 0.0}

                if float(reading["rainfall_mm"]) > float(zone_config["max_rainfall_mm"]):
                    breaches.append(f"{zone_config['nama_wilayah']} rain alert ({reading['rainfall_mm']}mm)")
                if float(reading["wind_speed_kph"]) > float(zone_config["max_wind_speed_kph"]):
                    breaches.append(f"{zone_config['nama_wilayah']} wind alert ({reading['wind_speed_kph']}kph)")

            return {
                "status": "BAHAYA" if breaches else "AMAN",
                "notes": " | ".join(breaches) if breaches else "No current threshold violations detected."
            }
