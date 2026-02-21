# NOTAMS: Notice to Airmen (NOTAMs) Monitoring System

A Docker-based Python application for querying, storing, and reporting on Notice to Airmen (NOTAM) notifications for worldwide airports, with emphasis on drone/UAP-related activity. Is it adversaries, is it UAPs, is it morons with a joystick? Who knows!

## Description

I built this app to process NOTAM notices and hunt for keywords like 'drones' and 'balloons' (read UAPs) in airspace closures - yes, this is an attempt at getting information about UFOs/UAPs, get over it.

**Version 2.0 Features:**
- **Rich NOTAM Domain Model** - Full ICAO-compliant parsing with Q-code decoding
- **Dual Monitoring Modes**:
  - `airport` mode - Traditional airport-specific monitoring
  - `search` mode - Free-text search across all NOTAMs
- **Priority Scoring** - Automatic scoring of NOTAM importance (0-100+)
- **Digest Alerts** - Batched notifications via ntfy.sh to respect rate limits
- **Aerodrome Database** - Cached airport data from OurAirports
- **Comprehensive Reporting** - Multiple report types for analysis

NOTAMS works by storing NOTAM data in a local SQLite database, which you can then query with canned reports or your own custom searches. The application intelligently parses ICAO-standard NOTAM format, extracts Q-codes, and calculates priority scores based on configurable rules.

I've wrapped it all in Docker for easier deployment, and most tasks are run through the Makefile for convenience. Easy is a relative term, some level of knowledge of Docker, Python and Linux systems (or Windows WSL) is required. I will try to be as clear as possible in the documentation, however.

The input data endpoint is a bit of a hack: it pulls data from the FAA's public site since I couldn't find a proper API that didn't cost a fortune. The code uses OOP principles, so swapping in a better data source later should be straightforward. And yes, the application plays nice by rate limiting itself to avoid spamming the site.

## Requirements

- Docker
- Docker Compose
- Make

## Project Structure

```bash
notams/
├── Dockerfile                    # Multi-stage Docker build
├── docker-compose.yml            # Service definitions
├── .env                          # Environment configuration (copy from .env.example)
├── .env.version                  # Version configuration
├── .env.example                  # Example configuration with all options
├── requirements.txt              # Python dependencies
├── requirements-test.txt         # Test dependencies
├── Makefile                      # Local development commands
├── Makefile.prod                 # Production deployment commands
├── run_query.sh                  # Helper script for running queries
├── src/
│   ├── __init__.py
│   ├── main.py                    # Main application entry point
│   ├── config.py                  # Configuration management
│   ├── notam_client.py            # NOTAM API clients (airport + search)
│   ├── database.py                # Database operations
│   ├── parser.py                  # NOTAM parsing (returns Notam objects)
│   ├── reports.py                 # Report generation
│   ├── alert_digester.py          # NEW - Batched ntfy notifications
│   ├── aerodrome_repository.py    # Airport data caching
│   ├── aerodrome_loader.py        # CLI for loading airport data
│   ├── database_cli.py            # Database maintenance CLI
│   └── models/
│       ├── __init__.py
│       └── notam.py               # Rich NOTAM domain model
├── tests/
│   ├── test_notam_model.py        # Notam model tests
│   ├── test_parser.py             # Parser tests
│   ├── test_database.py           # Database tests
│   └── test_integration.py        # Integration tests
├── queries/
│   ├── drone_closures.sql         # Drone-related NOTAMs
│   ├── recent_closures.sql        # Recent NOTAMs
│   └── todays_closures.sql        # Today's NOTAMs
└── data/
    ├── notam.db                   # SQLite database (created on first run)
    └── airports.csv                # Optional - OurAirports dataset

```

## Quick Start

### 1. Clone and Initialize

``` {bash}
# Clone the repository
git clone https://github.com/[USERNAME]/notams
cd notams

# Initialize project (creates directories and .env file)
make init

# Edit configuration
nano .env

```

### 2. Configure .env
Key configuration options (see .env.example for all options):

