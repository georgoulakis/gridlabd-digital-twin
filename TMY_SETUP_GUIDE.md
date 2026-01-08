# TMY Climate Data Setup and Usage Guide

## Folder Structure

Place your TMY CSV files in the `data/tmy/` directory. The folder is automatically created when the API starts, but you need to add the CSV files manually.

```
data/
  └── tmy/
      ├── murcia.csv
      ├── aspra_spitia.csv
      └── zagreb.csv
```

## Step 1: Create the TMY Directory and Add Files

```bash
# Create the directory (if it doesn't exist)
mkdir -p data/tmy

# Copy your TMY CSV files to this directory
# Make sure they are named exactly:
# - murcia.csv
# - aspra_spitia.csv
# - zagreb.csv
```

## Step 2: Create a Config with Pilot Specification

### Example Config for Aspra Spitia Pilot

```bash
curl -X POST http://localhost:8000/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "aspra_spitia_house",
    "config": {
      "pilot": "aspra_spitia",
      "timezone": "EET+2EEST",
      "floor_area": 120,
      "cooling_setpoint": 24,
      "heating_setpoint": 20,
      "design_cooling_setpoint": 26,
      "design_cooling_capacity": 5000,
      "design_heating_setpoint": 18,
      "design_heating_capacity": 4000,
      "thermostat_deadband": 2,
      "number_of_stories": 1,
      "ceiling_height": 2.5,
      "envelope_UA": 200,
      "window_wall_ratio": 0.15,
      "number_of_doors": 2,
      "Rwall": 3.5,
      "Rwindows": 0.5,
      "Rroof": 4.0,
      "Rfloor": 2.0,
      "glazing_layers": 2,
      "cooling_system_type": "ELECTRIC",
      "heating_system_type": "GAS",
      "default_simulation": {
        "output_properties": [
          "house:total_load",
          "house:hvac_load",
          "house:air_temperature",
          "house:outdoor_temperature"
        ],
        "recording_interval": 60,
        "recording_limit": 1440
      },
      "appliance_templates": {
        "washing_machine": {
          "nominal_power": 2.2,
          "duration_min": 90,
          "activations_per_day": 1,
          "pattern_dir": "washing_machine_patterns",
          "generation_method": "scaling",
          "baseline": 0,
          "timestep_native": 7,
          "output_timestep": 60
        }
      }
    }
  }'
```

**Response:**
```json
{
  "id": "abc123-def456-..."
}
```

Save the `id` for the next step.

## Step 3: Create a Scenario

### Option A: Using the Standard Endpoint

```bash
curl -X POST http://localhost:8000/simulations \
  -H "Content-Type: application/json" \
  -d '{
    "cfg_id": "abc123-def456-...",
    "start_time": "2024-07-01 00:00:00",
    "stop_time": "2024-07-07 23:59:00",
    "output_properties": [
      "house:total_load",
      "house:air_temperature",
      "house:outdoor_temperature"
    ]
  }'
```

**Response:**
```json
{
  "scenario_id": "xyz789-...",
  "scenario_dir": "./data/scenarios/aspra_spitia_house/xyz789-...",
  "glm_file": "./data/scenarios/aspra_spitia_house/xyz789-.../scenario_xyz789.glm",
  "generated_csvs": ["washing_machine_consumption.csv"],
  "metadata": { ... }
}
```

### Option B: Using the Partner-Friendly Endpoint

```bash
curl -X POST http://localhost:8000/partner/simulations \
  -H "Content-Type: application/json" \
  -d '{
    "partner_request_id": "test-001",
    "household": {
      "name": "aspra_spitia_house"
    },
    "scenario": {
      "start_time": "2024-07-01 00:00:00",
      "stop_time": "2024-07-07 23:59:00",
      "interval_seconds": 60,
      "output_properties": [
        "house:total_load",
        "house:air_temperature"
      ]
    },
    "execution": {
      "run_immediately": true,
      "return_results": true,
      "result_format": "partner"
    }
  }'
```

## Step 4: Verify the Climate File Was Copied

After creating a scenario, check that the TMY CSV file was copied to the scenario directory:

```bash
# List files in the scenario directory
ls -la data/scenarios/aspra_spitia_house/<scenario_id>/

# You should see:
# - scenario_*.glm
# - aspra_spitia.csv  (copied from data/tmy/)
# - washing_machine_consumption.csv (if applicable)
# - metadata.json
```

## Step 5: Check the Generated GLM File

Open the generated GLM file and verify it contains:

```glm
object csv_reader {
    name climate_reader_xyz789;
    filename "aspra_spitia.csv";
}

object climate {
    tmyfile "aspra_spitia.csv";
    reader climate_reader_xyz789;
};
```

## Example Configs for Other Pilots

### Murcia Pilot

```json
{
  "name": "murcia_house",
  "config": {
    "pilot": "murcia",
    "timezone": "CET+1CEST",
    ...
  }
}
```

### Zagreb Pilot

```json
{
  "name": "zagreb_house",
  "config": {
    "pilot": "zagreb",
    "timezone": "CET+1CEST",
    ...
  }
}
```

## Troubleshooting

### Error: "Pilot must be specified"
- Make sure you include `"pilot": "aspra_spitia"` (or `murcia`/`zagreb`) in your config

### Error: "Climate CSV 'aspra_spitia.csv' not found"
- Verify the file exists at `data/tmy/aspra_spitia.csv`
- Check the filename matches exactly (case-sensitive)
- Ensure the file has read permissions

### Error: "expected time zone specification"
- Make sure you include `"timezone"` in your config (e.g., `"EET+2EEST"` for Greece)

## Complete Test Workflow

```bash
# 1. Create config
CONFIG_ID=$(curl -X POST http://localhost:8000/configs \
  -H "Content-Type: application/json" \
  -d @config_example.json | jq -r '.id')

# 2. Create and execute scenario (partner endpoint)
curl -X POST http://localhost:8000/partner/simulations \
  -H "Content-Type: application/json" \
  -d "{
    \"household\": { \"config_id\": \"$CONFIG_ID\" },
    \"scenario\": {
      \"start_time\": \"2024-07-01 00:00:00\",
      \"stop_time\": \"2024-07-02 00:00:00\",
      \"output_properties\": [\"house:total_load\"]
    },
    \"execution\": { \"run_immediately\": true }
  }"
```

