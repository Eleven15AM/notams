"""NOTAM domain model."""
import re
import html
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

from src.config import Config


class NotamType(Enum):
    """NOTAM type based on suffix."""
    NEW = "NEW"        # NOTAMN
    REPLACE = "REPLACE" # NOTAMR
    CANCEL = "CANCEL"   # NOTAMC


# ---------------------------------------------------------------------------
# Q-Code decoding tables (ICAO Annex 15 / Doc 8126)
#
# IMPORTANT: These are TWO SEPARATE lookup tables.
#
#   Q_CODE_SUBJECTS  — decoded from letters 2+3 of the Q-code (e.g. "MR" in QMRLC)
#                      Identifies WHAT the NOTAM is about (the subject).
#
#   Q_CODE_CONDITIONS — decoded from letters 4+5 of the Q-code (e.g. "LC" in QMRLC)
#                       Identifies the STATUS or CONDITION of the subject.
#
# The two tables are entirely independent and their key namespaces must not overlap.
# Many two-letter codes appear in both tables with different meanings — this is
# intentional per the ICAO standard (e.g. "LC" means "Runway centre line lights"
# as a subject, but "Closed" as a condition).
# ---------------------------------------------------------------------------

# Subject codes: 2nd + 3rd letters of the Q-code
Q_CODE_SUBJECTS = {
    # AGA — Lighting Facilities (L_)
    "LA": "Approach lighting system",
    "LB": "Aerodrome beacon",
    "LC": "Runway centre line lights",
    "LD": "Landing direction indicator lights",
    "LE": "Runway edge lights",
    "LF": "Sequenced flashing lights",
    "LH": "High intensity runway lights",
    "LI": "Runway end identifier lights",
    "LJ": "Runway alignment indicator lights",
    "LK": "Category II components of approach lighting system",
    "LL": "Low intensity runway lights",
    "LM": "Medium intensity runway lights",
    "LP": "Precision approach path indicator",
    "LR": "All landing area lighting facilities",
    "LS": "Stopway lights",
    "LT": "Threshold lights",
    "LV": "Visual approach slope indicator system",
    "LW": "Heliport lighting",
    "LX": "Taxiway centre line lights",
    "LY": "Taxiway edge lights",
    "LZ": "Runway touchdown zone lights",

    # AGA — Movement and Landing Area (M_)
    "MA": "Movement area",
    "MB": "Bearing strength",
    "MC": "Clearway",
    "MD": "Declared distances",
    "MG": "Taxiing guidance system",
    "MH": "Runway arresting gear",
    "MK": "Parking area",
    "MM": "Daylight markings",
    "MN": "Apron",
    "MP": "Aircraft stands",
    "MR": "Runway",
    "MS": "Stopway",
    "MT": "Threshold",
    "MU": "Runway turning bay",
    "MW": "Strip",
    "MX": "Taxiway(s)",

    # AGA — Facilities and Services (F_)
    "FA": "Aerodrome",
    "FB": "Braking action measurement equipment",
    "FC": "Ceiling measurement equipment",
    "FD": "Docking system",
    "FF": "Fire fighting and rescue",
    "FG": "Ground movement control",
    "FH": "Helicopter alighting area/platform",
    "FL": "Landing direction indicator",
    "FM": "Meteorological service",
    "FO": "Fog dispersal system",
    "FP": "Heliport",
    "FS": "Snow removal equipment",
    "FT": "Transmissometer",
    "FU": "Fuel availability",
    "FW": "Wind direction indicator",
    "FZ": "Customs",

    # COM — Communications and Radar Facilities (C_)
    "CA": "Air/ground facility",
    "CE": "En route surveillance radar",
    "CG": "Ground controlled approach system",
    "CL": "Selective calling system (SELCAL)",
    "CM": "Surface movement radar",
    "CP": "Precision approach radar",
    "CR": "Surveillance radar element of precision approach system",
    "CS": "Secondary surveillance radar (SSR)",
    "CT": "Terminal area surveillance radar",

    # COM — Instrument and Microwave Landing Systems (I_)
    "ID": "DME associated with ILS",
    "IG": "ILS glide path",
    "II": "ILS inner marker",
    "IL": "ILS localiser",
    "IM": "ILS middle marker",
    "IO": "ILS outer marker",
    "IS": "ILS Category I",
    "IT": "ILS Category II",
    "IU": "ILS Category III",
    "IW": "Microwave landing system (MLS)",
    "IX": "ILS localiser outer",
    "IY": "ILS localiser middle",

    # COM — Terminal and En Route Navigation Facilities (N_)
    "NA": "All radio navigation facilities",
    "NB": "Non-directional radio beacon (NDB)",
    "NC": "DECCA",
    "ND": "Distance measuring equipment (DME)",
    "NF": "Fan marker",
    "NL": "Locator",
    "NM": "VOR/DME",
    "NN": "TACAN",
    "NO": "OMEGA",
    "NT": "VORTAC",
    "NV": "VOR",
    "NX": "Direction finding station",

    # RAC — Airspace Organisation (A_)
    "AA": "Minimum altitude",
    "AC": "Class B, C, D or E surface area",
    "AD": "Air defence identification zone (ADIZ)",
    "AE": "Control area (CTA)",
    "AF": "Flight information region (FIR)",
    "AG": "General aviation area",
    "AH": "Upper control area (UTA)",
    "AI": "Initial approach fix",
    "AK": "Upper flight information region (UIR)",
    "AL": "Minimum usable flight level",
    "AM": "Military operating area (MOA)",
    "AN": "Terminal control area (TCA)",
    "AO": "Control zone (CTR)",
    "AP": "Reporting point",
    "AR": "RNAV route",
    "AT": "Terminal area",
    "AU": "Upper advisory area",
    "AV": "Upper advisory route",
    "AX": "Intermediate approach fix",
    "AZ": "Aerodrome traffic zone (ATZ)",

    # RAC — Air Traffic Procedures (P_)
    "PA": "Standard instrument arrival (STAR)",
    "PD": "Standard instrument departure (SID)",
    "PF": "Flow control procedure",
    "PH": "Holding procedure",
    "PI": "Instrument approach procedure",
    "PL": "Obstacle clearance limit",
    "PM": "Aerodrome operating minima",
    "PO": "Obstacle clearance altitude",
    "PP": "Obstacle clearance height",
    "PR": "Radio failure procedure",
    "PT": "Transition altitude",
    "PU": "Missed approach procedure",
    "PX": "Minimum holding altitude",
    "PZ": "ADIZ procedure",

    # RAC — Airspace Restrictions (R_)
    "RA": "Airspace reservation",
    "RD": "Danger area",
    "RO": "Overflying",
    "RP": "Prohibited area",
    "RR": "Restricted area",
    "RT": "Temporary restricted area",

    # Navigation Warnings (W_)
    "WA": "Air display",
    "WB": "Aerobatics",
    "WC": "Captive balloon or kite",
    "WD": "Demolition of explosives",
    "WE": "Exercises",
    "WF": "Air refuelling",
    "WG": "Glider flying",
    "WJ": "Banner/target towing",
    "WL": "Ascent of free balloon",
    "WM": "Missile, gun or rocket firing",
    "WP": "Parachute jumping exercise",
    "WS": "Burning or blowing gas",
    "WT": "Mass movement of aircraft",
    "WU": "Unmanned aircraft",
    "WV": "Formation flight",
    "WZ": "Model flying",

    # Other Information (O_)
    "OA": "Aeronautical information service",
    "OB": "Obstacle",
    "OE": "Aircraft entry requirements",
    "OL": "Obstacle lights",
    "OR": "Rescue coordination centre",

    # Plain language fallback
    "XX": "Plain language",
}


