"""
Helper functions for processing partner API requests and translating them to internal formats.
"""
import uuid
from typing import Dict, Any, Optional
from fastapi import HTTPException
from utils.db_helpers import db_fetchone
from utils.genererate_consumption_utils import deep_merge


def merge_overrides(base: Optional[Dict[str, Any]], extra: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge configuration overrides into a base configuration.
    
    Args:
        base: Base configuration dictionary (can be None)
        extra: Override dictionary to merge on top
        
    Returns:
        Merged configuration dictionary
    """
    if not base and not extra:
        return {}
    if base and extra:
        return deep_merge(dict(base), extra)
    return dict(base or extra)


def ensure_config_id_from_partner(household, config_pool, create_config_fn) -> str:
    """
    Resolve or create a config ID from partner household reference.
    
    Handles three cases:
    1. Direct config_id provided -> returns it
    2. Name provided -> looks up most recent config with that name
    3. Inline config provided -> creates new config and returns its ID
    
    Args:
        household: PartnerHouseholdRef object with config_id, name, or config
        config_pool: Database connection pool for configs database
        create_config_fn: Function to create a new config (to avoid circular import)
        
    Returns:
        Config ID string (UUID)
        
    Raises:
        HTTPException: 503 if DB unavailable, 404 if name not found, 400 if no valid reference
    """
    if household.config_id:
        return household.config_id
    if household.name and not household.config:
        if not config_pool:
            raise HTTPException(503, "Config DB unavailable")
        from utils.db_helpers import db_fetchone
        row = db_fetchone(
            config_pool,
            "SELECT id FROM configs WHERE name=%s ORDER BY created_at DESC LIMIT 1",
            (household.name,)
        )
        if row:
            return row["id"]
        raise HTTPException(404, f"Config with name '{household.name}' not found")
    if household.config:
        # ConfigCreate is passed via create_config_fn parameter to avoid circular import
        # The caller (main.py) will pass the ConfigCreate class
        config_name = household.name or f"partner_{uuid.uuid4().hex[:8]}"
        # create_config_fn expects a ConfigCreate-like object with name and config attributes
        # We create a simple dict-like object or the caller handles ConfigCreate creation
        created = create_config_fn({"name": config_name, "config": household.config})
        return created["id"]
    raise HTTPException(400, "Provide household.config_id, household.name, or household.config")


def build_simulation_request_from_partner(config_id: str, partner_req, SimulationRequest) -> Any:
    """
    Translate partner simulation request to internal SimulationRequest format.
    
    Converts partner-friendly fields (interval_seconds, recording_limit) into
    the internal overrides structure expected by create_simulation.
    
    Args:
        config_id: Resolved config ID from ensure_config_id_from_partner
        partner_req: PartnerSimulationRequest object
        SimulationRequest: SimulationRequest class (passed to avoid circular import)
        
    Returns:
        SimulationRequest object ready for create_simulation endpoint
    """
    scenario_overrides: Dict[str, Any] = {}
    if partner_req.scenario.interval_seconds:
        scenario_overrides["recording_interval"] = partner_req.scenario.interval_seconds
    if partner_req.scenario.recording_limit:
        scenario_overrides["recording_limit"] = partner_req.scenario.recording_limit
    merged_overrides = merge_overrides(partner_req.overrides, scenario_overrides)

    output_props = partner_req.scenario.output_properties

    return SimulationRequest(
        cfg_id=config_id,
        start_time=partner_req.scenario.start_time,
        stop_time=partner_req.scenario.stop_time,
        output_properties=output_props,
        appliance_patterns=partner_req.appliances,
        overrides=merged_overrides or None
    )

