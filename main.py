# app/main.py
"""
FastAPI service for GridLAB-D Digital Twin configurations with dynamic appliance pattern generation
"""
import os
import sys
import time
import socket
import uuid
import json
import datetime
import shutil
from typing import Optional, Dict, Any, List, Literal
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from jinja2 import Template
from psycopg2.pool import SimpleConnectionPool
from utils.db_helpers import wait_for_port, make_pool, db_fetchone, db_fetchall, db_execute
from utils.genererate_consumption_utils import deep_merge, generate_appliance_csv
from utils.unit_converters import (
    convert_partner_config_to_gridlabd,
    detect_units
)
from utils.parsing_helpers import safe_float, parse_gridlabd_timestamp, parse_iso_datetime
from utils.partner_helpers import merge_overrides, ensure_config_id_from_partner, build_simulation_request_from_partner
from utils.result_helpers import ingest_result_timeseries, convert_value_to_partner, fetch_result_series

# Import your pattern generation functions
# Make sure appliance_pattern_generator.py is in the same directory or in PYTHONPATH

# ---------- Config / env ----------
# Change these from Docker service names to localhost
CONFIG_DB_HOST = os.getenv("CONFIG_DB_HOST", "localhost")  # Changed from "db_configs"
CONFIG_DB_PORT = int(os.getenv("CONFIG_DB_PORT", "5432"))
CONFIG_DB_NAME = os.getenv("CONFIG_DB_NAME", "configs_db")
CONFIG_DB_USER = os.getenv("CONFIG_DB_USER", "postgres")
CONFIG_DB_PASSWORD = os.getenv("CONFIG_DB_PASSWORD", "postgres")

RESULTS_DB_HOST = os.getenv("RESULTS_DB_HOST", "localhost")  # Changed from "db_results"
RESULTS_DB_PORT = int(os.getenv("RESULTS_DB_PORT", "5433"))  # Keep 5433 for second DB
RESULTS_DB_NAME = os.getenv("RESULTS_DB_NAME", "results_db")
RESULTS_DB_USER = os.getenv("RESULTS_DB_USER", "postgres")
RESULTS_DB_PASSWORD = os.getenv("RESULTS_DB_PASSWORD", "postgres")

# Update data directories for local development
DATA_DIR = os.getenv("DATA_DIR", "./data")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
RESULTS_DIR = os.path.join(DATA_DIR, "results")
SCENARIOS_DIR = os.path.join(DATA_DIR, "scenarios")
PATTERNS_BASE_DIR = os.getenv("PATTERNS_BASE_DIR", os.path.join(DATA_DIR, "patterns"))
TMY_BASE_DIR = os.getenv("TMY_BASE_DIR", os.path.join(DATA_DIR, "tmy"))
TEMPLATES_BASE_DIR = os.getenv("TEMPLATES_BASE_DIR", os.path.join(DATA_DIR, "templates"))

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(SCENARIOS_DIR, exist_ok=True)
os.makedirs(PATTERNS_BASE_DIR, exist_ok=True)
os.makedirs(TMY_BASE_DIR, exist_ok=True)
os.makedirs(TEMPLATES_BASE_DIR, exist_ok=True)

TMY_PROFILE_MAP = {
    "murcia": "murcia.csv",
    "aspra_spitia": "aspra_spitia.csv",
    "zagreb": "zagreb.csv",
    "dublin": "dublin.csv"
}


# ---------- Updated Template with Player Support ----------
GLM_TEMPLATE = """module tape;
module residential {
    implicit_enduses NONE;
};
module powerflow;
module climate;

#include "typical_light_yearly.glm";
#include "typical_fridge_yearly.glm";
#include "typical_misc_appliances_yearly.glm";
{% if solar_enabled %}module generators;{% endif %}

clock {
    timezone {{ timezone }};
    starttime '{{ start_time }}';
    stoptime '{{ stop_time }}';
}

{% if climate_csv_file %}
object csv_reader {
    name {{ climate_reader_name }};
    filename "{{ climate_csv_file }}";
}

object climate {
    tmyfile "{{ climate_csv_file }}";
    reader {{ climate_reader_name }};
};
{% endif %}

{% if custom_schedules %}
{% for schedule_name, schedule_data in custom_schedules.items() %}
schedule {{ schedule_name }} {
    {% for entry in schedule_data %}
    {{ entry.time }} {{ entry.value }};
    {% endfor %}
}
{% endfor %}
{% endif %}

object triplex_meter {
    name meter1;
    phases AS;
    nominal_voltage 120;
    
    {% if solar_enabled %}
    object inverter {
        name inverter1;
        phases S;
        parent meter1;
        inverter_type FOUR_QUADRANT;
        power_factor 1.0;
        
        object solar {
            name house_solar;
            parent inverter1;
            generator_mode SUPPLY_DRIVEN;
            generator_status ONLINE;
            panel_type SINGLE_CRYSTAL_SILICON;
            efficiency {{ solar_config.efficiency }};
            area {{ solar_config.area }};
        };
    };
    {% endif %}
    
    object house {
        name house;
        heating_setpoint {{ heating_setpoint }};
        cooling_setpoint {{ cooling_setpoint }};
        system_mode OFF;
        cooling_system_type {{ cooling_system_type }};
        design_cooling_setpoint {{ design_cooling_setpoint }};
        design_cooling_capacity {{ design_cooling_capacity }};
        {% if cooling_COP is defined %}cooling_COP {{ cooling_COP }};{% endif %}
        heating_system_type {{ heating_system_type }};
        design_heating_setpoint {{ design_heating_setpoint }};
        design_heating_capacity {{ design_heating_capacity }};
        {% if heating_COP is defined %}heating_COP {{ heating_COP }};{% endif %}
        thermostat_deadband {{ thermostat_deadband }};
        floor_area {{ floor_area }};
        number_of_stories {{ number_of_stories }};
        ceiling_height {{ ceiling_height }};
        envelope_UA {{ envelope_UA }};
        window_wall_ratio {{ window_wall_ratio }};
        number_of_doors {{ number_of_doors }};
        Rwall {{ Rwall }};
        Rwindows {{ Rwindows }};
        Rroof {{ Rroof }};
        Rfloor {{ Rfloor }};
        glazing_layers {{ glazing_layers }};
        
        {% if objects.waterheater %}
        {% for wh_name, wh_config in objects.waterheater.items() %}
        object waterheater {
            name {{ wh_name }};
            tank_volume {{ wh_config.tank_volume }};
            tank_UA {{ wh_config.tank_UA }};
            tank_setpoint {{ wh_config.tank_setpoint }};
            heating_element_capacity {{ wh_config.heating_element_capacity }};
            location {{ wh_config.location | default('INSIDE') }};
            heat_mode {{ wh_config.heat_mode | default('ELECTRIC') }};
            water_demand {{ wh_config.water_demand }};
            impedance_fraction {{ wh_config.impedance_fraction }};
            power_fraction {{ wh_config.power_fraction }};
            power_factor {{ wh_config.power_factor }};
        };
        {% endfor %}
        {% endif %}
        
        {% if objects.lights %}
        {% for name, L in objects.lights.items() %}
        object ZIPload {
            name {{ name }};
            parent house;
            base_power yearly_lighting*{{ L.installed_kw }};
            power_pf {{ L.power_pf }};
            heatgain_fraction 1.0;
            impedance_fraction 0.0;
            current_fraction 0.0;
            power_fraction 1.0;
            is_240 FALSE;
        };
        {% endfor %}
        {% endif %}
        
        {% if objects.misc_appliances %}
        {% for name, M in objects.misc_appliances.items() %}
        object ZIPload {
            name {{ name }};
            parent house;
            base_power yearly_misc_appliances*{{ M.base_power }};
            power_pf {{ M.power_pf | default(0.95) }};
            heatgain_fraction {{ M.heatgain_fraction | default(0.3) }};
            impedance_fraction {{ M.impedance_fraction | default(0.1) }};
            current_fraction {{ M.current_fraction | default(0.0) }};
            power_fraction {{ M.power_fraction | default(0.9) }};
            is_240 {{ M.is_240 | default('FALSE') }};
        };
        {% endfor %}
        {% endif %}
        
        {% if objects.appliances %}
        {% for appliance_name, appliance_config in objects.appliances.items() %}
        object ZIPload {
            name {{ appliance_name }};
            parent house;
            {% if appliance_config.player_file %}
            object player {
                property base_power;
                file "{{ appliance_config.player_file }}";
                loop 1;
            };
            {% elif appliance_config.base_power %}
            base_power {{ appliance_config.base_power }};
            {% endif %}
            heatgain_fraction {{ appliance_config.heatgain_fraction }};
            power_pf {{ appliance_config.power_pf }};
            impedance_fraction {{ appliance_config.impedance_fraction }};
            current_fraction {{ appliance_config.current_fraction }};
            power_fraction {{ appliance_config.power_fraction }};
            is_240 {{ appliance_config.is_240 }};
        };
        {% endfor %}
        {% endif %}
        
        // Refrigerator - always included with yearly schedule
        object ZIPload {
            name refrigerator;
            parent house;
            base_power yearly_refrigerator*0.15;
            heatgain_fraction 0.90;
            power_pf 0.80;
            impedance_fraction 0.10;
            current_fraction 0.60;
            power_fraction 0.30;
            is_240 FALSE;
        };
        
        object multi_recorder {
            property {% for prop in output_properties %}{{ prop }}{% if not loop.last %},{% endif %}{% endfor %};
            file "{{ output_file }}";
            interval {{ recording_interval }};
            limit {{ recording_limit }};
        };
    };
}
"""