# Condition codes: 4th + 5th letters of the Q-code
Q_CODE_CONDITIONS = {
    # Availability (A_)
    "AC": "Withdrawn for maintenance",
    "AD": "Available for daylight operation",
    "AF": "Flight checked and found reliable",
    "AG": "Operating but ground checked only, awaiting flight check",
    "AH": "Hours of service are now",
    "AK": "Resumed normal operations",
    "AM": "Military operations only",
    "AN": "Available for night operation",
    "AO": "Operational",
    "AP": "Available, prior permission required",
    "AR": "Available on request",
    "AS": "Unserviceable",
    "AU": "Not available",
    "AW": "Completely withdrawn",
    "AX": "Previously promulgated shutdown cancelled",

    # Changes (C_)
    "CA": "Activated",
    "CC": "Completed",
    "CD": "Deactivated",
    "CE": "Erected",
    "CF": "Operating frequency changed to",
    "CG": "Downgraded to",
    "CH": "Changed",
    "CI": "Identification or radio call sign changed to",
    "CL": "Realigned",
    "CM": "Displaced",
    "CO": "Operating",
    "CP": "Operating on reduced power",
    "CR": "Temporarily replaced by",
    "CS": "Installed",

    # Hazard Conditions (H_)
    "HA": "Braking action is",
    "HB": "Braking coefficient is",
    "HC": "Covered by compacted snow",
    "HD": "Covered by dry snow",
    "HE": "Covered by water",
    "HF": "Totally free of snow and ice",
    "HG": "Grass cutting in progress",
    "HH": "Hazard due to",
    "HI": "Covered by ice",
    "HJ": "Launch planned",
    "HK": "Migration in progress",
    "HL": "Snow clearance completed",
    "HM": "Marked by",
    "HN": "Covered by wet snow or slush",
    "HO": "Obscured by snow",
    "HP": "Snow clearance in progress",
    "HQ": "Operation cancelled",
    "HR": "Standing water",
    "HS": "Sanding in progress",
    "HT": "Approach according to signal area only",
    "HU": "Launch in progress",
    "HV": "Work completed",
    "HW": "Work in progress",
    "HX": "Concentration of birds",
    "HY": "Snow banks exist",
    "HZ": "Covered by frozen ruts and ridges",

    # Limitations (L_)
    # Note: L_ condition codes are entirely distinct from L_ subject codes above.
    # "LC" as a subject = "Runway centre line lights"; "LC" as a condition = "Closed".
    "LA": "Operating on auxiliary power supply",
    "LB": "Reserved for aircraft based therein",
    "LC": "Closed",
    "LD": "Unsafe",
    "LE": "Operating without auxiliary power supply",
    "LF": "Interference from",
    "LG": "Operating without identification",
    "LH": "Unserviceable for aircraft heavier than",
    "LI": "Closed to IFR operations",
    "LK": "Operating as a fixed light",
    "LL": "Usable for length of ... and width of ...",
    "LN": "Closed to all night operations",
    "LP": "Prohibited to",
    "LR": "Aircraft restricted to runways and taxiways",
    "LS": "Subject to interruption",
    "LT": "Limited to",
    "LV": "Closed to VFR operations",
    "LW": "Will take place",
    "LX": "Operating but caution advised due to",

    # Trigger NOTAM (T_)
    # TT is used specifically in the Q-code condition position to flag a Trigger NOTAM.
    "TT": "Trigger NOTAM",

    # Plain language fallback
    "XX": "Plain language",
}


