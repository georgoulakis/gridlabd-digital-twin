import sys
import os



try:
    from appliance_pattern_generator import generate_timeseries_with_activations, save_timeseries_csv
except ImportError:
    print("WARNING: appliance_pattern_generator not found. CSV generation will fail.", file=sys.stderr)
    generate_timeseries_with_activations = None
    save_timeseries_csv = None



# Update data directories for local development
DATA_DIR = os.getenv("DATA_DIR", "./data")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
RESULTS_DIR = os.path.join(DATA_DIR, "results")
SCENARIOS_DIR = os.path.join(DATA_DIR, "scenarios")
PATTERNS_BASE_DIR = os.getenv("PATTERNS_BASE_DIR", os.path.join(DATA_DIR, "patterns"))


def deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge overrides into base (non-destructive)."""
    if not isinstance(base, dict) or not isinstance(overrides, dict):
        return overrides
    result = dict(base)
    for k, v in overrides.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

# ---------- NEW: Pattern Generation Helper ----------
def generate_appliance_csv(appliance_name, appliance_config, start_time, stop_time, scenario_dir):
    """
    Generate CSV file for a single appliance using pattern generation script.
    
    Returns: filename of generated CSV (relative to scenario_dir)
    """
    if not generate_timeseries_with_activations or not save_timeseries_csv:
        raise RuntimeError("Pattern generation module not available")
    
    # Extract parameters from appliance_config
    nominal = appliance_config.get('nominal_power', 2.0)
    duration_min = appliance_config.get('duration_min', 90)
    activations_per_day = appliance_config.get('activations_per_day', 2)
    method = appliance_config.get('generation_method', 'scaling')
    baseline = appliance_config.get('baseline', 0)
    timestep_native = appliance_config.get('timestep_native', 7)
    output_timestep = appliance_config.get('output_timestep', 60)
    
    # Pattern directory for this appliance type
    pattern_dir = appliance_config.get('pattern_dir', f'{appliance_name}_patterns')
    pattern_full_path = os.path.join(PATTERNS_BASE_DIR, pattern_dir)
    
    if not os.path.exists(pattern_full_path):
        raise FileNotFoundError(f"Pattern directory not found: {pattern_full_path}")
    
    # Check if probabilistic schedule is provided
    schedule = appliance_config.get('schedule', None)
    
    # Generate timeseries
    timeseries = generate_timeseries_with_activations(
        templates_dir=pattern_full_path,
        nominal=nominal,
        duration_min=duration_min,
        start_date=start_time,
        end_date=stop_time,
        activations_per_day=activations_per_day if schedule is None else None,  # Ignored if schedule provided
        method=method,
        baseline=baseline,
        timestep_native=timestep_native,
        output_timestep=output_timestep,
        seed=appliance_config.get('seed', 42),
        schedule=schedule  # Pass schedule if provided
    )
    
    # Save to scenario directory
    csv_filename = f"{appliance_name}_consumption.csv"
    csv_path = os.path.join(scenario_dir, csv_filename)
    save_timeseries_csv(timeseries, csv_path, gridlabd_format=True)
    
    return csv_filename