# ---------- FastAPI app ----------
from fastapi import FastAPI
import logging
import uvicorn
import sys

app = FastAPI(title="api")

LOG = logging.getLogger(__name__)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
LOG= logging.getLogger(__name__)
LOG.addHandler(handler)
LOG.setLevel(logging.INFO)

LOG.info("API is starting up")
LOG.info(uvicorn.Config.asgi_version)

app = FastAPI(title="GLM Digital Twin Service")

config_pool: Optional[SimpleConnectionPool] = None
results_pool: Optional[SimpleConnectionPool] = None

# ---------- Pydantic models ----------
class ConfigCreate(BaseModel):
    name: str
    config: Dict[str, Any]

class ApplianceTemplateCreate(BaseModel):
    name: str
    appliance_type: str
    template_config: Dict[str, Any]

class ConfigReplace(BaseModel):
    name: Optional[str] = None
    config: Dict[str, Any]

class AppliancePattern(BaseModel):
    """Configuration for dynamic appliance pattern generation - all fields optional for overrides"""
    nominal_power: Optional[float] = None  # Watts
    duration_min: Optional[float] = None  # Minutes per activation
    activations_per_day: Optional[int] = None  # Number of times appliance runs per day
    generation_method: Optional[str] = None  # 'scaling', 'weighted', 'interpolate', 'dtw'
    baseline: Optional[float] = None
    timestep_native: Optional[int] = None
    output_timestep: Optional[int] = None
    pattern_dir: Optional[str] = None  # e.g., 'washing_machine_patterns'
    seed: Optional[int] = None
    heatgain_fraction: Optional[float] = None
    power_pf: Optional[float] = None
    impedance_fraction: Optional[float] = None
    current_fraction: Optional[float] = None
    power_fraction: Optional[float] = None
    is_240: Optional[str] = None
    schedule: Optional[Dict[str, Any]] = None  # Probabilistic weekly schedule override

class SimulationRequest(BaseModel):
    """Request to run a simulation scenario"""
    cfg_id: str  # Config ID from database
    start_time: str  # 'YYYY-MM-DD HH:MM:SS'
    stop_time: str  # 'YYYY-MM-DD HH:MM:SS'
    output_properties: Optional[List[str]] = None
    appliance_patterns: Optional[Dict[str, AppliancePattern]] = None  # appliance_name -> pattern config
    overrides: Optional[Dict[str, Any]] = None  # Any other config overrides

class PartnerHouseholdRef(BaseModel):
    """Reference or inline payload for partner-provided household configs"""
    config_id: Optional[str] = None
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

class PartnerScenarioSettings(BaseModel):
    start_time: str
    stop_time: str
    interval_seconds: Optional[int] = 60
    output_properties: Optional[List[str]] = None
    recording_limit: Optional[int] = None

class PartnerExecutionSettings(BaseModel):
    run_immediately: bool = True
    return_results: bool = True
    result_format: Literal["gridlabd", "partner"] = "partner"

class PartnerSimulationRequest(BaseModel):
    partner_request_id: Optional[str] = None
    household: PartnerHouseholdRef
    scenario: PartnerScenarioSettings
    overrides: Optional[Dict[str, Any]] = None
    appliances: Optional[Dict[str, AppliancePattern]] = None
    execution: PartnerExecutionSettings = PartnerExecutionSettings()


# ---------- Helper utilities ----------
def _resolve_climate_profile(merged_config: Dict[str, Any]) -> Optional[str]:
    """Determine which climate profile (CSV) should be used for this scenario."""
    climate_cfg = merged_config.get('climate') if isinstance(merged_config.get('climate'), dict) else {}

    explicit_csv = (
        merged_config.get('climate_csv')
        or climate_cfg.get('csv')
        or climate_cfg.get('csv_file')
        or climate_cfg.get('tmy_csv')
        or climate_cfg.get('file')
    )
    if isinstance(explicit_csv, str) and explicit_csv.strip():
        return explicit_csv.strip()

    candidates = [
        merged_config.get('climate_profile'),
        merged_config.get('pilot'),
        climate_cfg.get('profile'),
        climate_cfg.get('pilot'),
        merged_config.get('location'),
    ]

    for candidate in candidates:
        if not candidate or not isinstance(candidate, str):
            continue
        key = candidate.lower().strip()
        if key in TMY_PROFILE_MAP:
            return TMY_PROFILE_MAP[key]
        if key.endswith('.csv'):
            return candidate
    return None


