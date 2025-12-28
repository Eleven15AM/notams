# NOTAMS: Notice to Airmen (NOTAMs) Monitoring System

A Docker-based Python application for querying, storing, and reporting on Notice to Airmen (NOTAM) notifications for worldwide airports, with emphasis on drone-related closures. Is it adversaries, is it UAPs, is it morons with a joystick? Who knows!

## Description
I built this app to process NOTAMs notices and hunt for keywords like 'drones' and 'balloons' (read UAPs) in airspace closures - yes, this is an attempt at getting information about UFOs/UAPs, get over it.

NOTAMS works by storing closure info in a local SQLite database, which you can then query with canned reports or your own custom searches. 

I've wrapped it all in Docker for easier deployment, and most tasks are run through the Makefile for convenience. Easy is a relative term, some level of knowledge of Docker, Python and Linux systems (or Windows WSL) is required. I will try to be as clear as possible in the documentation, however.

The input data endpoint is a bit of a hack: it pulls data from the FAA's public site since I couldn't find a proper API that didn't cost a fortune. 

The code uses OOP principles, so swapping in a better data source later should be straightforward. And yes, the application plays nice by rate limiting itself to avoid spamming the site.

## Requirements
- Docker
- Docker Compose
- Make

## Project Structure

The application relies heavely on Makefiles for its running. It is more efficient and promotes standardisation, I believe. The project deploys a Github Package that can be pulled when running in "Production" mode. You can however build the project locally.

```
notams/
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Service definitions
├── .env                    # Environment configuration (example)
├── .env                    # Environment configuration (needs to be copied from .env.exampleruntime)
├── requirements.txt        # Python dependencies
├── requirements-test.txt   # Test dependencies
├── Makefile               # Command shortcuts for local build and run
├── Makefile.prod          # Command shortcuts for "Production" run
├── run_query.sh           # Helper script for running queries
├── src/
│   ├── main.py            # Main application entry point
│   ├── config.py          # Configuration management
│   ├── notam_client.py    # NOTAM API client
│   ├── database.py        # Database operations
│   ├── parser.py          # NOTAM parsing logic
│   └── reports.py         # Report generation
├── tests/
│   ├── test_parser.py     # Parser unit tests
│   ├── test_database.py   # Database unit tests
│   └── test_integration.py # Integration tests
├── queries/
│   ├── drone_closures.sql  # Drone-related closures
│   ├── recent_closures.sql # Recent closures
│   └── todays_closures.sql # Today's closures
└── data/
    └── notam.db           # SQLite database (created on first run)
```

## Quick Start (pull the Github package)

You only need these things:

- `Makefile`
- `Makefile.prod`
- `.env` (copy from .env.example)

```bash
# 1. Clone project, if you are forking change the username to the appropriate value
git clone https://github.com/[USERNAME]/noatms

# 2. navigate in
cd notams

# 3. Create .env from example
cp .env.example .env

# 4. edit .env
nano .env

# 5. run
make run-background-prod
```   