# Build locally

## Quick Start

```bash
# 1. Setup project
make init

# 2. Configure (edit .env)
nano .env

# 3. Build Docker images
make build

# 4. Choose your monitoring mode:

# Airport mode
make run-once-airport

# OR Search mode
make run-once-search

# 5. View results
make reports
```

### 1. Clone and Initialize

```bash
# Create project directory
mkdir notams
cd notams

# Clone repository
git clone https://github.com/[USERNAME]/notams .

# Initialize (creates directories and .env file)
make init
```

### 2. Configuration (.env)

The `.env` file contains all runtime configuration. Changes take effect immediately, but you need to restart the app.

```bash
# Software version (change accordingly)
VERSION=v2.0.0

# Logging
LOG_LEVEL=INFO

# Database location
DATABASE_PATH=/app/data/notam.db

# NOTAM API (FAA public endpoint)
NOTAM_API_URL=https://notams.aim.faa.gov/notamSearch/search
NOTAM_API_KEY=

# === OPTION A: Airport Monitoring ===
AIRPORTS=KATL,KORD,KLAX,EGLL,LFPG,EDDF

# === OPTION B: Free-Text Search ===
SEARCH_TERMS=drone,UAS,UAV,RPAS,balloon,UAP

# Update interval (seconds)
UPDATE_INTERVAL_SECONDS=3600

# Rate limiting - random delay between requests (seconds)
MIN_REQUEST_DELAY=2
MAX_REQUEST_DELAY=5

# Drone detection keywords (comma-separated, case-insensitive)
DRONE_KEYWORDS=drone,UAS,unmanned,RPAs,RPAS,UAV,-copter,balloon

# === Digest Alerts (batched notifications) ===
NTFY_URL=https://ntfy.sh/your-topic
# How often to send a digest (seconds)
NTFY_DIGEST_INTERVAL=3600
# Minimum priority score to include in digest
NTFY_MIN_SCORE=80
# Maximum items to show per digest
NTFY_MAX_DIGEST_ITEMS=10

# === Priority Score Thresholds ===
CLOSURE_SCORE=50
DRONE_SCORE=30
RESTRICTION_SCORE=20

# === Aerodrome Data ===
AIRPORTS_CSV_PATH=/app/data/airports.csv

# === Purge Settings ===
PURGE_EXPIRED_AFTER_DAYS=30
PURGE_CANCELLED_AFTER_DAYS=7
```

### 3. Build Docker Images

```bash
make build
```

## Usage

### Running the Application

**Airport Mode:**
```bash
# Run once and exit
make run-once-airport

# Continuous monitoring (background)
make run-background-airport
make logs-airport   # View logs
make stop           # Stop when done
```

**Search Mode:**
```bash
# Run once and exit
make run-once-search

# Continuous monitoring (background, with digest alerts)
make run-background-search
make logs-search    # View logs
make stop           # Stop when done
```

**Both modes:**
``` bash
make run-background-all
make logs-follow    # View all container logs
make stop
```

### Aerodrome Data (Optional but Recommended)
The system can cache airport data from the OurAirports open dataset.
This enables:
- Better airport name resolution
- Country/location data for reports
- Geospatial queries (future)

``` bash
# Download and load airports.csv
make load-aerodromes
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
make report-stats        # Database statistics
make report-active       # Active NOTAMs
make report-closures     # Active closures
make report-drone        # Drone-related NOTAMs
make report-priority     # High priority NOTAMs (score >= 50)
make report-search       # NOTAMs by search term
make report-by-airport   # Grouped by airport

# Production reports
make -f Makefile.prod reports-prod
```

### Database Maintenance
``` bash
# Purge old records (using configured values)
make purge

# Open SQLite shell
make db-shell

# Backup production database
make -f Makefile.prod db-backup-prod
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
    notam_id,
    airport_code,
    priority_score,
    is_closure,
    is_drone_related,
    substr(body, 1, 100) as preview
FROM notams
WHERE priority_score >= 80
ORDER BY priority_score DESC;
```

Run it:
```bash
make query FILE=queries/my_query.sql
```

### Digest Alert System

When running in continuous search mode (make search-background), the system accumulates high-priority NOTAMs and sends periodic digests.
**How It Works**
1. NOTAMs with score >= ```NTFY_MIN_SCORE``` are added to a queue
2. Every ```NTFY_DIGEST_INTERVAL``` seconds, a digest is sent
3. The digest includes statistics and the top ```NTFY_MAX_DIGEST_ITEMS``` items
4. On shutdown, a final digest is sent immediately

**Example digest**

``` text
NOTAM Digest: 12 new high-priority items

📊 Summary
• Total: 12
• Closures: 8
• Drone-related: 3
• Restrictions: 4
• Airports affected: 5

⏰ Period: 2026-02-20 10:30 UTC

🔔 Top Items

1. A0521/26 - LPSO (Score: 100) [CLOSURE, DRONE]
   RUNWAY 09/27 CLSD DUE TO DRONE ACTIVITY...

2. A0522/26 - LPSO (Score: 100) [CLOSURE, DRONE]
   AD CLSD DUE TO UAS SIGHTING...

... and 2 more

[View in NOTAM system](https://ntfy.sh/your-topic)
```

### Understanding Priority Scores
NOTAMs are automatically scored based on their content:
|Score|Range|Meaning|Digest Inclusion|
|---|---|---|---|
|80+|Critical|Always included|
|60-79|High priority|Optional (adjust threshold)|
|40-59|Medium priority|Rarely included|
|<40|Routine|Never included|

***Example scoring:***
- Drone closure: 50 (closure) + 30 (drone) + 10 (NEW) = 90
- Normal closure: 50 (closure) + 10 (NEW) = 60
- Drone restriction: 30 (drone) + 20 (restriction) + 10 (NEW) = 60