def _attach_climate_assets(merged_config: Dict[str, Any], scenario_dir: str, scenario_id: str):
    """
    Copy the appropriate climate CSV into the scenario directory and set template variables.
    
    Requires a pilot to be specified in the config. No fallback - pilot must be one of:
    murcia, aspra_spitia, zagreb, or dublin.
    """
    csv_candidate = _resolve_climate_profile(merged_config)
    if not csv_candidate:
        raise HTTPException(
            400,
            "Pilot must be specified. Provide 'pilot' or 'climate_profile' in config. "
            f"Valid pilots: {', '.join(TMY_PROFILE_MAP.keys())}"
        )

    if os.path.isabs(csv_candidate) and os.path.exists(csv_candidate):
        source_path = csv_candidate
    else:
        source_path = os.path.join(TMY_BASE_DIR, csv_candidate)

    if not os.path.exists(source_path):
        raise HTTPException(
            400,
            f"Climate CSV '{csv_candidate}' not found for pilot. "
            f"Place it under {TMY_BASE_DIR} or provide an absolute path. "
            f"Valid pilots: {', '.join(TMY_PROFILE_MAP.keys())}"
        )

    dest_name = os.path.basename(source_path)
    dest_path = os.path.join(scenario_dir, dest_name)
    if os.path.abspath(source_path) != os.path.abspath(dest_path):
        shutil.copy2(source_path, dest_path)

    merged_config['climate_csv_file'] = dest_name
    merged_config['climate_reader_name'] = f"climate_reader_{scenario_id[:8]}"


def _attach_lighting_schedule(scenario_dir: str):
    """
    Copy the typical_light_yearly.glm file into the scenario directory.
    
    This file contains the yearly_lighting schedule that is referenced in the GLM template.
    The file is copied from the templates directory if it exists there, otherwise it will
    be skipped if not found (non-fatal).
    """
    light_schedule_filename = "typical_light_yearly.glm"
    source_path = os.path.join(TEMPLATES_BASE_DIR, light_schedule_filename)
    dest_path = os.path.join(scenario_dir, light_schedule_filename)
    
    # Check if source file exists in templates directory
    if os.path.exists(source_path):
        if os.path.abspath(source_path) != os.path.abspath(dest_path):
            shutil.copy2(source_path, dest_path)
            LOG.info("Copied lighting schedule to scenario directory: %s", dest_path)
    else:
        # Try to find it in an existing scenario as fallback
        for house_name in os.listdir(SCENARIOS_DIR):
            house_path = os.path.join(SCENARIOS_DIR, house_name)
            if not os.path.isdir(house_path):
                continue
            for existing_scenario_id in os.listdir(house_path):
                existing_scenario_path = os.path.join(house_path, existing_scenario_id)
                fallback_path = os.path.join(existing_scenario_path, light_schedule_filename)
                if os.path.exists(fallback_path):
                    shutil.copy2(fallback_path, dest_path)
                    LOG.info("Copied lighting schedule from existing scenario to: %s", dest_path)
                    return
        LOG.warning("typical_light_yearly.glm not found in templates directory. Please ensure it exists in %s", TEMPLATES_BASE_DIR)


def _attach_fridge_schedule(scenario_dir: str):
    """
    Copy the typical_fridge_yearly.glm file into the scenario directory.
    
    This file contains the yearly_fridge schedule that is referenced in the GLM template.
    The file is copied from the templates directory if it exists there, otherwise it will
    be skipped if not found (non-fatal).
    """
    fridge_schedule_filename = "typical_fridge_yearly.glm"
    source_path = os.path.join(TEMPLATES_BASE_DIR, fridge_schedule_filename)
    dest_path = os.path.join(scenario_dir, fridge_schedule_filename)
    
    # Check if source file exists in templates directory
    if os.path.exists(source_path):
        if os.path.abspath(source_path) != os.path.abspath(dest_path):
            shutil.copy2(source_path, dest_path)
            LOG.info("Copied refrigerator schedule to scenario directory: %s", dest_path)
    else:
        # Try to find it in an existing scenario as fallback
        for house_name in os.listdir(SCENARIOS_DIR):
            house_path = os.path.join(SCENARIOS_DIR, house_name)
            if not os.path.isdir(house_path):
                continue
            for existing_scenario_id in os.listdir(house_path):
                existing_scenario_path = os.path.join(house_path, existing_scenario_id)
                fallback_path = os.path.join(existing_scenario_path, fridge_schedule_filename)
                if os.path.exists(fallback_path):
                    shutil.copy2(fallback_path, dest_path)
                    LOG.info("Copied refrigerator schedule from existing scenario to: %s", dest_path)
                    return
        LOG.warning("typical_fridge_yearly.glm not found in templates directory. Please ensure it exists in %s", TEMPLATES_BASE_DIR)


def _attach_misc_appliances_schedule(scenario_dir: str):
    """
    Copy the typical_misc_appliances_yearly.glm file into the scenario directory.
    
    This file contains the yearly_misc_appliances schedule that is referenced in the GLM template.
    The file is copied from the templates directory if it exists there, otherwise it will
    be skipped if not found (non-fatal).
    """
    misc_appliances_schedule_filename = "typical_misc_appliances_yearly.glm"
    source_path = os.path.join(TEMPLATES_BASE_DIR, misc_appliances_schedule_filename)
    dest_path = os.path.join(scenario_dir, misc_appliances_schedule_filename)
    
    # Check if source file exists in templates directory
    if os.path.exists(source_path):
        if os.path.abspath(source_path) != os.path.abspath(dest_path):
            shutil.copy2(source_path, dest_path)
            LOG.info("Copied misc appliances schedule to scenario directory: %s", dest_path)
    else:
        # Try to find it in an existing scenario as fallback
        for house_name in os.listdir(SCENARIOS_DIR):
            house_path = os.path.join(SCENARIOS_DIR, house_name)
            if not os.path.isdir(house_path):
                continue
            for existing_scenario_id in os.listdir(house_path):
                existing_scenario_path = os.path.join(house_path, existing_scenario_id)
                fallback_path = os.path.join(existing_scenario_path, misc_appliances_schedule_filename)
                if os.path.exists(fallback_path):
                    shutil.copy2(fallback_path, dest_path)
                    LOG.info("Copied misc appliances schedule from existing scenario to: %s", dest_path)
                    return
        LOG.warning("typical_misc_appliances_yearly.glm not found in templates directory. Please ensure it exists in %s", TEMPLATES_BASE_DIR)


# ---------- Startup / Shutdown ----------
@app.on_event("startup")
def on_startup():
    global config_pool, results_pool
    
    # Optional: You can keep the port check but reduce timeout for local development
    if not wait_for_port(CONFIG_DB_HOST, CONFIG_DB_PORT, timeout=10):  # Reduced timeout
        LOG.warning(f"Config DB not immediately reachable at {CONFIG_DB_HOST}:{CONFIG_DB_PORT}")
    
    if not wait_for_port(RESULTS_DB_HOST, RESULTS_DB_PORT, timeout=10):  # Reduced timeout
        LOG.warning(f"Results DB not immediately reachable at {RESULTS_DB_HOST}:{RESULTS_DB_PORT}")
    
    try:
        config_pool = make_pool(CONFIG_DB_HOST, CONFIG_DB_PORT, CONFIG_DB_NAME, CONFIG_DB_USER, CONFIG_DB_PASSWORD)
        results_pool = make_pool(RESULTS_DB_HOST, RESULTS_DB_PORT, RESULTS_DB_NAME, RESULTS_DB_USER, RESULTS_DB_PASSWORD)
        LOG.info("DB pools created successfully")
    except Exception as e:
        LOG.error("Error creating DB pools: %s", e)
        # Don't raise immediately, let the app start and retry later

