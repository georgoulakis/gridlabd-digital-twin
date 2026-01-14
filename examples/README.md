# Examples

This folder contains example JSON files for creating configurations and scenarios.

## Structure

### `config_creation/`
Contains example household configuration files that define the physical and electrical properties of a building, its systems, and appliances.

**Files:**
- `base_config_without_schedule_example.json` - Basic configuration without custom schedules
- `dublin_household_config_example.json` - Complete Dublin household configuration
- `dublin_household_config_with_schedule_example.json` - Dublin household with custom schedules
- `config_example_aspra_spitia.json` - Aspra Spitia location configuration example
- `complete_dublin_test_config.json` - Complete Dublin test configuration with all features (misc appliances, etc.)
- `test_per_day_schedule_config.json` - Configuration with per-day schedule examples

### `scenario_creation/`
Contains example scenario request files that define simulation parameters, time ranges, output properties, and appliance pattern overrides.

**Files:**
- `scenario_request_example.json` - Basic scenario request example
- `scenario_with_schedule_only_example.json` - Scenario with schedule overrides only
- `complete_dublin_test_scenario.json` - Complete Dublin test scenario (1-minute intervals)
- `complete_dublin_test_scenario_15min.json` - Complete Dublin test scenario with 15-minute recording intervals
- `complete_dublin_test_scenario_1hour.json` - Complete Dublin test scenario with 1-hour recording intervals
- `test_per_day_schedule_scenario.json` - Scenario with per-day schedule testing
- `partner_simulation_example.json` - Partner API format example
- `partner_schedule_testing_examples.json` - Partner schedule testing examples

## Usage

1. **Creating a Configuration:**
   - Use files from `config_creation/` as templates
   - POST to `/configs` endpoint with the JSON file content
   - Save the returned `config_id` for creating scenarios

2. **Creating a Scenario:**
   - Use files from `scenario_creation/` as templates
   - Replace `cfg_id` with your actual configuration ID
   - Adjust `start_time` and `stop_time` as needed
   - POST to `/simulations` endpoint with the JSON file content

## Recording Intervals

The `recording_interval` parameter controls how often data is written to the output CSV (in seconds):
- 60 seconds = 1 minute (default)
- 900 seconds = 15 minutes
- 3600 seconds = 1 hour

You can override this in scenario files using the `overrides` section:
```json
"overrides": {
  "recording_interval": 900,
  "recording_limit": 999999
}
```

