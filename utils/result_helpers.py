"""
Helper functions for result ingestion, querying, and unit conversion.
"""
import os
import csv
import logging
from collections import defaultdict
from typing import Optional, Dict, Any, List, Literal
from fastapi import HTTPException
from psycopg2.extras import execute_values
from utils.parsing_helpers import safe_float, parse_gridlabd_timestamp, parse_iso_datetime
from utils.unit_converters import fahrenheit_to_celsius, wh_to_kwh
from utils.db_helpers import db_fetchall

LOG = logging.getLogger(__name__)


def ingest_result_timeseries(result_id: str, scenario_id: str, output_path: str, results_pool) -> int:
    """
    Parse GridLAB-D CSV output and persist per-property time-series into Postgres.
    
    Reads the CSV file, extracts property columns from the header (handling commented headers),
    and inserts each timestamp/property/value combination into the result_timeseries table.
    
    Args:
        result_id: UUID of the result record
        scenario_id: UUID of the scenario this result belongs to
        output_path: Full path to the GridLAB-D output CSV file
        results_pool: Database connection pool for results database
        
    Returns:
        Number of rows ingested (0 if file missing or parsing failed)
    """
    if not results_pool:
        LOG.warning("Results DB pool unavailable; skipping timeseries ingestion")
        return 0
    if not os.path.exists(output_path):
        LOG.warning("Output file missing for ingestion: %s", output_path)
        return 0

    header: List[str] = []
    rows_to_insert: List[tuple] = []

    with open(output_path, "r") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                candidate = stripped.lstrip("#").strip()
                if "," in candidate and not header:
                    header = [cell.strip() for cell in candidate.split(",")]
                    break
                continue
            header = [cell.strip() for cell in stripped.split(",")]
            break

        if not header:
            LOG.warning("No header detected in %s", output_path)
            return 0

        reader = csv.reader(f)
        for raw in reader:
            if not raw:
                continue
            timestamp = parse_gridlabd_timestamp(raw[0].strip())
            for idx, prop in enumerate(header[1:], start=1):
                raw_value = raw[idx].strip() if idx < len(raw) else ""
                rows_to_insert.append((
                    result_id,
                    scenario_id,
                    prop,
                    timestamp,
                    safe_float(raw_value),
                    raw_value or None
                ))

    if not rows_to_insert:
        return 0

    conn = results_pool.getconn()
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO result_timeseries (result_id, scenario_id, property, ts, value_numeric, value_text)
                VALUES %s
                """,
                rows_to_insert,
                page_size=1000
            )
        conn.commit()
    finally:
        results_pool.putconn(conn)

    LOG.info("Ingested %s timeseries rows for result %s", len(rows_to_insert), result_id)
    return len(rows_to_insert)


def convert_value_to_partner(property_name: str, value: Optional[float]) -> Optional[float]:
    """
    Convert a GridLAB-D value to partner units (SI/metric).
    
    Converts:
    - Temperature properties: Fahrenheit -> Celsius
    - Energy properties: Wh -> kWh
    
    Args:
        property_name: Name of the property (checked for keywords)
        value: Numeric value in GridLAB-D units
        
    Returns:
        Converted value in partner units, or original value if no conversion needed
    """
    if value is None:
        return None
    lname = property_name.lower()
    if "temperature" in lname or "setpoint" in lname:
        return fahrenheit_to_celsius(value)
    if "energy" in lname:
        return wh_to_kwh(value)
    return value


def fetch_result_series(result_id: str,
                       results_pool,
                       properties: Optional[List[str]] = None,
                       start_time: Optional[str] = None,
                       stop_time: Optional[str] = None,
                       fmt: Literal["gridlabd", "partner"] = "gridlabd") -> Dict[str, List[Dict[str, Any]]]:
    """
    Retrieve structured time-series data for a stored result from the database.
    
    Queries the result_timeseries table and returns data grouped by property name.
    Supports filtering by property names and time range, with optional unit conversion.
    
    Args:
        result_id: UUID of the result record
        results_pool: Database connection pool for results database
        properties: Optional list of property names to filter (e.g., ['house:total_load'])
        start_time: Optional ISO datetime string for start of time range
        stop_time: Optional ISO datetime string for end of time range
        fmt: Output format - 'gridlabd' (native units) or 'partner' (converted to SI/metric)
        
    Returns:
        Dictionary mapping property names to lists of {timestamp, value, raw} dictionaries
        
    Raises:
        HTTPException: 503 if database unavailable
    """
    if not results_pool:
        raise HTTPException(503, "Results DB unavailable")

    conditions = ["result_id = %s"]
    params: List[Any] = [result_id]

    if properties:
        conditions.append("property = ANY(%s)")
        params.append(properties)

    start_dt = parse_iso_datetime(start_time)
    stop_dt = parse_iso_datetime(stop_time)

    if start_dt:
        conditions.append("ts >= %s")
        params.append(start_dt)
    if stop_dt:
        conditions.append("ts <= %s")
        params.append(stop_dt)

    sql = f"""
        SELECT property, ts, value_numeric, value_text
        FROM result_timeseries
        WHERE {' AND '.join(conditions)}
        ORDER BY ts ASC
    """

    rows = db_fetchall(results_pool, sql, tuple(params))

    series_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ts = row["ts"]
        value = row["value_numeric"]
        if fmt == "partner":
            value = convert_value_to_partner(row["property"], value)
        if value is None:
            value = row["value_text"]
        series_map[row["property"]].append({
            "timestamp": ts.isoformat() if hasattr(ts, 'isoformat') else str(ts),
            "value": value,
            "raw": row["value_text"]
        })

    return series_map