@app.on_event("shutdown")
def on_shutdown():
    global config_pool, results_pool
    try:
        if config_pool:
            config_pool.closeall()
        if results_pool:
            results_pool.closeall()
        print("DB pools closed")
    except Exception as e:
        print("Error closing pools:", e, file=sys.stderr)

# ---------- Config endpoints (unchanged) ----------
@app.post("/configs", status_code=201)
def create_config(payload: ConfigCreate):
    """
    Create a new household configuration.
    
    Accepts a household configuration in JSON format. Automatically detects if the config
    uses partner units (SI/metric) and converts them to GridLAB-D units (imperial).
    
    The configuration is stored in the configs database with a unique UUID and version 1.
    
    Args:
        payload: ConfigCreate object containing:
            - name: Human-readable name for the configuration
            - config: Dictionary containing household parameters (floor_area, setpoints, etc.)
    
    Returns:
        Dictionary with the created config's ID (UUID)
        
    Raises:
        HTTPException: 503 if database pool not initialized
    """
    global config_pool
    if not config_pool:
        raise HTTPException(503, "DB pool not initialized")
    
     # Detect and convert units
    units = detect_units(payload.config)
    LOG.info(f"Detected units: {units}")
    
    if units == 'partner' or units == 'unknown':
        LOG.info("Converting partner units to GridLAB-D units")
        converted_config = convert_partner_config_to_gridlabd(payload.config)
    else:
        converted_config = payload.config
    
    cfg_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    sql = "INSERT INTO configs (id, name, created_at, config, version) VALUES (%s,%s,%s,%s,%s)"
    db_execute(config_pool, sql, (cfg_id, payload.name, now, json.dumps(converted_config), 1))
    return {"id": cfg_id}

@app.get("/configs")
def list_configs():
    """
    List all stored household configurations.
    
    Returns a list of all configurations in the database, ordered by creation date
    (most recent first). Includes ID, name, creation timestamp, and version.
    
    Returns:
        List of dictionaries containing config metadata (id, name, created_at, version)
    """
    global config_pool
    rows = db_fetchall(config_pool, "SELECT id, name, created_at, version FROM configs ORDER BY created_at DESC")
    return rows

@app.get("/configs/{cfg_id}")
def get_config(cfg_id: str):
    """
    Retrieve a specific household configuration by ID.
    
    Args:
        cfg_id: UUID of the configuration to retrieve
    
    Returns:
        Dictionary containing full config details (id, name, created_at, config JSON, version)
        
    Raises:
        HTTPException: 404 if config not found
    """
    row = db_fetchone(config_pool, "SELECT id, name, created_at, config, version FROM configs WHERE id = %s", (cfg_id,))
    if not row:
        raise HTTPException(404, "Config not found")
    return row

@app.put("/configs/{cfg_id}")
def replace_config(cfg_id: str, payload: ConfigReplace):
    """
    Replace an existing configuration entirely.
    
    Replaces the entire configuration with new data. The version number is incremented.
    Optionally updates the name if provided.
    
    Args:
        cfg_id: UUID of the configuration to replace
        payload: ConfigReplace object containing:
            - name: Optional new name (if None, keeps existing name)
            - config: Complete new configuration dictionary
    
    Returns:
        Dictionary with config ID and status
        
    Raises:
        HTTPException: 404 if config not found
    """
    now = datetime.datetime.utcnow().isoformat()
    name_to_set = payload.name
    
    existing = db_fetchone(config_pool, "SELECT id FROM configs WHERE id=%s", (cfg_id,))
    if not existing:
        raise HTTPException(404, "Config not found")
    
    db_execute(config_pool, "UPDATE configs SET config=%s, name=COALESCE(%s,name), version=version+1 WHERE id=%s",
               (json.dumps(payload.config), name_to_set, cfg_id))
    return {"id": cfg_id, "status": "replaced"}

@app.patch("/configs/{cfg_id}")
def patch_config(cfg_id: str, partial: Dict[str, Any]):
    """
    Partially update a configuration using deep merge.
    
    Merges the provided partial configuration into the existing one. Only the fields
    provided in the patch are updated; all other fields remain unchanged.
    The version number is incremented.
    
    Args:
        cfg_id: UUID of the configuration to patch
        partial: Dictionary containing fields to update (can be nested)
                 OR dictionary with 'config' key containing the partial config
    
    Returns:
        Dictionary with config ID and new version number
        
    Raises:
        HTTPException: 404 if config not found, 400 if payload is not a valid object
    """
    row = db_fetchone(config_pool, "SELECT config, version FROM configs WHERE id=%s", (cfg_id,))
    if not row:
        raise HTTPException(404, "Config not found")
    
    existing_config = row["config"] if isinstance(row["config"], dict) else json.loads(row["config"])
    patch_body = partial.get("config") if "config" in partial else partial
    
    if not isinstance(patch_body, dict):
        raise HTTPException(400, "Patch payload must be a JSON object")
    
    merged = deep_merge(existing_config, patch_body)
    db_execute(config_pool, "UPDATE configs SET config=%s, version=version+1 WHERE id=%s",
               (json.dumps(merged), cfg_id))
    return {"id": cfg_id, "version": (row["version"] + 1)}

@app.delete("/configs/{cfg_id}")
def delete_config(cfg_id: str):
    """
    Delete a household configuration.
    
    Permanently removes the configuration from the database. This action cannot be undone.
    
    Args:
        cfg_id: UUID of the configuration to delete
    
    Returns:
        Dictionary with config ID and deletion status
    """
    db_execute(config_pool, "DELETE FROM configs WHERE id=%s", (cfg_id,))
    return {"id": cfg_id, "status": "deleted"}





# ---- Logging Configuration ----




