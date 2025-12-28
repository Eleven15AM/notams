# Build locally

```bash
# 1. Setup project
make init

# 2. Configure (edit .env if needed)
nano .env

# 3. Build Docker images
make build

# 4. Run single update
make run-once

# 5. View results
make reports
```

### 1. Clone and Initialize

```bash
# Create project directory
mkdir notams

# Copy/clone/fork all files into the directory structure shown above
git clone https://github.com/[USERNAME]/noatms

# move in
cd notams

# Initialize (creates directories and .env file)
make init
```

### 2. Configuration (.env)

The `.env` file contains all runtime configuration. Changes take effect immediately, but you need to restart the app.

```bash
# Logging
LOG_LEVEL=INFO

# Database location
DATABASE_PATH=/app/data/notam.db

# NOTAM API (currently using FAA public endpoint)
NOTAM_API_URL=https://notams.aim.faa.gov/notamSearch/search
NOTAM_API_KEY=

# Airports to monitor (ICAO codes, comma-separated)
AIRPORTS=EKCH,ENRY,EDDM,EYVI,EBCI,EBLG,EHRD,EKKA,EPWA,EGSS

# Update interval (seconds)
UPDATE_INTERVAL_SECONDS=3600

# Rate limiting - random delay between requests (seconds)
MIN_REQUEST_DELAY=2
MAX_REQUEST_DELAY=5

# Drone detection keywords (comma-separated, case-insensitive)
DRONE_KEYWORDS=drone,UAS,unmanned,RPAs,RPAS,UAV,-copter,balloon
```

### 3. Build Docker Images

```bash
make build
```

## Usage

### Running the Application

**Single Update:**
```bash
make run-once
```

**Continuous Monitoring (daemon):**
```bash
make run-background
make logs-follow  # View logs
make stop         # Stop when done
```

### Running Tests

```bash
# All tests
make test

# Just unit tests
make test-unit

# With coverage
make test-coverage
```

### Running Reports

```bash
# Quick access to all reports
make reports

# Individual reports
make report-stats        # Summary statistics
make report-active       # Active closures
make report-today        # Today's closures
make report-drone        # Drone-related closures
make report-by-airport   # Grouped by airport
```

### Custom SQL Queries

```bash
# Run existing queries
make query-drone
make query-recent

# Run your own query
make query FILE=queries/my_custom_query.sql
```

**Create Your Own Query:**

```sql
-- queries/my_query.sql
SELECT 
    airport_code,
    airport_name,
    COUNT(*) as total_closures,
    SUM(weight) as total_weight,
    SUM(CASE WHEN is_drone_related = 1 THEN 1 ELSE 0 END) as drone_count
FROM airport_closures
WHERE closure_start >= datetime('now', '-30 days')
GROUP BY airport_code, airport_name
ORDER BY drone_count DESC, total_weight DESC;
```

Run it:
```bash
make query FILE=queries/my_query.sql
```