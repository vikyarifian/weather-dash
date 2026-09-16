from datetime import datetime
from pydantic import BaseModel

class WilayahCreate(BaseModel):
    nama_wilayah: str
    max_rainfall_mm: float
    max_wind_speed_kph: float