@app.post("/simulations", status_code=201)
def create_simulation(request: SimulationRequest):
    """
    Create a simulation scenario from a household configuration.
    
    This endpoint orchestrates the scenario creation process:
    1. Loads the base household configuration from the database
    2. Loads appliance templates from the config (authoritative defaults)
    3. Applies any provided overrides from request.appliance_patterns
    4. Generates CSV files for dynamic appliances using pattern generation
    5. Renders a GLM file referencing the generated player files
    6. Saves scenario metadata and returns scenario information
    
    The scenario is created but not executed. Use /simulations/{scenario_id}/execute to run it.
    
    Args:
        request: SimulationRequest containing:
            - cfg_id: UUID of the household configuration to use
            - start_time: Simulation start time (format: 'YYYY-MM-DD HH:MM:SS')
            - stop_time: Simulation stop time (format: 'YYYY-MM-DD HH:MM:SS')
            - output_properties: Optional list of GridLAB-D properties to record
            - appliance_patterns: Optional dict of appliance_name -> AppliancePattern overrides
            - overrides: Optional dict of general config overrides
    
    Returns:
        Dictionary containing:
            - scenario_id: UUID of the created scenario
            - scenario_dir: Full path to scenario directory
            - glm_file: Full path to generated GLM file
            - generated_csvs: List of generated appliance CSV filenames
            - metadata: Complete scenario metadata dictionary
        
    Raises:
        HTTPException: 404 if config not found, 500 if GLM rendering fails
    """
    LOG.info("Received simulation request: cfg_id=%s start=%s stop=%s",
             request.cfg_id, request.start_time, request.stop_time)

    # --- small helpers local to this endpoint ---
    def _coerce_number_from_str(val):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return val
        if isinstance(val, str):
            try:
                return int(val) if val.isdigit() else float(val)
            except Exception:
                return val
        return val

    def _coerce_bool_from_str(val):
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.strip().upper() in ("TRUE", "1", "YES", "ON")
        return None

    def normalize_appliance_template(template: dict) -> dict:
        """Return a sanitized copy with coerced types and sensible defaults (non-destructive)."""
        tpl = dict(template) if isinstance(template, dict) else {}
        for k in ('nominal_power', 'duration_min', 'activations_per_day', 'baseline', 'timestep_native', 'output_timestep', 'seed'):
            if k in tpl:
                tpl[k] = _coerce_number_from_str(tpl.get(k))
        if 'is_240' in tpl:
            tpl['is_240'] = _coerce_bool_from_str(tpl.get('is_240'))
        tpl.setdefault('baseline', 0)
        tpl.setdefault('timestep_native', 7)
        tpl.setdefault('output_timestep', 60)
        tpl.setdefault('activations_per_day', tpl.get('activations_per_day', 1))
        return tpl

    # --- Load base config from DB ---
    row = db_fetchone(config_pool, "SELECT id, name, config FROM configs WHERE id = %s", (request.cfg_id,))
    if not row:
        LOG.warning("Config not found: %s", request.cfg_id)
        raise HTTPException(404, "Config not found")

    base_config = row["config"] if isinstance(row["config"], dict) else json.loads(row["config"])
    config_name = row["name"]
    LOG.info("Loaded base config '%s' (id=%s)", config_name, request.cfg_id)

    # --- prepare scenario directory ---
    scenario_id = str(uuid.uuid4())
    house_dir = os.path.join(SCENARIOS_DIR, config_name)
    scenario_dir = os.path.join(house_dir, scenario_id)
    os.makedirs(scenario_dir, exist_ok=True)
    LOG.info("Created scenario directory: %s", scenario_dir)

    # --- start merging config ---
    merged_config = dict(base_config)  # shallow copy of base config
    merged_config['start_time'] = request.start_time
    merged_config['stop_time'] = request.stop_time

    # output properties selection fallback
    if request.output_properties:
        merged_config['output_properties'] = request.output_properties
    elif 'default_simulation' in merged_config and 'output_properties' in merged_config['default_simulation']:
        merged_config['output_properties'] = merged_config['default_simulation']['output_properties']
    else:
        merged_config.setdefault('output_properties', ['house:total_load'])

    if 'default_simulation' in merged_config:
        merged_config.setdefault('recording_interval', merged_config['default_simulation'].get('recording_interval', 60))
        merged_config.setdefault('recording_limit', merged_config['default_simulation'].get('recording_limit', 1440))