@dataclass
class Notam:
    """Rich domain model for a NOTAM message following ICAO standards."""

    # Identity & Series
    notam_id: str
    series: str
    number: int
    year: int

    # NOTAM Type
    notam_type: NotamType
    replaces_notam_id: Optional[str] = None
    cancels_notam_id: Optional[str] = None

    # Q-Line
    fir: Optional[str] = None
    q_code: Optional[str] = None
    q_code_subject: Optional[str] = None
    q_code_condition: Optional[str] = None
    traffic: Optional[str] = None
    purpose: Optional[str] = None
    scope: Optional[str] = None
    lower_limit: Optional[int] = None
    upper_limit: Optional[int] = None
    coordinates: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_nm: Optional[int] = None

    # Lettered Fields
    location: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    is_permanent: bool = False
    schedule: Optional[str] = None
    body: Optional[str] = None
    lower_limit_text: Optional[str] = None
    upper_limit_text: Optional[str] = None

    # Source metadata
    airport_code: Optional[str] = None
    airport_name: Optional[str] = None
    issue_date: Optional[datetime] = None
    source: Optional[str] = None
    source_type: Optional[str] = None
    raw_icao_message: Optional[str] = None
    transaction_id: Optional[int] = None
    has_history: bool = False

    # Derived / Computed
    search_term: Optional[str] = None
    priority_score: int = 0

    def __post_init__(self):
        """Calculate derived properties after initialization."""
        if self.priority_score == 0:
            self.priority_score = self._calculate_priority_score()

    @property
    def is_closure(self) -> bool:
        """
        Check if NOTAM indicates a closure.

        Checks both the free-text body (primary) and the Q-code condition
        (secondary). The Q-code condition "LC" means "Closed" per ICAO, so
        a NOTAM with QMRLC (runway closed) is correctly identified even if
        the body text uses non-standard wording.
        """
        # Q-code based check (most reliable — structured ICAO data)
        if self.q_code and len(self.q_code) >= 5:
            condition_code = self.q_code[3:5]
            closure_condition_codes = {
                'LC',  # Closed
                'LI',  # Closed to IFR operations
                'LN',  # Closed to all night operations
                'LV',  # Closed to VFR operations
            }
            if condition_code in closure_condition_codes:
                return True

        # Body text keyword check (handles non-standard / plain language NOTAMs)
        if not self.body:
            return False

        text_lower = self.body.lower()
        closure_keywords = [
            'closed', 'clsd', 'closure', 'not avbl',
            'unavailable', 'suspended', 'ad clsd',
            'airport closed', 'rwy closed', 'runway closed'
        ]
        return any(keyword in text_lower for keyword in closure_keywords)

    @property
    def is_drone_related(self) -> bool:
        """Check if NOTAM is drone-related."""
        if not self.body:
            return False

        text_lower = self.body.lower()
        config = Config()

        for keyword in config.DRONE_KEYWORDS:
            # Use word boundaries to match whole words only
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, text_lower):
                return True
        return False

    @property
    def is_restriction(self) -> bool:
        """
        Check if NOTAM indicates a restricted/prohibited/danger area.

        Uses Q-code subject codes (2nd+3rd letters) as primary source,
        with a body text fallback for plain-language NOTAMs.
        """
        if self.q_code and len(self.q_code) >= 3:
            restriction_subject_codes = {
                'RD',  # Danger area
                'RP',  # Prohibited area
                'RR',  # Restricted area
                'RT',  # Temporary restricted area
                'RA',  # Airspace reservation
                'WU',  # Unmanned aircraft
            }
            subject_code = self.q_code[1:3]
            if subject_code in restriction_subject_codes:
                return True

        if self.body:
            text_lower = self.body.lower()
            restriction_keywords = [
                'restricted area', 'prohibited area', 'danger area',
                'temporary restricted', 'activated'
            ]
            return any(keyword in text_lower for keyword in restriction_keywords)

        return False

    @property
    def is_trigger_notam(self) -> bool:
        """Check if this is a TRIGGER NOTAM."""
        if not self.body:
            return False
        return self.body.strip().upper().startswith('TRIGGER NOTAM')

    def _calculate_priority_score(self) -> int:
        """
        Calculate priority score based on additive rules.

        | Condition                    | Points |
        |------------------------------|--------|
        | is_closure is True           | +50    |
        | is_drone_related is True     | +30    |
        | notam_type is NEW            | +10    |
        | notam_type is REPLACE        | +5     |
        | notam_type is CANCEL         |  0     |
        | scope includes A (aerodrome) | +10    |
        | is_permanent is True         | +5     |
        | is_trigger_notam is True     | -10    |
        | is_restriction (non-closure) | +20    |
        """
        config = Config()
        score = 0

        if self.is_closure:
            score += config.CLOSURE_SCORE

        if self.is_drone_related:
            score += config.DRONE_SCORE

        if self.notam_type == NotamType.NEW:
            score += 10
        elif self.notam_type == NotamType.REPLACE:
            score += 5
        # CANCEL gets 0

        if self.scope and 'A' in self.scope:
            score += 10

        if self.is_permanent:
            score += 5

        if self.is_trigger_notam:
            score -= 10

        if self.is_restriction and not self.is_closure:
            score += config.RESTRICTION_SCORE

        return max(0, score)  # Ensure non-negative

    @classmethod
    def from_api_dict(cls, data: Dict[str, Any], search_term: Optional[str] = None) -> 'Notam':
        """
        Factory method to create a Notam from FAA API response dict.

        Args:
            data: Raw API response dictionary
            search_term: Optional search term that retrieved this NOTAM

        Returns:
            Notam instance
        """
        # Extract basic fields
        notam_id = data.get('notamNumber', '')
        icao_message = data.get('icaoMessage', '')

        # Parse series, number, year from NOTAM ID (e.g. "A3097/25")
        series = notam_id[0] if notam_id else ''
        number = None
        year = None

        if '/' in notam_id:
            num_part, year_part = notam_id.split('/')
            if num_part and len(num_part) > 1:
                series = num_part[0]
                try:
                    number = int(num_part[1:])
                except (ValueError, IndexError):
                    pass
            try:
                year = int(year_part)
            except ValueError:
                pass

        # Parse NOTAM type from first line of icaoMessage
        notam_type = NotamType.NEW
        replaces_notam_id = None
        cancels_notam_id = None

        first_line = icao_message.split('\n')[0] if icao_message else ''
        if 'NOTAMR' in first_line:
            notam_type = NotamType.REPLACE
            match = re.search(r'NOTAMR\s+([A-Z]\d+/\d+)', first_line)
            if match:
                replaces_notam_id = match.group(1)
        elif 'NOTAMC' in first_line:
            notam_type = NotamType.CANCEL
            match = re.search(r'NOTAMC\s+([A-Z]\d+/\d+)', first_line)
            if match:
                cancels_notam_id = match.group(1)

        # Parse Q-line
        fir = None
        q_code = None
        traffic = None
        purpose = None
        scope = None
        lower_limit = None
        upper_limit = None
        coordinates = None
        latitude = None
        longitude = None
        radius_nm = None
        q_code_subject = None
        q_code_condition = None

        q_match = re.search(r'Q\)\s*([^)]+?)(?=\s+[A-Z]\)|\s*$)', icao_message)
        if q_match:
            q_parts = q_match.group(1).strip().split('/')
            if len(q_parts) >= 8:
                fir = q_parts[0] if q_parts[0] else None
                q_code = q_parts[1] if len(q_parts) > 1 else None
                traffic = q_parts[2] if len(q_parts) > 2 else None
                purpose = q_parts[3].strip() if len(q_parts) > 3 and q_parts[3] else None
                scope = q_parts[4] if len(q_parts) > 4 else None

                try:
                    lower_limit = int(q_parts[5]) if len(q_parts) > 5 and q_parts[5].isdigit() else None
                except (ValueError, IndexError):
                    pass

                try:
                    upper_limit = int(q_parts[6]) if len(q_parts) > 6 and q_parts[6].isdigit() else None
                except (ValueError, IndexError):
                    pass

                coordinates = q_parts[7] if len(q_parts) > 7 else None

                # Decode Q-code using the two SEPARATE lookup tables.
                # Letters 2+3 → subject (what the NOTAM is about).
                # Letters 4+5 → condition (the status of that subject).
                if q_code and len(q_code) >= 5:
                    subject_code = q_code[1:3]
                    condition_code = q_code[3:5]
                    q_code_subject = Q_CODE_SUBJECTS.get(
                        subject_code, f"Unknown ({subject_code})"
                    )
                    q_code_condition = Q_CODE_CONDITIONS.get(
                        condition_code, f"Unknown ({condition_code})"
                    )

                # Parse coordinates: format 4904N00607E003 (lat°min + lon°min + radius NM)
                if coordinates and len(coordinates) >= 11:
                    lat_part = coordinates[:5] if len(coordinates) >= 5 else None
                    if lat_part:
                        try:
                            lat_deg = int(lat_part[:2])
                            lat_min = int(lat_part[2:4])
                            lat_dir = lat_part[4]
                            latitude = lat_deg + lat_min / 60.0
                            if lat_dir in ('S', 's'):
                                latitude = -latitude
                        except (ValueError, IndexError):
                            pass

                    # Longitude: 00607E (006°07'E)
                    lon_part = coordinates[5:11] if len(coordinates) >= 11 else None
                    if lon_part:
                        try:
                            lon_deg = int(lon_part[:3])
                            lon_min = int(lon_part[3:5])
                            lon_dir = lon_part[5]
                            longitude = lon_deg + lon_min / 60.0
                            if lon_dir in ('W', 'w'):
                                longitude = -longitude
                        except (ValueError, IndexError):
                            pass

                    if len(coordinates) >= 14:
                        try:
                            radius_nm = int(coordinates[11:14])
                        except (ValueError, IndexError):
                            pass

        # Parse lettered fields
        location = None
        valid_from = None
        valid_to = None
        is_permanent = False
        schedule = None
        body = None
        lower_limit_text = None
        upper_limit_text = None

        a_match = re.search(r'A\)\s*([^\s]+)', icao_message)
        if a_match:
            location = a_match.group(1)

        b_match = re.search(r'B\)\s*(\d{10})', icao_message)
        if b_match:
            date_str = b_match.group(1)
            # Format: YYMMDDHHMM (UTC)
            try:
                year_val = 2000 + int(date_str[0:2]) if int(date_str[0:2]) < 50 else 1900 + int(date_str[0:2])
                month = int(date_str[2:4])
                day = int(date_str[4:6])
                hour = int(date_str[6:8])
                minute = int(date_str[8:10])
                valid_from = datetime(year_val, month, day, hour, minute)
            except (ValueError, IndexError):
                pass

        # C) field: either a 10-digit datetime or PERM.
        # "EST" suffix (meaning "estimated") is intentionally stripped — the datetime
        # is still valid per ICAO; the NOTAM remains in force until cancelled/replaced.
        c_match = re.search(r'C\)\s*(\d{10}|PERM)', icao_message)
        if c_match:
            date_str = c_match.group(1)
            if date_str == 'PERM':
                is_permanent = True
                valid_to = None
            else:
                is_permanent = False
                try:
                    year_val = 2000 + int(date_str[0:2]) if int(date_str[0:2]) < 50 else 1900 + int(date_str[0:2])
                    month = int(date_str[2:4])
                    day = int(date_str[4:6])
                    hour = int(date_str[6:8])
                    minute = int(date_str[8:10])
                    valid_to = datetime(year_val, month, day, hour, minute)
                except (ValueError, IndexError):
                    valid_to = None
                    is_permanent = False

        d_match = re.search(r'D\)\s*([^\n]+)', icao_message)
        if d_match:
            schedule = d_match.group(1).strip()

        e_match = re.search(r'E\)\s*(.*?)(?=\s*[F-G]\)|$)', icao_message, re.DOTALL)
        if e_match:
            body_text = e_match.group(1).strip()
            body = html.unescape(body_text)

        f_match = re.search(r'F\)\s*(.*?)(?=\s+[G-Z]\)|$)', icao_message, re.DOTALL)
        if f_match:
            lower_limit_text = f_match.group(1).strip()

        g_match = re.search(r'G\)\s*([^\n]+)', icao_message)
        if g_match:
            upper_limit_text = g_match.group(1).strip()

        # Parse FAA issue date
        issue_date = None
        if data.get('issueDate'):
            try:
                issue_date = cls._parse_faa_date(data['issueDate'])
            except (ValueError, AttributeError):
                pass

        # Construct the instance
        instance = cls(
            notam_id=notam_id,
            series=series,
            number=number,
            year=year,
            notam_type=notam_type,
            replaces_notam_id=replaces_notam_id,
            cancels_notam_id=cancels_notam_id,
            fir=fir,
            q_code=q_code,
            q_code_subject=q_code_subject,
            q_code_condition=q_code_condition,
            traffic=traffic,
            purpose=purpose,
            scope=scope,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            coordinates=coordinates,
            latitude=latitude,
            longitude=longitude,
            radius_nm=radius_nm,
            location=location,
            valid_from=valid_from,
            valid_to=valid_to,
            is_permanent=is_permanent,
            schedule=schedule,
            body=body,
            lower_limit_text=lower_limit_text,
            upper_limit_text=upper_limit_text,
            airport_code=data.get('facilityDesignator'),
            airport_name=data.get('airportName'),
            issue_date=issue_date,
            source=data.get('source'),
            source_type=data.get('sourceType'),
            raw_icao_message=icao_message,
            transaction_id=data.get('transactionID'),
            has_history=data.get('hasHistory', False),
            search_term=search_term,
        )

        # Priority score is recalculated now that all fields are set
        instance.priority_score = instance._calculate_priority_score()

        return instance

    @staticmethod
    def _parse_faa_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse FAA format date: MM/DD/YYYY HHMM."""
        if not date_str:
            return None

        try:
            # Strip trailing timezone indicators (EST, UTC, GMT) — these are
            # informational only; all NOTAM times are UTC regardless.
            date_str = re.sub(r'\s*(EST|UTC|GMT)$', '', date_str.strip())

            parts = date_str.split()
            if len(parts) >= 2:
                date_part = parts[0]   # MM/DD/YYYY
                time_part = parts[1]   # HHmm

                date_components = date_part.split('/')
                if len(date_components) == 3:
                    month = int(date_components[0])
                    day = int(date_components[1])
                    year = int(date_components[2])

                    if len(time_part) >= 4:
                        hour = int(time_part[0:2])
                        minute = int(time_part[2:4])
                    else:
                        hour = 0
                        minute = 0

                    return datetime(year, month, day, hour, minute)
        except (ValueError, IndexError, AttributeError):
            pass

        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for database storage or JSON export."""
        result = {}

        for key, value in asdict(self).items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, NotamType):
                result[key] = value.value
            else:
                result[key] = value

        # Computed properties are not dataclass fields — add them explicitly
        result['is_closure'] = self.is_closure
        result['is_drone_related'] = self.is_drone_related
        result['is_restriction'] = self.is_restriction
        result['is_trigger_notam'] = self.is_trigger_notam
        result['priority_score'] = self.priority_score

        return result

    def summary(self) -> str:
        """Generate human-readable summary suitable for ntfy alert body."""
        lines = []

        header = f"{self.notam_id} | {self.airport_code or self.location or 'Unknown'}"
        if self.airport_name:
            header += f" ({self.airport_name})"
        lines.append(header)
        lines.append("=" * len(header))

        type_str = f"Type: {self.notam_type.value}"
        if self.replaces_notam_id:
            type_str += f" (replaces {self.replaces_notam_id})"
        if self.cancels_notam_id:
            type_str += f" (cancels {self.cancels_notam_id})"
        lines.append(type_str)

        valid_str = "Valid: "
        if self.valid_from:
            valid_str += self.valid_from.strftime('%Y-%m-%d %H:%M UTC')
        if self.valid_to:
            valid_str += f" → {self.valid_to.strftime('%Y-%m-%d %H:%M UTC')}"
        elif self.is_permanent:
            valid_str += " → PERMANENT"
        lines.append(valid_str)

        if self.schedule:
            lines.append(f"Schedule: {self.schedule}")

        if self.q_code_subject or self.q_code_condition:
            q_str = "Q-Code: "
            if self.q_code_subject:
                q_str += self.q_code_subject
            if self.q_code_condition:
                q_str += f" — {self.q_code_condition}"
            lines.append(q_str)

        if self.body:
            body_preview = self.body.replace('\n', ' ').strip()
            if len(body_preview) > 200:
                body_preview = body_preview[:200] + "..."
            lines.append(f"\n{body_preview}")

        lines.append(f"\nPriority Score: {self.priority_score}")
        if self.is_closure:
            lines.append("⚠️ CLOSURE")
        if self.is_drone_related:
            lines.append("🚁 DRONE ACTIVITY")
        if self.is_restriction:
            lines.append("🚫 RESTRICTION")

        return "\n".join(lines)

    def __repr__(self) -> str:
        """Compact single-line representation."""
        flags = []
        if self.is_closure:
            flags.append("CLS")
        if self.is_drone_related:
            flags.append("DRN")
        if self.is_restriction:
            flags.append("RST")
        if self.is_permanent:
            flags.append("PERM")

        flag_str = f" [{','.join(flags)}]" if flags else ""

        return (
            f"<Notam {self.notam_id} "
            f"{self.airport_code or self.location or 'N/A'} "
            f"score={self.priority_score}{flag_str}>"
        )