``` {bash}

# Software version
VERSION=v2.0.0

# Choose your monitoring mode:
# Option A: Airport monitoring
AIRPORTS=KATL,KORD,KLAX,EGLL,LFPG,EDDF

# Option B: Free-text search
SEARCH_TERMS=drone,UAS,UAV,RPAS,balloon,UAP

# Digest alerts (batched notifications)
NTFY_URL=https://ntfy.sh/your-topic
NTFY_DIGEST_INTERVAL=3600  # Send digest every hour
NTFY_MIN_SCORE=80          # Only include NOTAMs with score >= 80
NTFY_MAX_DIGEST_ITEMS=10   # Max items to show in digest

# Database
DATABASE_PATH=/app/data/notam.db

```

***Important***: Do not put inline comments ( # ...) on the same line as numeric values in .env. Docker's --env-file parser does not strip them, and the value will fail to parse. Put comments on their own line above the value instead!

### 3. Build and Run the Application

**Build the Docker images:**

``` bash
make build
```

**Running the Application:**

The application has two independent monitoring modes. Each runs as its own container and writes to the same shared database. You can run one or both simultaneously. 

Airport Mode — monitors a specific list of airports defined in ``` AIRPORTS=: ```

``` {bash}

# Run once and exit
make run-once-airport

# Continuous monitoring (background)
make run-background-airport
make logs-airport   # View logs
make stop           # Stop when done

```

Search Mode — free-text search across all NOTAMs for terms defined in ``` SEARCH_TERMS=: ```

``` {bash}
# Run once and exit
make run-once-search

# Continuous monitoring (background, with digest alerts)
make run-background-search
make logs-search    # View logs
make stop           # Stop when done

```

Both modes simultaneously:

``` bash
make run-background-all
make logs-follow    # View all container logs
make stop
```

### 4. Load Aerodrome Data (Optional but Recommended)
The system can cache airport data from the OurAirports open dataset. This enables better airport name resolution and country/location data for reports.

``` {bash}

# Download and load OurAirports CSV
make load-aerodromes

```

### 5. View Reports

``` {bash}

# All reports at once
make reports

# Individual reports
make report-stats        # Database statistics
make report-active       # Active NOTAMs
make report-closures     # Active closures
make report-drone        # Drone-related NOTAMs
make report-priority     # High priority NOTAMs (score >= 50)
make report-search       # NOTAMs by search term
make report-by-airport   # Grouped by airport

```

## Priority Scoring System

NOTAMs are automatically scored based on their importance:

|Condition|Points|
|---|---|
|Closure|+50|
|Drone-related|+30|
|Restriction (non-closure)|+20|
|NEW NOTAM|+10|
|REPLACE NOTAM|+5|
|Aerodrome scope|+10|
|Permanent|+5|
|Trigger NOTAM|-10|

Score thresholds:

- 80+: Critical - Urgent alerts
- 60-79: High priority
- 40-59: Medium priority
- <40: Routine

## Alerts with ntfy

When NTFY_URL is configured, the system batches alerts into periodic digests rather than sending one notification per NOTAM.
How it works:
- NOTAMs with priority_score >= NTFY_MIN_SCORE are added to a queue
- Every ``` NTFY_DIGEST_INTERVAL ``` seconds, a digest is sent
- The digest includes statistics and the top ``` NTFY_MAX_DIGEST_ITEMS ``` items
- On shutdown, a final digest is sent immediately

``` {bash}

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

## Database Maintenance

``` {bash}
# Purge old records (using configured values)
make purge

# Open SQLite shell
make db-shell

# Backup production database
make -f Makefile.prod db-backup-prod

```

## Production Deployment

Production uses pre-built images pulled from a registry. Each monitoring mode runs as its own independently managed container — ``` notam-airport-prod``` and ```notam-search-prod``` — both sharing the same database volume.

``` bash
# Start airport monitoring
make -f Makefile.prod start-airport-prod

# Start search monitoring
make -f Makefile.prod start-search-prod

# Start both
make -f Makefile.prod start-all-prod

# Check what's running
make -f Makefile.prod status-prod

# View logs
make -f Makefile.prod logs-airport-prod
make -f Makefile.prod logs-search-prod

# Generate reports (no running container required)
make -f Makefile.prod reports-prod

# Stop everything
make -f Makefile.prod stop-all-prod

```

## Running Tests

``` bash
# All tests
make test

# Unit tests only
make test-unit

# With coverage
make test-coverage

```

## Custom SQL Queries

Create your own queries in the queries/ directory:

``` bash
# in queries/high_priority.sql
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
# Run it:
make query FILE=queries/high_priority.sql
```