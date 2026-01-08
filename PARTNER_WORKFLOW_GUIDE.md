# Partner Workflow Guide

Step-by-step guide for external partners to find their household configuration and request simulations with specific outputs.

## Overview

Partners can interact with the API in two ways:
1. **Simple workflow** - Use household name/ID and let the API handle everything
2. **Advanced workflow** - Create custom configs and scenarios manually

## Simple Workflow (Recommended)

### Step 1: Find Your Household Configuration

**Option A: List all available households**
```bash
curl http://localhost:8000/configs
```

Response:
```json
[
  {
    "id": "abc123-def456-...",
    "name": "aspra_spitia_house",
    "created_at": "2024-01-15T10:30:00",
    "version": 1
  },
  {
    "id": "xyz789-...",
    "name": "zagreb_house",
    "created_at": "2024-01-16T14:20:00",
    "version": 1
  }
]
```

**Option B: Get specific household by name** (if you know it)
```bash
curl http://localhost:8000/configs
# Look for your household name in the response
```

**Option C: Get household details by ID** (if you have the ID)
```bash
curl http://localhost:8000/configs/<household_id>
```

### Step 2: Request a Simulation with Specific Outputs

Use the **`/partner/simulations`** endpoint - it handles everything automatically:

```bash
curl -X POST http://localhost:8000/partner/simulations \
  -H "Content-Type: application/json" \
  -d '{
    "partner_request_id": "your-request-123",
    "household": {
      "name": "aspra_spitia_house"
    },
    "scenario": {
      "start_time": "2024-07-01 00:00:00",
      "stop_time": "2024-07-07 23:59:00",
      "interval_seconds": 60,
      "output_properties": [
        "house:total_load",
        "house:hvac_load",
        "house:air_temperature",
        "house:outdoor_temperature",
        "meter1:measured_real_power",
        "washing_machine:base_power",
        "dishwasher:base_power"
      ]
    },
    "execution": {
      "run_immediately": true,
      "return_results": true,
      "result_format": "partner"
    }
  }'
```

**Response includes:**
- `scenario_id` - Unique ID for this simulation
- `result_id` - Unique ID for the results
- `results.series` - Time-series data in partner units (if `return_results: true`)

### Step 3: Retrieve Results (if not returned immediately)

**Option A: Get structured JSON data**
```bash
curl "http://localhost:8000/results/<result_id>/series?properties=house:total_load,house:air_temperature&fmt=partner"
```

**Option B: Get raw CSV content**
```bash
curl http://localhost:8000/results/<result_id>/csv
```

**Option C: Download CSV file**
```bash
curl -O http://localhost:8000/download/results/<result_id>
```

## Advanced Workflow

### Step 1: Create Your Own Household Configuration

If you need a custom household configuration:

```bash
curl -X POST http://localhost:8000/configs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_custom_house",
    "config": {
      "pilot": "aspra_spitia",
      "timezone": "EET+2EEST",
      "floor_area": 120,
      "cooling_setpoint": 24,
      "heating_setpoint": 20,
      "default_simulation": {
        "output_properties": [
          "house:total_load",
          "house:air_temperature"
        ]
      }
    }
  }'
```

Save the returned `id` for future use.

### Step 2: Create Scenario Manually

```bash
curl -X POST http://localhost:8000/simulations \
  -H "Content-Type: application/json" \
  -d '{
    "cfg_id": "your-config-id",
    "start_time": "2024-07-01 00:00:00",
    "stop_time": "2024-07-07 23:59:00",
    "output_properties": [
      "house:total_load",
      "house:hvac_load",
      "meter1:measured_real_power"
    ]
  }'
```

### Step 3: Execute Simulation

```bash
curl -X POST http://localhost:8000/simulations/<scenario_id>/execute
```

### Step 4: Retrieve Results

Same as Step 3 in Simple Workflow above.

## Available Output Properties

