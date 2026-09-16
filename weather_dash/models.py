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

