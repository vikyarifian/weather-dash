import os
import sys
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import psycopg
from psycopg.rows import dict_row

# Configure Database connection from environment variables
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/weather_dash"
)

# Database Schema Initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS wilayah (
                        id SERIAL PRIMARY KEY,
                        nama_wilayah VARCHAR(100) UNIQUE NOT NULL,
                        max_rainfall_mm DECIMAL(5,2) NOT NULL,
                        max_wind_speed_kph DECIMAL(5,2) NOT NULL
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS weather_updates (
                        id SERIAL PRIMARY KEY,
                        wilayah_id INTEGER REFERENCES wilayah(id) ON DELETE CASCADE,
                        rainfall_mm DECIMAL(5,2) NOT NULL,
                        wind_speed_kph DECIMAL(5,2) NOT NULL,
                        temperature_c DECIMAL(4,1) NOT NULL,
                        recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS dispatch_logs (
                        id SERIAL PRIMARY KEY,
                        route_from_id INTEGER REFERENCES wilayah(id),
                        route_to_id INTEGER REFERENCES wilayah(id),
                        driver_name VARCHAR(150) NOT NULL,
                        surat_jalan_code VARCHAR(100) UNIQUE NOT NULL,
                        status VARCHAR(10) NOT NULL,
                        assessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT
                    );
                """)
                conn.commit()
    except Exception as e:
        print(f"Database connection or initialization failed: {e}", file=sys.stderr)
    yield

app = FastAPI(
    title="Weather Dash API",
    description="Internal Weather Assessment System for Dispatch Operations (Cikarang - Karawang)",
    version="1.0.0",
    lifespan=lifespan
)

# Pydantic Schemas
class WilayahCreate(BaseModel):
    nama_wilayah: str
    max_rainfall_mm: float
    max_wind_speed_kph: float

class WilayahResponse(BaseModel):
    id: int
    nama_wilayah: str
    max_rainfall_mm: float
    max_wind_speed_kph: float

class WeatherCreate(BaseModel):
    wilayah_id: int
    rainfall_mm: float
    wind_speed_kph: float
    temperature_c: float

class WeatherResponse(BaseModel):
    id: int
    wilayah_id: int
    rainfall_mm: float
    wind_speed_kph: float
    temperature_c: float
    recorded_at: datetime

class DispatchAssessRequest(BaseModel):
    route_from_id: int
    route_to_id: int
    driver_name: str
    surat_jalan_code: str

class DispatchAssessResponse(BaseModel):
    status: str
    notes: str
    assessed_at: datetime

# API Endpoints
@app.get("/api/v1/health")
def health_check():
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"status": "UP", "database": "CONNECTED"}
    except Exception as e:
        return {"status": "UP", "database": "DISCONNECTED", "detail": str(e)}

@app.post("/api/v1/wilayah", response_model=WilayahResponse)
def create_wilayah(data: WilayahCreate):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO wilayah (nama_wilayah, max_rainfall_mm, max_wind_speed_kph)
                    VALUES (%s, %s, %s)
                    RETURNING id, nama_wilayah, max_rainfall_mm, max_wind_speed_kph
                """, (data.nama_wilayah.lower().strip(), data.max_rainfall_mm, data.max_wind_speed_kph))
                result = cur.fetchone()
                conn.commit()
                return result
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                raise HTTPException(status_code=400, detail="Operational zone (wilayah) already exists")

@app.get("/api/v1/wilayah", response_model=list[WilayahResponse])
def list_wilayah():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nama_wilayah, max_rainfall_mm, max_wind_speed_kph FROM wilayah ORDER BY id ASC")
            return cur.fetchall()

@app.post("/api/v1/weather", response_model=WeatherResponse)
def record_weather(data: WeatherCreate):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # Validate wilayah relationship exists
            cur.execute("SELECT id FROM wilayah WHERE id = %s", (data.wilayah_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Operational zone (wilayah) does not exist")
            
            cur.execute("""
                INSERT INTO weather_updates (wilayah_id, rainfall_mm, wind_speed_kph, temperature_c)
                VALUES (%s, %s, %s, %s)
                RETURNING id, wilayah_id, rainfall_mm, wind_speed_kph, temperature_c, recorded_at
            """, (data.wilayah_id, data.rainfall_mm, data.wind_speed_kph, data.temperature_c))
            result = cur.fetchone()
            conn.commit()
            return result

@app.get("/api/v1/weather/history", response_model=list[WeatherResponse])
def get_weather_history(wilayah_id: int | None = None, limit: int = 50):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
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

@app.post("/api/v1/dispatch/assess", response_model=DispatchAssessResponse)
def assess_dispatch(data: DispatchAssessRequest):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # Check duplicate Surat Jalan to prevent processing same trip multiple times
            cur.execute("SELECT id FROM dispatch_logs WHERE surat_jalan_code = %s", (data.surat_jalan_code,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Surat Jalan assessment has already been logged previously")

            # Load operational thresholds for origin & destination zones
            cur.execute("SELECT * FROM wilayah WHERE id IN (%s, %s)", (data.route_from_id, data.route_to_id))
            zones = {row["id"]: row for row in cur.fetchall()}

            if data.route_from_id not in zones:
                raise HTTPException(status_code=404, detail="Origin zone (route_from_id) is invalid or not registered")
            if data.route_to_id not in zones:
                raise HTTPException(status_code=404, detail="Destination zone (route_to_id) is invalid or not registered")

            # Retrieve latest environmental readings
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
                    # Safely default to 0 parameters if the newly provisioned zone has no metrics ingested
                    weather_snapshots[zone_id] = {"rainfall_mm": 0.0, "wind_speed_kph": 0.0}

            # Apply safety validation rules against parameters
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

            # Store historical snapshot in ledger for review / delays verification
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

# Workaround for FastAPI limitation: FastAPI does not support direct mapping of Pydantic schemas as query parameters without complex dependency-injection resolvers.
@app.get("/api/v1/dispatch/quick-check")
def quick_check(from_id: int = Query(...), to_id: int = Query(...)):
    """
    Read-only safety scan utility for ERP dispatch modules to run route pre-checks without logging audit trails.
    """
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM wilayah WHERE id IN (%s, %s)", (from_id, to_id))
            zones = {row["id"]: row for row in cur.fetchall()}

            if from_id not in zones:
                raise HTTPException(status_code=404, detail="Origin zone is invalid or not registered")
            if to_id not in zones:
                raise HTTPException(status_code=404, detail="Destination zone is invalid or not registered")

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
