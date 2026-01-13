# Adding Schedules Only During Scenario Creation

## Overview

You can add schedules to appliances **only when creating a scenario**, without modifying the base household configuration. This is useful for:
- Testing different usage patterns with the same base config
- Creating multiple scenarios with different schedules
- Keeping base configs simple and reusable

## How It Works

1. **Base Config**: Contains appliance templates with basic settings (power, duration, etc.) but **no schedule**
2. **Scenario Request**: Adds `appliance_patterns` with schedules that override/merge with base config
3. **Result**: Scenario uses the schedule from `appliance_patterns`, base config remains unchanged

## Example Workflow

### Step 1: Create Base Config (No Schedules)

Create a base household config **without** schedules:

```json
POST /configs
{
  "name": "dublin_household_base",
  "config": {
    "location": "dublin",
    "appliance_templates": {
      "dishwasher": {
        "nominal_power": 1.8,
        "duration_min": 120,
        "generation_method": "weighted",
        "pattern_dir": "dishwasher_patterns"
      },
      "washing_machine": {
        "nominal_power": 2.0,
        "duration_min": 90,
        "generation_method": "scaling",
        "pattern_dir": "washing_machine_patterns"
      }
    }
  }
}
```

**Note**: No `schedule` field in appliance_templates!

### Step 2: Create Scenario with Schedules

When creating a simulation, add schedules via `appliance_patterns`:

```json
POST /simulations
{
  "cfg_id": "your-config-id-from-step-1",
  "start_time": "2024-07-01 00:00:00",
  "stop_time": "2024-07-14 23:59:00",
  "output_properties": [
    "house:total_load",
    "house:air_temperature"
  ],
  "appliance_patterns": {
    "dishwasher": {
      "schedule": {
        "activations_per_week": 7,
        "weekday": {
          "hour_probabilities": {
            "6-9": 0.3,
            "12-14": 0.4,
            "18-22": 0.6
          }
        },
        "weekend": {
          "hour_probabilities": {
            "10-13": 0.3,
            "14-17": 0.4,
            "19-23": 0.5
          }
        }
      }
    },
    "washing_machine": {
      "schedule": {
        "activations_per_week": 5,
        "weekday": {
          "hour_probabilities": {
            "6-9": 0.5,
            "18-22": 0.6
          }
        },
        "weekend": {
          "hour_probabilities": {
            "8-12": 0.4,
            "14-18": 0.5
          }
        }
      }
    }
  }
}
```

## Complete Example Files

### 1. Base Config (No Schedule)
See: `base_config_without_schedule_example.json`

### 2. Scenario Request (With Schedule)
See: `scenario_with_schedule_only_example.json`

## Key Points

1. **Base config doesn't need schedules**: You can create configs without any schedule information
2. **Schedules added at scenario time**: Use `appliance_patterns` in the simulation request
3. **Overrides merge**: The schedule from `appliance_patterns` will override any schedule in base config
4. **Partial overrides**: You can add schedules for only some appliances

## Partial Override Example

Add schedule for only one appliance:

```json
POST /simulations
{
  "cfg_id": "your-config-id",
  "start_time": "2024-07-01 00:00:00",
  "stop_time": "2024-07-14 23:59:00",
  "appliance_patterns": {
    "dishwasher": {
      "schedule": {
        "activations_per_week": 7,
        "weekday": {
          "hour_probabilities": {
            "18-22": 0.8
          }
        },
        "weekend": {
          "hour_probabilities": {
            "19-23": 0.6
          }
        }
      }
    }
    // washing_machine will use base config (or activations_per_day if no schedule)
  }
}
```

## Multiple Scenarios, Same Config

You can create multiple scenarios with different schedules using the same base config:

```json
// Scenario 1: Low usage
POST /simulations
{
  "cfg_id": "same-config-id",
  "start_time": "2024-07-01 00:00:00",
  "stop_time": "2024-07-07 23:59:00",
  "appliance_patterns": {
    "dishwasher": {
      "schedule": {
        "activations_per_week": 3,
        "weekday": {"hour_probabilities": {"18-22": 0.8}},
        "weekend": {"hour_probabilities": {"19-23": 0.6}}
      }
    }
  }
}

// Scenario 2: High usage (same config!)
POST /simulations
{
  "cfg_id": "same-config-id",
  "start_time": "2024-07-01 00:00:00",
  "stop_time": "2024-07-07 23:59:00",
  "appliance_patterns": {
    "dishwasher": {
      "schedule": {
        "activations_per_week": 10,
        "weekday": {"hour_probabilities": {"12-14": 0.4, "18-22": 0.6}},
        "weekend": {"hour_probabilities": {"10-23": 0.5}}
      }
    }
  }
}
```

## Benefits

1. **Reusability**: One base config, many scenarios
2. **Flexibility**: Test different schedules without changing base config
3. **Clean separation**: Base config = physical properties, Scenario = usage patterns
4. **Easy comparison**: Run multiple scenarios with same time period to compare

## Fallback Behavior

- **If schedule provided in scenario**: Uses that schedule
- **If schedule in base config but not in scenario**: Uses base config schedule
- **If no schedule anywhere**: Falls back to `activations_per_day` with random placement

