# Weekday/Weekend Activation Schedule Guide

## Overview

The appliance pattern generator supports **weekday/weekend schedules** with **time-of-day probabilities**. This allows you to specify:
- Total number of activations per week
- Hour probabilities for when activations happen on weekdays (Monday-Friday)
- Hour probabilities for when activations happen on weekends (Saturday-Sunday)

The system automatically distributes the total activations across weekdays and weekends based on the probabilities you provide.

## Schedule Format

### Structure

```json
{
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
}
```

### Key Requirements

1. **`activations_per_week`**: Total number of activations per week
2. **`weekday.hour_probabilities`**: Time probabilities for weekdays (Mon-Fri)
3. **`weekend.hour_probabilities`**: Time probabilities for weekends (Sat-Sun)

### Hour Probability Format

- **Format**: `"start-end"` (e.g., `"6-9"` means 6am to 9am, exclusive of end hour)
- **Values**: Relative probabilities (higher = more likely)
- **Multiple ranges**: Can overlap; system uses maximum probability for overlapping hours

## How It Works

1. **Week processing**: For each week in the simulation period:
   - System calculates total activations needed for the week
   - Uses `weekday.hour_probabilities` for timesteps on weekdays (Mon-Fri)
   - Uses `weekend.hour_probabilities` for timesteps on weekends (Sat-Sun)

2. **Automatic distribution**: 
   - Activations are distributed across all days (weekdays and weekends) based on probabilities
   - If weekday probabilities are higher, more activations will naturally occur on weekdays
   - If weekend probabilities are higher, more activations will naturally occur on weekends
   - The system uses weighted random selection based on all probabilities

3. **Time selection**: 
   - Higher probability hours are more likely to be selected
   - The system considers both the day type (weekday/weekend) and hour probabilities
   - All `activations_per_week` activations are distributed across the entire week

4. **Overlap prevention**: Ensures activations don't overlap with each other

## Example: Dishwasher Schedule

**Scenario**: Dishwasher runs 7 times per week total, distributed automatically based on probabilities

**Weekday times**: Higher probability in morning (6-9am), lunch (12-2pm), and evening (6-10pm)
**Weekend times**: Higher probability in late morning (10am-1pm), afternoon (2-5pm), and evening (7-11pm)

Since weekday probabilities are generally higher, more activations will occur on weekdays, but the exact distribution varies based on the random selection.

```json
{
  "schedule": {
    "activations_per_week": 7,
    "weekday_activations": 5,
    "weekend_activations": 2,
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
}
```

## Example: Washing Machine Schedule

**Scenario**: Washing machine runs 5 times per week total, distributed automatically based on probabilities

**Weekday times**: Higher probability in morning (6-9am) and evening (6-10pm)
**Weekend times**: Higher probability in morning (8am-12pm) and afternoon (2-6pm)

The system will automatically distribute the 5 activations across the week based on these probabilities.

```json
{
  "schedule": {
    "activations_per_week": 5,
    "weekday_activations": 3,
    "weekend_activations": 2,
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
```

## Testing

### Step 1: Create/Update Config

Use `test_per_day_schedule_config.json` as a template, or add the schedule to an existing config:

```bash
# Create a new config via API
POST /configs
{
  "name": "my_test_config",
  "config": { ... }  # Include schedule in appliance_templates
}
```

### Step 2: Create Scenario

Use `test_per_day_schedule_scenario.json` as a template:

```bash
POST /simulations
{
  "cfg_id": "your-config-id",
  "start_time": "2024-07-01 00:00:00",
  "stop_time": "2024-07-14 23:59:00",
  "appliance_patterns": {
    "dishwasher": {
      "schedule": { ... }
    }
  }
}
```

### Step 3: Verify Activations

After running the simulation, check the generated CSV files:
- `dishwasher_consumption.csv` - Should show activations distributed across weekdays and weekends
- Count total activations per week to verify they match `activations_per_week`
- Check times to verify they align with your `hour_probabilities`
- Note: The exact distribution between weekdays and weekends will vary based on probabilities and random selection

## Tips

1. **Start simple**: Test with small numbers first (e.g., 3 weekday, 1 weekend)
2. **Use distinct probabilities**: Make sure probability differences are noticeable (e.g., 0.3 vs 0.8)
3. **Check overlaps**: Ensure `duration_min` allows multiple activations per day if needed
4. **Validate totals**: Always verify `weekday_activations + weekend_activations == activations_per_week`

## Common Patterns

### Weekday Focused
To favor weekdays, set higher probabilities for weekdays:
```json
{
  "activations_per_week": 5,
  "weekday": {
    "hour_probabilities": {
      "18-22": 0.8
    }
  },
  "weekend": {
    "hour_probabilities": {
      "18-22": 0.1
    }
  }
}
```

### Weekend Heavy
To favor weekends, set higher probabilities for weekends:
```json
{
  "activations_per_week": 7,
  "weekday": {
    "hour_probabilities": {
      "18-22": 0.2
    }
  },
  "weekend": {
    "hour_probabilities": {
      "8-12": 0.6,
      "14-18": 0.7,
      "19-23": 0.8
    }
  }
}
```

### Evening Only (Both)
```json
{
  "activations_per_week": 7,
  "weekday_activations": 5,
  "weekend_activations": 2,
  "weekday": {
    "hour_probabilities": {
      "18-23": 0.9
    }
  },
  "weekend": {
    "hour_probabilities": {
      "18-23": 0.9
    }
  }
}
```

## Backward Compatibility

If `weekday_activations` and `weekend_activations` are not provided, the system falls back to the old behavior:
- Uses `activations_per_week` and distributes randomly across all days
- Still uses `weekday` and `weekend` hour probabilities if provided