### TO DO : Change units to where applicable
    # --- Apply general overrides from request ---
    if request.overrides:
        
        merged_config = deep_merge(merged_config, request.overrides)
        LOG.info("Applied request.overrides to merged_config: %s", request.overrides)

    LOG.debug("Merged config ready (partial view): %s", {k: merged_config.get(k) for k in ('start_time','stop_time','output_properties','default_simulation')})

    # --- Load appliance_templates from DB config (authoritative defaults) ---
    appliances_to_generate = {}
    if 'appliance_templates' in merged_config and isinstance(merged_config['appliance_templates'], dict):
        for appliance_name, template in merged_config['appliance_templates'].items():
            try:
                normalized = normalize_appliance_template(template if isinstance(template, dict) else dict(template))
            except Exception:
                normalized = dict(template) if isinstance(template, dict) else {}
            appliances_to_generate[appliance_name] = normalized
    LOG.info("Appliances loaded from DB templates: %s", list(appliances_to_generate.keys()))

    # --- Apply request-provided overrides (only non-None keys) ---
    if request.appliance_patterns:
        LOG.info("Request provided appliance_patterns: %s", list(request.appliance_patterns.keys()))
        for appliance_name, pattern_model in request.appliance_patterns.items():
            base_template = appliances_to_generate.get(appliance_name, {})
            if hasattr(pattern_model, "dict"):
                provided = {k: v for k, v in pattern_model.dict().items() if v is not None}
            else:
                provided = {k: v for k, v in dict(pattern_model).items() if v is not None}

            # merge provided onto base_template (base wins for missing keys)
            merged_pattern = deep_merge(dict(base_template), provided)
            # normalize merged result
            merged_pattern = normalize_appliance_template(merged_pattern)
            appliances_to_generate[appliance_name] = merged_pattern
            LOG.info("Final merged pattern for '%s': %s", appliance_name, merged_pattern)

    LOG.info("Appliances to generate CSVs for: %s", list(appliances_to_generate.keys()))

    # --- Generate CSVs for each appliance ---
    generated_files = []
    generation_errors = {}

    if appliances_to_generate:
        merged_config.setdefault('objects', {})
        merged_config['objects'].setdefault('appliances', {})

        for appliance_name, pattern_config in appliances_to_generate.items():
            try:
                # pattern_config should already be a normalized dict; make sure it's a plain dict
                pattern_dict = dict(pattern_config) if isinstance(pattern_config, dict) else {}

                LOG.info("Preparing to generate CSV for '%s' pattern_dict(before final defaults)=%s", appliance_name, pattern_dict)

                # default pattern_dir if missing
                pattern_dict.setdefault('pattern_dir', f'{appliance_name}_patterns')

                # DB template fallback lookup (original templates from merged_config)
                db_tpl = {}
                if 'appliance_templates' in merged_config and isinstance(merged_config['appliance_templates'], dict):
                    db_tpl = merged_config['appliance_templates'].get(appliance_name, {}) or {}

                # Ensure essential numeric fields: prefer pattern_dict -> db_tpl -> hard-coded
                pattern_dict['nominal_power'] = pattern_dict.get('nominal_power') or _coerce_number_from_str(db_tpl.get('nominal_power')) or 2000
                pattern_dict['duration_min'] = pattern_dict.get('duration_min') or _coerce_number_from_str(db_tpl.get('duration_min')) or 90
                pattern_dict['activations_per_day'] = pattern_dict.get('activations_per_day') or _coerce_number_from_str(db_tpl.get('activations_per_day')) or 1
                # baseline and timesteps (explicit None => use db_tpl or fallback)
                pattern_dict['baseline'] = 0 if pattern_dict.get('baseline') is None else pattern_dict.get('baseline')
                pattern_dict['timestep_native'] = pattern_dict.get('timestep_native') or _coerce_number_from_str(db_tpl.get('timestep_native')) or 7
                pattern_dict['output_timestep'] = pattern_dict.get('output_timestep') or _coerce_number_from_str(db_tpl.get('output_timestep')) or 60
                # ensure generation_method
                if not pattern_dict.get('generation_method'):
                    pattern_dict['generation_method'] = (db_tpl.get('generation_method') if isinstance(db_tpl, dict) else None) or 'scaling'

                LOG.info("Final pattern_dict for generator for '%s'=%s", appliance_name, pattern_dict)

                # Pattern directory check (helpful for local / Docker path problems)
                pattern_full_path = os.path.join(PATTERNS_BASE_DIR, pattern_dict['pattern_dir'])
                if not os.path.exists(pattern_full_path):
                    # try a couple of helpful fallbacks
                    alt_candidates = [
                        os.path.join(PATTERNS_BASE_DIR, appliance_name),
                        os.path.join(PATTERNS_BASE_DIR, pattern_dict['pattern_dir'].lower()),
                        os.path.join(PATTERNS_BASE_DIR, pattern_dict['pattern_dir'].replace(" ", "_"))
                    ]
                    for p in alt_candidates:
                        if os.path.exists(p):
                            pattern_full_path = p
                            break

                if not os.path.exists(pattern_full_path):
                    raise FileNotFoundError(f"Pattern directory not found: {pattern_full_path}")

                # Generate CSV (this function is expected to raise on failure)
                csv_filename = generate_appliance_csv(
                    appliance_name=appliance_name,
                    appliance_config=pattern_dict,
                    start_time=request.start_time,
                    stop_time=request.stop_time,
                    scenario_dir=scenario_dir
                )

                LOG.info("Generated CSV for '%s' -> %s", appliance_name, csv_filename)
                generated_files.append(csv_filename)

                # Update merged_config objects to reference the player_file
                merged_config['objects']['appliances'].setdefault(appliance_name, {})
                merged_config['objects']['appliances'][appliance_name]['player_file'] = csv_filename
                merged_config['objects']['appliances'][appliance_name].setdefault('heatgain_fraction', pattern_dict.get('heatgain_fraction', 0.05))
                merged_config['objects']['appliances'][appliance_name].setdefault('power_pf', pattern_dict.get('power_pf', 0.95))
                merged_config['objects']['appliances'][appliance_name].setdefault('impedance_fraction', pattern_dict.get('impedance_fraction', 0.1))
                merged_config['objects']['appliances'][appliance_name].setdefault('current_fraction', pattern_dict.get('current_fraction', 0.0))
                merged_config['objects']['appliances'][appliance_name].setdefault('power_fraction', pattern_dict.get('power_fraction', 0.9))
                merged_config['objects']['appliances'][appliance_name].setdefault('is_240', pattern_dict.get('is_240', True))
                merged_config['objects']['appliances'][appliance_name].pop('base_power', None)

            except Exception as e:
                LOG.exception("Failed to generate pattern for %s: %s", appliance_name, e)
                generation_errors[appliance_name] = str(e)
                # continue generating other appliances; we'll surface errors in metadata

    # --- Cleanup / defaults reassurance ---
    merged_config.setdefault('output_properties', ['house:total_load'])
    merged_config.setdefault('recording_interval', 60)
    merged_config.setdefault('recording_limit', 1440)

    # Attach climate CSV assets if configured
    _attach_climate_assets(merged_config, scenario_dir, scenario_id)
    
    # Copy lighting schedule file to scenario directory
    _attach_lighting_schedule(scenario_dir)
    
    # Copy refrigerator schedule file to scenario directory
    _attach_fridge_schedule(scenario_dir)
    
    # Copy misc appliances schedule file to scenario directory
    _attach_misc_appliances_schedule(scenario_dir)

    # set output file
    output_csv = f"results_{scenario_id[:8]}.csv"
    merged_config['output_file'] = output_csv

    # Render GLM
    glm_filename = f"scenario_{scenario_id[:8]}.glm"
    glm_path = os.path.join(scenario_dir, glm_filename)
    try:
        template = Template(GLM_TEMPLATE)
        glm_content = template.render(**merged_config)
        with open(glm_path, 'w') as f:
            f.write(glm_content)
        LOG.info("Rendered GLM file: %s", glm_path)
    except Exception as e:
        LOG.exception("GLM template rendering failed")
        raise HTTPException(500, f"GLM template rendering failed: {str(e)}")

    # Write metadata (include any generation errors)
    metadata = {
        'scenario_id': scenario_id,
        'config_id': request.cfg_id,
        'config_name': config_name,
        'start_time': request.start_time,
        'stop_time': request.stop_time,
        'created_at': datetime.datetime.utcnow().isoformat(),
        'glm_file': glm_filename,
        'output_file': output_csv,
        'generated_csvs': generated_files,
        'generation_errors': generation_errors,
        'scenario_dir': scenario_dir
    }
    metadata_path = os.path.join(scenario_dir, 'metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    if generation_errors:
        LOG.warning("Scenario created with errors: %s", generation_errors)
    else:
        LOG.info("Scenario created successfully: %s (generated_files=%s)", scenario_id, generated_files)

    return {
        'scenario_id': scenario_id,
        'scenario_dir': scenario_dir,
        'glm_file': glm_path,
        'generated_csvs': generated_files,
        'metadata': metadata
    }


@app.post("/partner/simulations", status_code=201)
def create_partner_simulation(request: PartnerSimulationRequest):
    """
    Partner-friendly endpoint to create and optionally execute a simulation.
    
    This is a simplified API for partners that handles the full workflow:
    1. Resolves or creates a household configuration (by ID, name, or inline config)
    2. Creates a simulation scenario
    3. Optionally executes the GridLAB-D simulation immediately
    4. Optionally returns structured time-series results
    
    Partners only need to provide minimal information (household reference, time window,
    output properties) and the service handles the rest.
    
    Args:
        request: PartnerSimulationRequest containing:
            - partner_request_id: Optional partner tracking ID
            - household: PartnerHouseholdRef (config_id, name, or inline config)
            - scenario: PartnerScenarioSettings (start_time, stop_time, interval, outputs)
            - overrides: Optional config overrides
            - appliances: Optional appliance pattern overrides
            - execution: PartnerExecutionSettings (run_immediately, return_results, format)
    
    Returns:
        Dictionary containing:
            - partner_request_id: Echo of provided request ID
            - config_id: UUID of the configuration used
            - scenario_id: UUID of the created scenario
            - scenario_dir: Path to scenario directory
            - glm_file: Path to GLM file
            - generated_csvs: List of generated CSV files
            - execution: Execution result (if run_immediately=True)
            - results: Time-series data (if return_results=True)
    """
    # Wrapper to pass ConfigCreate properly to avoid circular import
    def _create_config_wrapper(payload_dict):
        cfg = ConfigCreate(**payload_dict) if isinstance(payload_dict, dict) else payload_dict
        return create_config(cfg)
    
    config_id = ensure_config_id_from_partner(request.household, config_pool, _create_config_wrapper)
    sim_request = build_simulation_request_from_partner(config_id, request, SimulationRequest)

    scenario = create_simulation(sim_request)
    response = {
        "partner_request_id": request.partner_request_id,
        "config_id": config_id,
        "scenario_id": scenario["scenario_id"],
        "scenario_dir": scenario["scenario_dir"],
        "glm_file": scenario["glm_file"],
        "generated_csvs": scenario["generated_csvs"]
    }

    if request.execution.run_immediately:
        exec_result = execute_simulation(scenario["scenario_id"])
        response["execution"] = exec_result

        result_id = exec_result.get("result_id")
        if request.execution.return_results and result_id:
            series = fetch_result_series(
                result_id=result_id,
                results_pool=results_pool,
                properties=request.scenario.output_properties,
                fmt=request.execution.result_format
            )
            response["results"] = {
                "result_id": result_id,
                "format": request.execution.result_format,
                "series": series
            }

    return response


# ---------- Results endpoints ----------
@app.post("/results", status_code=201)
async def upload_result(file: UploadFile = File(...), config_id: Optional[str] = Form(None), 
                        scenario_id: Optional[str] = Form(None), metadata: Optional[str] = Form(None)):
    """
    Upload a simulation result file (typically CSV from GridLAB-D).
    
    Accepts a file upload and stores it in the results database. If the file is a CSV,
    it automatically parses and ingests the time-series data into the result_timeseries table
    for querying via the /results/{id}/series endpoint.
    
    Args:
        file: Uploaded file (typically a CSV from GridLAB-D simulation)
        config_id: Optional UUID of the configuration this result belongs to
        scenario_id: Optional UUID of the scenario this result belongs to
        metadata: Optional JSON string with additional metadata
    
    Returns:
        Dictionary with result_id (UUID) and file_path where the file was stored
    """
    rid = str(uuid.uuid4())
    filename = f"{rid}_{file.filename}"
    file_path = os.path.join(RESULTS_DIR, filename)
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    
    meta_json = {}
    if metadata:
        try:
            meta_json = json.loads(metadata)
        except Exception:
            meta_json = {"raw": metadata}
    
    if scenario_id:
        meta_json['scenario_id'] = scenario_id
    
    sql = "INSERT INTO results (id, config_id, filename, file_path, stored_at, metadata) VALUES (%s,%s,%s,%s,%s,%s)"
    db_execute(results_pool, sql, (rid, config_id, file.filename, file_path, 
                                   datetime.datetime.utcnow().isoformat(), json.dumps(meta_json)))

    if file.filename.lower().endswith(".csv"):
        ingested = ingest_result_timeseries(
            rid,
            scenario_id or meta_json.get('scenario_id'),
            file_path,
            results_pool
        )
        if ingested:
            meta_json['timeseries_rows'] = ingested
            db_execute(results_pool, "UPDATE results SET metadata=%s WHERE id=%s",
                       (json.dumps(meta_json), rid))
    
    return {"result_id": rid, "file_path": file_path}

@app.get("/results")
def list_results():
    """
    List all stored simulation results.
    
    Returns a list of all result files in the database, ordered by storage time
    (most recent first).
    
    Returns:
        List of dictionaries containing result metadata (id, config_id, filename, file_path, stored_at)
    """
    rows = db_fetchall(results_pool, "SELECT id, config_id, filename, file_path, stored_at FROM results ORDER BY stored_at DESC")
    return rows

@app.get("/results/{result_id}")
def get_result_meta(result_id: str):
    """
    Get metadata for a specific result.
    
    Args:
        result_id: UUID of the result to retrieve
    
    Returns:
        Dictionary containing result metadata (id, config_id, filename, file_path, stored_at, metadata)
        
    Raises:
        HTTPException: 404 if result not found
    """
    row = db_fetchone(results_pool, "SELECT id, config_id, filename, file_path, stored_at, metadata FROM results WHERE id = %s", (result_id,))
    if not row:
        raise HTTPException(404, "Result not found")
    return row

@app.get("/download/results/{result_id}")
def download_result(result_id: str):
    """
    Download a result file.
    
    Returns the original file (typically CSV) for download.
    
    Args:
        result_id: UUID of the result to download
    
    Returns:
        FileResponse with the result file
        
    Raises:
        HTTPException: 404 if result not found
    """
    row = db_fetchone(results_pool, "SELECT file_path, filename FROM results WHERE id = %s", (result_id,))
    if not row:
        raise HTTPException(404, "Result not found")
    return FileResponse(row["file_path"], filename=row["filename"])


@app.get("/results/{result_id}/series")
def get_result_series(
    result_id: str,
    properties: Optional[str] = None,
    start_time: Optional[str] = None,
    stop_time: Optional[str] = None,
    fmt: Literal["gridlabd", "partner"] = "gridlabd"
):
    """
    Retrieve structured time-series data for a simulation result.
    
    Returns time-series data from the ingested result_timeseries table, grouped by property.
    Supports filtering by property names and time range, with optional unit conversion.
    
    Args:
        result_id: UUID of the result to query
        properties: Optional comma-separated list of property names (e.g., 'house:total_load,meter1:measured_real_power')
                    If omitted, returns all properties
        start_time: Optional ISO datetime string for start of time range filter
        stop_time: Optional ISO datetime string for end of time range filter
        fmt: Output format - 'gridlabd' (native units) or 'partner' (converted to SI/metric)
             Partner format converts: Fahrenheit->Celsius, Wh->kWh
    
    Returns:
        Dictionary containing:
            - result_id: UUID of the result
            - format: Output format used
            - series: Dictionary mapping property names to lists of {timestamp, value, raw} dicts
        
    Raises:
        HTTPException: 503 if database unavailable
    """
    props_list = [p.strip() for p in properties.split(",") if p.strip()] if properties else None
    series = fetch_result_series(
        result_id=result_id,
        results_pool=results_pool,
        properties=props_list,
        start_time=start_time,
        stop_time=stop_time,
        fmt=fmt
    )
    return {
        "result_id": result_id,
        "format": fmt,
        "series": series
    }


@app.get("/results/{result_id}/csv")
def get_result_csv(result_id: str):
    """
    Get the raw CSV content of a simulation result.
    
    Returns the exact CSV file content as it was generated by GridLAB-D,
    including all header comments and data rows. This is useful for partners
    who want the raw CSV format without downloading a file.
    
    Args:
        result_id: UUID of the result to retrieve
    
    Returns:
        Raw CSV content as text/csv response
        
    Raises:
        HTTPException: 404 if result not found, 500 if file cannot be read
    """
    row = db_fetchone(results_pool, "SELECT file_path, filename FROM results WHERE id = %s", (result_id,))
    if not row:
        raise HTTPException(404, "Result not found")
    
    file_path = row["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(404, f"Result file not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            csv_content = f.read()
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'inline; filename="{row["filename"]}"'
            }
        )
    except Exception as e:
        LOG.exception("Error reading CSV file: %s", file_path)
        raise HTTPException(500, f"Error reading CSV file: {str(e)}")


