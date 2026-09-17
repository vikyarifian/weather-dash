# weather-dash

Internal weather risk assessment API service for logistics and field dispatch operations. `weather-dash` periodically ingests regional weather snapshot data and correlates local rainfall and wind parameters against scheduled deliveries to issue dispatch safety alerts.

Built for internal integration with corporate ERP and transport management modules.

## System Architecture & Flow

```
+--------------------+      +------------------+      +-----------------------+
| Internal ERP / Transport| ---> |  Nginx Proxy     | ---> | weather-dash (Uvicorn)|
| Dispatch Module    |      | (port 80/443)    |      | (Port 8000)           |
+--------------------+      +------------------+      +-----------------------+
                                                                  |
                                                                  v
                                                      +-----------------------+
                                                      | PostgreSQL 18         |
                                                      | (weather_dash DB)     |
                                                      +-----------------------+
```

## Features

- **Regional Weather Ingestion**: Endpoint to ingest snapshot weather metrics including hourly rainfall (mm), wind speed (km/h), and temperature per defined zone.
- **Dispatch Safety Assessment**: API endpoint that evaluates dispatch route risk levels (e.g., safe, warning, suspended) based on configurable rainfall thresholds.
- **Historical Logs & Verification**: Weather snapshot archive endpoint for audit trails, delivery delay dispute resolution, and operational reviews (`surat_jalan` validation).
- **Zone Management & Health Monitoring**: CRUD operational endpoints for delivery zone metadata and standard `/healthz` monitoring for corporate load balancers.

## Prerequisites

- Python 3.14+
- PostgreSQL 18
- Linux environment (Rocky Linux 9 recommended for production alignment)

## Quickstart & Setup

1. **Clone repository and set up environment**
   ```bash
   git clone git@gitlab.internal.corp/logistics/weather-dash.git
   cd weather-dash
   python3.14 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Database Configuration**
   Ensure PostgreSQL 18 is running and initialize the database instance:
   ```sql
   CREATE DATABASE weather_dash;
   CREATE USER weather_user WITH ENCRYPTED PASSWORD 'select_password';
   GRANT ALL PRIVILEGES ON DATABASE weather_dash TO weather_user;
   ```

3. **Environment Variables**
   Create a `.env` file in the project root:
   ```env
   DATABASE_URL=postgresql://weather_user:select_password@localhost:5432/weather_dash
   APP_ENV=development
   LOG_LEVEL=INFO
   ```

4. **Run Application**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

## API Documentation

When running locally, interactable OpenAPI documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- Redoc: `http://localhost:8000/redoc`

## Production Deployment

Deployed on-premise on local Virtual Machines running Rocky Linux in the Jakarta Corporate Data Center.

1. Copy unit configuration to systemd:
   ```bash
   sudo cp deployment/weather-dash.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now weather-dash
   ```

2. Configure Nginx reverse proxy:
   ```nginx
   server {
       listen 80;
       server_name weather-dash.corp.internal;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```
