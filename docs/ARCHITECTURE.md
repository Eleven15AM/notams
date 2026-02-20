# Architecture

```mermaid
flowchart TD
    subgraph A[Configuration Layer]
        A1[config.py]
        A2[.env] 
    end
    
    subgraph B[API Client Layer]
        B1[BaseNotamClient - Abstract Class]
        B2[FAANotamClient - Airport Mode]
        B3[FreeTextNotamClient - Search Mode]
        B4[AuthenticatedNotamClient - Future]
    end
    
    subgraph C[Domain Model Layer]
        C1[models/notam.py - Rich NOTAM Class]
        C2[Q-Code Decoding]
        C3[Priority Score Calculation]
    end
    
    subgraph D[Parsing Layer]
        D1[parser.py - Returns Notam Objects]
    end
    
    subgraph E[Persistence Layer]
        E1[database.py - New Schema]
        E2[aerodrome_repository.py - Airport Cache]
    end
    
    subgraph F[Presentation Layer]
        F1[reports.py - Updated Reports]
        F2[alert_digester.py - Digest Alerts]
    end
    
    A --> B
    B2-->B1
    B3-->B1
    B-->D
    D-->C
    C-->E
    E-->F
    C-->F2
```

### Client Inheritance Pattern

The system uses an inheritance-based architecture to support different API types, when they become available:

```text
BaseNotamClient (Abstract)
    ├── FAANotamClient (Airport-based search)
    ├── FreeTextNotamClient (Free-text search)
    └── AuthenticatedNotamClient (Token-based - future)
```
- **Airport Mode** (FAANotamClient): Traditional airport-specific queries
- **Search Mode** (FreeTextNotamClient): Free-text search with automatic pagination

**Current Implementation**: Uses FAA public endpoint (no authentication)

**Future Implementation**:
1. Add a `NOTAM_API_KEY` to `.env`
2. System automatically switches to `AuthenticatedNotamClient` note: some coding is going to be required!

### Rate Limiting

To avoid detection and rate limits:
- Random delays between requests (`MIN_REQUEST_DELAY` to `MAX_REQUEST_DELAY`)
- Browser-like headers
- Natural request patterns
- Configurable timing in `.env` file

### Digest Alert System
Instead of sending individual alerts for every NOTAM, the system uses a batched digest approach:

``` text
AlertDigester
    ├── Accumulates high-priority NOTAMs (score >= NTFY_MIN_SCORE)
    ├── Sends periodic summaries every NTFY_DIGEST_INTERVAL seconds
    ├── Includes statistics (totals, closures, drone, restrictions)
    ├── Shows top N items (NTFY_MAX_DIGEST_ITEMS)
    └── Sends final digest on shutdown
```
This prevents rate limiting issues with ntfy.sh while keeping users informed.

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

### Runtime Configuration

All settings are loaded from environment variables at runtime:
- Change `.env` file
- Restart container (`make restart`)

## Drone Detection

Keywords (configurable in `.env`):

## Database Schema

### notams Table

```mermaid
erDiagram
    notams {
        int id PK
        string notam_id UK "Unique identifier (e.g., A3097/25)"
        string series "Letter prefix (A, R, etc.)"
        string notam_type "NEW, REPLACE, CANCEL"
        string replaces_notam_id "If NOTAMR"
        string cancels_notam_id "If NOTAMC"
        string fir "Flight Information Region"
        string q_code "Full Q-code"
        string q_code_subject "Decoded subject"
        string q_code_condition "Decoded condition"
        string traffic "IV, I, V, K"
        string purpose "Purpose qualifier"
        string scope "Scope qualifier"
        int lower_limit "Lower FL"
        int upper_limit "Upper FL"
        string coordinates "Raw coordinates"
        float latitude "Parsed decimal"
        float longitude "Parsed decimal"
        int radius_nm "Radius in NM"
        string airport_code "ICAO code"
        string airport_name "Airport name"
        string location "A) field"
        datetime valid_from "B) field"
        datetime valid_to "C) field"
        boolean is_permanent "PERM flag"
        string schedule "D) field"
        string body "E) field (decoded)"
        string lower_limit_text "F) field"
        string upper_limit_text "G) field"
        boolean is_closure "Derived"
        boolean is_drone_related "Derived"
        boolean is_restriction "Derived"
        boolean is_trigger_notam "Derived"
        string search_term "Source search term"
        int priority_score "Calculated score"
        string source "Source system"
        string source_type "Source type"
        datetime issue_date "Issue date"
        string raw_icao_message "Original message"
        int transaction_id "FAA transaction ID"
        boolean has_history "Has history flag"
        datetime created_at "Record creation"
        datetime updated_at "Last update"
    }
```

### search_runs Table
``` mermaid
erDiagram
    search_runs {
        int id PK
        string search_term "Search term used"
        string airport_codes "Airports for airport mode"
        string mode "airport or search"
        int total_fetched "Records fetched"
        int new_inserted "New inserts"
        int updated "Updates"
        datetime run_at "Run timestamp"
    }
```

### aerodromes Table
``` mermaid
erDiagram
    aerodromes {
        string icao_code PK
        string iata_code "IATA code"
        string name "Airport name"
        string type "Airport type"
        float latitude "Decimal degrees"
        float longitude "Decimal degrees"
        int elevation_ft "Elevation in feet"
        string continent "Continent code"
        string country_code "ISO country code"
        string country_name "Country name"
        string region "Region"
        string municipality "City"
        string gps_code "GPS code"
        string source "ourairports or notam_inference"
        datetime created_at
        datetime updated_at
    }
```

### Component Details

**alert_digester.py**

The digester runs in a background thread and accumulates NOTAMs:
python
``` python
class AlertDigester:
    def add(notam: Notam)  # Queue a NOTAM for next digest
    def send_immediate()    # Force digest send (used on shutdown)
```
**Key features:**
- Thread-safe with locks
- Tracks statistics (totals, closures, drone, restrictions)
- Deduplicates by airport
- Sanitizes titles for HTTP headers (handles Unicode)
- Falls back gracefully if ntfy is not configured

**notam_client.py**

Core model, two client implementations:
``` python
# Airport mode - fetches NOTAMs for specific ICAO codes
FAANotamClient.fetch_all_notams()

# Search mode - free-text search with pagination
FreeTextNotamClient.fetch_all_notams()  # Auto-paginates 30 records per page
```

**database.py**

Key methods for the new schema:
``` python

upsert_notam(notam: Notam)              # Insert or update with deduplication
get_active_notams(min_score: int)       # Active NOTAMs with score filter
get_closures(active_only: bool)         # Get closure NOTAMs
get_drone_notams(active_only: bool)     # Get drone-related NOTAMs
purge_expired(days: int)                # Remove old expired NOTAMs
purge_cancelled(days: int)              # Remove old cancelled NOTAMs
```


## Testing Strategy

### Unit Tests

- test_notam_model.py: NOTAM parsing, Q-code decoding, priority scoring
- test_parser.py: Returns Notam objects
- test_database.py: New schema operations

### Integration Tests

- test_integration.py: Complete workflows with new data structures

**Run Tests:**
```bash
make test           # All tests
make test-unit      # Fast unit tests only
make test-coverage  # With coverage report
```