# ---------- NEW: List scenarios ----------
@app.get("/scenarios")
def list_scenarios():
    """
    List all simulation scenarios.
    
    Scans the scenarios directory and returns metadata for all created scenarios.
    Each scenario includes its ID, config reference, time window, and file paths.
    
    Returns:
        List of scenario metadata dictionaries
    """
    scenarios = []
    
    if not os.path.exists(SCENARIOS_DIR):
        return scenarios
    
    for house_name in os.listdir(SCENARIOS_DIR):
        house_path = os.path.join(SCENARIOS_DIR, house_name)
        if not os.path.isdir(house_path):
            continue
        
        for scenario_id in os.listdir(house_path):
            scenario_path = os.path.join(house_path, scenario_id)
            metadata_path = os.path.join(scenario_path, 'metadata.json')
            
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    scenarios.append(metadata)
    
    return scenarios

@app.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    """
    Get detailed information about a specific scenario.
    
    Args:
        scenario_id: UUID of the scenario to retrieve
    
    Returns:
        Dictionary containing complete scenario metadata from metadata.json
        
    Raises:
        HTTPException: 404 if scenario not found
    """
    # Search for scenario in all house directories
    for house_name in os.listdir(SCENARIOS_DIR):
        house_path = os.path.join(SCENARIOS_DIR, house_name)
        scenario_path = os.path.join(house_path, scenario_id)
        metadata_path = os.path.join(scenario_path, 'metadata.json')
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                return json.load(f)
    
    raise HTTPException(404, "Scenario not found")


