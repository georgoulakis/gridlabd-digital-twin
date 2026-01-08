"""
Parsing utilities for handling GridLAB-D output formats and data conversion.
"""
import datetime
from typing import Optional


def safe_float(value: Optional[str]) -> Optional[float]:
    """
    Safely convert a string value to float, handling GridLAB-D output formats.
    
    Handles:
    - Comma-separated numbers
    - Complex numbers (extracts real part)
    - Leading plus signs
    
    Args:
        value: String value to convert, or None
        
    Returns:
        Float value if conversion succeeds, None otherwise
    """
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    # Remove commas and trailing imaginary parts
    cleaned = cleaned.replace(",", "")
    if "i" in cleaned:
        cleaned = cleaned.split("+")[0]
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    try:
        return float(cleaned)
    except Exception:
        return None


def parse_gridlabd_timestamp(raw_ts: str) -> datetime.datetime:
    """
    Parse GridLAB-D timestamp format to Python datetime.
    
    GridLAB-D outputs timestamps like '2024-07-01 00:00:00 PST'.
    This function extracts the date/time portion and converts to naive datetime.
    
    Args:
        raw_ts: Raw timestamp string from GridLAB-D output
        
    Returns:
        Datetime object (naive, UTC-equivalent)
    """
    if not raw_ts:
        return datetime.datetime.utcnow()
    parts = raw_ts.split()
    if len(parts) >= 2:
        candidate = " ".join(parts[:2])
    else:
        candidate = raw_ts
    try:
        return datetime.datetime.strptime(candidate, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.datetime.fromisoformat(candidate)
        except Exception:
            return datetime.datetime.utcnow()


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime.datetime]:
    """
    Parse ISO format datetime string to Python datetime.
    
    Args:
        value: ISO format datetime string (e.g., '2024-07-01T00:00:00')
        
    Returns:
        Datetime object if parsing succeeds, None otherwise
    """
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value)
    except Exception:
        return None

