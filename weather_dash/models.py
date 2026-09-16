from datetime import datetime
from pydantic import BaseModel

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