Partners can request any combination of these properties in `output_properties`:

### House Properties
- `house:total_load` - Total electrical load (W)
- `house:hvac_load` - HVAC system load (W)
- `house:cooling_demand` - Cooling demand (W)
- `house:heating_demand` - Heating demand (W)
- `house:air_temperature` - Indoor temperature (°C in partner format)
- `house:outdoor_temperature` - Outdoor temperature (°C in partner format)

### Individual Appliances
- `<appliance_name>:base_power` - Appliance power (W)
- `<appliance_name>:power.real` - Real power (W)
- Examples: `washing_machine:base_power`, `dishwasher:base_power`, `oven:base_power`

### Meter Properties
- `meter1:measured_real_power` - Net power (W)
- `meter1:measured_real_energy` - Cumulative energy (kWh in partner format)
- `meter1:voltage_A` - Phase A voltage (V)
- `meter1:current_A` - Phase A current (A)

### Water Heater
- `main_wh:power.real` - Water heater power (W)
- `main_wh:tank_temperature` - Tank temperature (°C in partner format)
- `main_wh:tank_setpoint` - Setpoint temperature (°C in partner format)

### Solar (if enabled)
- `inverter1:P_Out` - Solar generation (W)
- `house_solar:P_Out` - Panel output (W)
- `climate:solar_flux` - Solar irradiance (W/m² in partner format)

### Climate
- `climate:temperature` - Outdoor temperature (°C in partner format)
- `climate:humidity` - Relative humidity (%)
- `climate:solar_flux` - Solar irradiance

## Unit Conversion

When using `result_format: "partner"` or `fmt=partner`:
- **Temperature**: Fahrenheit → Celsius
- **Energy**: Wh → kWh
- **Power**: Remains in watts (W)

GridLAB-D native format (`fmt=gridlabd`) returns all values in GridLAB-D units (Fahrenheit, Wh, etc.).

## Complete Example: Full Workflow

```bash
# 1. Find available households
HOUSEHOLDS=$(curl -s http://localhost:8000/configs)
echo $HOUSEHOLDS

# 2. Request simulation with specific outputs
RESPONSE=$(curl -s -X POST http://localhost:8000/partner/simulations \
  -H "Content-Type: application/json" \
  -d '{
    "partner_request_id": "demo-001",
    "household": { "name": "aspra_spitia_house" },
    "scenario": {
      "start_time": "2024-07-01 00:00:00",
      "stop_time": "2024-07-02 00:00:00",
      "output_properties": [
        "house:total_load",
        "house:air_temperature",
        "meter1:measured_real_power"
      ]
    },
    "execution": {
      "run_immediately": true,
      "return_results": true,
      "result_format": "partner"
    }
  }')

# Extract result_id from response
RESULT_ID=$(echo $RESPONSE | jq -r '.results.result_id')

# 3. Get raw CSV if needed
curl http://localhost:8000/results/$RESULT_ID/csv > results.csv

# 4. Or get filtered JSON data
curl "http://localhost:8000/results/$RESULT_ID/series?properties=house:total_load&fmt=partner"
```

## Error Handling

**404 - Household not found**
- Check household name spelling
- Verify household exists: `GET /configs`
- Use `config_id` instead of `name` if available

**400 - Pilot must be specified**
- Ensure household config includes `"pilot": "aspra_spitia"` (or murcia/zagreb)

**500 - Simulation failed**
- Check GridLAB-D is installed and accessible
- Verify scenario was created successfully
- Check scenario metadata: `GET /scenarios/{scenario_id}`

## Best Practices

1. **Use household names** - Easier than managing UUIDs
2. **Request only needed properties** - Reduces response size
3. **Use `return_results: true`** - Get data immediately without extra API calls
4. **Use `result_format: "partner"`** - Automatic unit conversion to SI/metric
5. **Store `scenario_id` and `result_id`** - For future reference and queries

