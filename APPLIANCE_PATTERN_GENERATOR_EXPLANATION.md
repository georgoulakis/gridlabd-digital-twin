# Appliance Pattern Generator - Current Implementation & Enhancement Plan

## How It Currently Works

### Arguments When Creating Scenarios

The pattern generator is called via `generate_appliance_csv()` in `utils/genererate_consumption_utils.py` with these parameters from the config:

1. **`nominal_power`** - Peak power consumption (Watts)
2. **`duration_min`** - How long each activation lasts (minutes)
3. **`activations_per_day`** - Number of times appliance runs per day (integer)
4. **`generation_method`** - Pattern generation method: 'scaling', 'weighted', 'interpolate', or 'dtw'
5. **`baseline`** - Baseline power when not active (Watts, usually 0)
6. **`timestep_native`** - Native timestep of templates (seconds, default 7)
7. **`output_timestep`** - Output CSV timestep (seconds, default 60)
8. **`pattern_dir`** - Directory containing pattern templates
9. **`seed`** - Random seed for reproducibility

### Current Activation Logic

**Lines 181-208 in `appliance_pattern_generator.py`:**

1. **Random placement**: Activations are randomly placed throughout each day
2. **Uniform distribution**: All time slots in a day have equal probability
3. **Per-day basis**: `activations_per_day` activations happen every single day
4. **No time-of-day preferences**: No distinction between morning/afternoon/evening
5. **No weekday/weekend distinction**: Same schedule every day

**Example**: If `activations_per_day=2`, the dishwasher runs 2 times every day, at random times.

## Proposed Enhancement: Probabilistic Weekly Schedule

### Requirements

1. **Weekly frequency**: X activations per week (not per day)
2. **Time-of-day probabilities**: Different probabilities for different hours
3. **Weekday vs Weekend**: Different schedules for weekdays (Mon-Fri) vs weekends (Sat-Sun)
4. **Probabilistic selection**: Use probabilities to determine when activations occur

### Implementation Plan

#### 1. New Configuration Structure

Add to appliance config:

```json
{
  "appliance_templates": {
    "dishwasher": {
      "nominal_power": 1.8,
      "duration_min": 120,
      "generation_method": "weighted",
      "schedule": {
        "activations_per_week": 7,  // Total per week
        "weekday": {
          "hour_probabilities": {
            "6-9": 0.3,    // 30% chance in morning
            "12-14": 0.4,  // 40% chance at lunch
            "18-22": 0.5   // 50% chance in evening
          }
        },
        "weekend": {
          "hour_probabilities": {
            "8-11": 0.2,
            "14-17": 0.3,
            "19-23": 0.4
          }
        }
      }
    }
  }
}
```

#### 2. Changes Needed

**File: `appliance_pattern_generator.py`**

1. **New function**: `generate_timeseries_with_probabilistic_schedule()`
   - Accepts schedule configuration
   - Calculates probabilities for each hour slot
   - Selects activation times based on probabilities
   - Ensures total activations per week matches target

2. **Modify**: `generate_timeseries_with_activations()`
   - Add optional `schedule` parameter
   - If schedule provided, use probabilistic logic
   - Otherwise, fall back to current random logic

3. **Helper functions**:
   - `parse_hour_range()` - Parse "6-9" into hour range
   - `calculate_activation_probabilities()` - Convert hour probabilities to per-timestep probabilities
   - `select_activation_times()` - Select times based on probabilities

**File: `utils/genererate_consumption_utils.py`**

1. **Modify**: `generate_appliance_csv()`
   - Check if `schedule` key exists in appliance_config
   - Pass schedule to generator if present

#### 3. Algorithm Logic

```
For each week in simulation period:
  1. Determine if day is weekday or weekend
  2. Get hour probabilities for that day type
  3. Convert hour probabilities to per-timestep probabilities
  4. Calculate target activations for this week
  5. For each timestep, roll dice based on probability
  6. If activation selected and no overlap with previous activation:
     - Place activation at this timestep
     - Track remaining activations for week
  7. If week ends and activations < target:
     - Force place remaining activations at highest probability slots
```

#### 4. Example Schedule Format

```python
schedule = {
    "activations_per_week": 7,
    "weekday": {
        "hour_probabilities": {
            "6-9": 0.3,      # Morning: 6am-9am
            "12-14": 0.4,    # Lunch: 12pm-2pm  
            "18-22": 0.5     # Evening: 6pm-10pm
        }
    },
    "weekend": {
        "hour_probabilities": {
            "8-11": 0.2,     # Late morning
            "14-17": 0.3,    # Afternoon
            "19-23": 0.4     # Evening
        }
    }
}
```

### Benefits

1. **More realistic**: Matches real-world usage patterns
2. **Flexible**: Can model complex schedules
3. **Backward compatible**: Old configs still work (if no schedule, use random)
4. **Weekly control**: Better than daily for appliances used less frequently

