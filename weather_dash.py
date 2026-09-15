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