@app.get("/scenarios/{scenario_id}/results")
def get_scenario_results(scenario_id: str):
    """
    List all stored result files linked to a specific scenario.
    
    Finds all results that belong to this scenario, either through metadata
    or through the result_timeseries table linkage.
    
    Args:
        scenario_id: UUID of the scenario
    
    Returns:
        List of result metadata dictionaries for all results belonging to this scenario
    """
    sql = """
        SELECT r.id, r.config_id, r.filename, r.file_path, r.stored_at, r.metadata
        FROM results r
        WHERE r.metadata ->> 'scenario_id' = %s
           OR EXISTS (
                SELECT 1 FROM result_timeseries t
                WHERE t.result_id = r.id AND t.scenario_id = %s
           )
        ORDER BY r.stored_at DESC
    """
    rows = db_fetchall(results_pool, sql, (scenario_id, scenario_id))
    return rows

# ---------- Health ----------
@app.get("/health")
def health():
    """
    Health check endpoint.
    
    Returns basic service status and directory paths. Useful for monitoring
    and verifying the service is running correctly.
    
    Returns:
        Dictionary with status='ok' and directory paths
    """
    return {
        "status": "ok",
        "output_dir": OUTPUT_DIR,
        "results_dir": RESULTS_DIR,
        "scenarios_dir": SCENARIOS_DIR,
        "patterns_base_dir": PATTERNS_BASE_DIR
    }

import subprocess

@app.post("/simulations/{scenario_id}/execute")
def execute_simulation(scenario_id: str):
    """
    Execute a GridLAB-D simulation for a created scenario.
    
    Runs the GridLAB-D simulator on the scenario's GLM file. The simulation
    must have been created first via /simulations endpoint. After execution,
    the output CSV is automatically:
    1. Stored in the results database
    2. Parsed and ingested into result_timeseries table for querying
    
    Args:
        scenario_id: UUID of the scenario to execute
    
    Returns:
        Dictionary containing:
            - status: 'success' if execution completed
            - scenario_id: UUID of the executed scenario
            - result_id: UUID of the stored result
            - output_file: Path to the output CSV file
            - gridlabd_output: First 500 characters of GridLAB-D stdout
        
    Raises:
        HTTPException: 404 if scenario/GLM not found, 500 if execution fails or times out
    """
    LOG.info(f"Executing simulation for scenario: {scenario_id}")
    
    # Find scenario directory
    scenario_metadata = None
    for house_name in os.listdir(SCENARIOS_DIR):
        house_path = os.path.join(SCENARIOS_DIR, house_name)
        scenario_path = os.path.join(house_path, scenario_id)
        metadata_path = os.path.join(scenario_path, 'metadata.json')
        
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                scenario_metadata = json.load(f)
            break
    
    if not scenario_metadata:
        raise HTTPException(404, "Scenario not found")
    
    scenario_dir = scenario_metadata['scenario_dir']
    glm_file = scenario_metadata['glm_file']
    glm_path = os.path.join(scenario_dir, glm_file)
    
    if not os.path.exists(glm_path):
        raise HTTPException(404, f"GLM file not found: {glm_path}")
    
    LOG.info(f"Running GridLAB-D on: {glm_path}")
    import shutil

    try:
        gridlabd_exe = shutil.which("gridlabd") or "gridlabd"  # or absolute path if needed

        cmd = [gridlabd_exe, os.path.basename(glm_path)]   # pass basename
        result = subprocess.run(
            cmd,
            cwd=scenario_dir,            # <- important: run inside the scenario dir
            capture_output=True,
            text=True,
            timeout=300
        )


        
        
        LOG.info(f"GridLAB-D stdout: {result.stdout}")
        if result.stderr:
            LOG.warning(f"GridLAB-D stderr: {result.stderr}")
        
        if result.returncode != 0:
            raise HTTPException(500, f"GridLAB-D execution failed: {result.stderr}")
        
        # Check if output CSV was created
        output_file = scenario_metadata['output_file']
        output_path = os.path.join(scenario_dir, output_file)
        
        if not os.path.exists(output_path):
            raise HTTPException(500, "Simulation completed but output file not found")
        
        # Auto-upload results to results DB
        with open(output_path, 'rb') as f:
            file_content = f.read()
        
        rid = str(uuid.uuid4())
        result_filename = f"{rid}_{output_file}"
        result_path = os.path.join(RESULTS_DIR, result_filename)
        
        with open(result_path, 'wb') as f:
            f.write(file_content)
        
        meta_json = {
            'scenario_id': scenario_id,
            'execution_time': datetime.datetime.utcnow().isoformat(),
            'gridlabd_returncode': result.returncode
        }
        
        sql = "INSERT INTO results (id, config_id, filename, file_path, stored_at, metadata) VALUES (%s,%s,%s,%s,%s,%s)"
        db_execute(results_pool, sql, (
            rid,
            scenario_metadata['config_id'],
            output_file,
            result_path,
            datetime.datetime.utcnow().isoformat(),
            json.dumps(meta_json)
        ))

        rows_ingested = ingest_result_timeseries(rid, scenario_id, result_path, results_pool)
        if rows_ingested:
            meta_json['timeseries_rows'] = rows_ingested
            db_execute(results_pool, "UPDATE results SET metadata=%s WHERE id=%s",
                       (json.dumps(meta_json), rid))
        
        LOG.info(f"Simulation completed successfully. Result ID: {rid}")
        
        return {
            'status': 'success',
            'scenario_id': scenario_id,
            'result_id': rid,
            'output_file': output_path,
            'gridlabd_output': result.stdout[:500]  # First 500 chars
        }
        
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "Simulation timeout (>5 minutes)")
    except Exception as e:
        LOG.exception("Simulation execution failed")
        raise HTTPException(500, f"Simulation failed: {str(e)}")