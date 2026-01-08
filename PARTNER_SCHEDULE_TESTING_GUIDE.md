# Partner Guide: Testing Different Activation Schedules

## Overview

Partners can test different activation schedules for appliances **without modifying the base household config**. This allows you to:
- Keep one base household configuration
- Create multiple scenarios with different appliance usage patterns
- Compare results across different schedules

## Two Approaches

### Approach 1: Override via `appliance_patterns` (Recommended for Testing)

**Use this when:** You want to test different schedules on the same household config.

**How it works:**
- Base config has default appliance templates (stored in database)
- When creating a scenario, you provide `appliance_patterns` overrides
- System merges overrides with base templates (overrides win)
- Base config remains unchanged

**Example Request:**

```json
POST /simulations
{
  "cfg_id": "your-household-config-id",
  "start_time": "2024-01-01 00:00:00",
  "stop_time": "2024-01-07 23:59:59",
  "appliance_patterns": {
    "dishwasher": {
      "schedule": {
        "activations_per_week": 5,
        "weekday": {
          "hour_probabilities": {
            "18-22": 0.8
          }
        },
        "weekend": {
          "hour_probabilities": {
            "10-14": 0.5,
            "19-23": 0.6
          }
        }
      }
    },
    "washing_machine": {
      "schedule": {
        "activations_per_week": 3,
        "weekday": {
          "hour_probabilities": {
            "6-9": 0.4
          }
        },
        "weekend": {
          "hour_probabilities": {
            "8-12": 0.5,
            "14-18": 0.4
          }
        }
      }
    }
  }
}
```

**Partner API Example:**

```json
POST /partner/simulations
{
  "household": {
    "config_id": "your-household-config-id"
  },
  "scenario": {
    "start_time": "2024-01-01 00:00:00",
    "stop_time": "2024-01-07 23:59:59"
  },
  "appliances": {
    "dishwasher": {
      "schedule": {
        "activations_per_week": 5,
        "weekday": {
          "hour_probabilities": {
            "18-22": 0.8
          }
        },
        "weekend": {
          "hour_probabilities": {
            "10-14": 0.5,
            "19-23": 0.6
          }
        }
      }
    }
  }
}
```

### Approach 2: Modify Base Config (For Permanent Changes)

**Use this when:** You want to permanently change the default schedule for a household.

**How it works:**
- Update the household config via `PATCH /configs/{cfg_id}`
- New scenarios will use the updated schedule by default
- All future scenarios inherit the new schedule

**Example:**

```json
PATCH /configs/{cfg_id}
{
  "config": {
    "appliance_templates": {
      "dishwasher": {
        "schedule": {
          "activations_per_week": 7,
          "weekday": {
            "hour_probabilities": {
              "12-14": 0.4,
              "18-22": 0.6
            }
          },
          "weekend": {
            "hour_probabilities": {
              "10-13": 0.3,
              "18-23": 0.5
            }
          }
        }
      }
    }
  }
}
```

## Schedule Override Structure

The `schedule` object supports:

```json
{
  "schedule": {
    "activations_per_week": 7,  // Total activations per week
    "weekday": {                 // Monday-Friday
      "hour_probabilities": {
        "6-9": 0.3,    // 30% probability during 6am-9am
        "12-14": 0.4,  // 40% probability during 12pm-2pm
        "18-22": 0.6   // 60% probability during 6pm-10pm
      }
    },
    "weekend": {                 // Saturday-Sunday
      "hour_probabilities": {
        "8-11": 0.2,
        "14-17": 0.3,
        "19-23": 0.4
      }
    }
  }
}
```

**Key Points:**
- Hour ranges use format `"start-end"` (e.g., `"6-9"` means 6am to 9am)
- Probabilities are relative weights (higher = more likely)
- Multiple hour ranges can overlap (system uses max probability)
- If no schedule provided, falls back to `activations_per_day` (random placement)

## Testing Workflow

### Scenario 1: Test Different Weekly Frequencies

```json
// Test 1: Low usage (3 times per week)
POST /simulations
{
  "cfg_id": "household-id",
  "start_time": "2024-01-01 00:00:00",
  "stop_time": "2024-01-07 23:59:59",
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

// Test 2: High usage (10 times per week)
POST /simulations
{
  "cfg_id": "household-id",  // Same config!
  "start_time": "2024-01-01 00:00:00",
  "stop_time": "2024-01-07 23:59:59",
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

### Scenario 2: Test Different Time-of-Day Patterns

```json
// Morning person household
POST /simulations
{
  "cfg_id": "household-id",
  "appliance_patterns": {
    "dishwasher": {
      "schedule": {
        "activations_per_week": 7,
        "weekday": {"hour_probabilities": {"6-9": 0.7}},
        "weekend": {"hour_probabilities": {"7-10": 0.6}}
      }
    }
  }
}

// Evening person household
POST /simulations
{
  "cfg_id": "household-id",  // Same config!
  "appliance_patterns": {
    "dishwasher": {
      "schedule": {
        "activations_per_week": 7,
        "weekday": {"hour_probabilities": {"18-23": 0.8}},
        "weekend": {"hour_probabilities": {"19-23": 0.7}}
      }
    }
  }
}
```

### Scenario 3: Test Weekday vs Weekend Differences

```json
POST /simulations
{
  "cfg_id": "household-id",
  "appliance_patterns": {
    "washing_machine": {
      "schedule": {
        "activations_per_week": 4,
        "weekday": {
          "hour_probabilities": {
            "6-8": 0.5  // Only early morning on weekdays
          }
        },
        "weekend": {
          "hour_probabilities": {
            "10-16": 0.6  // Afternoon on weekends
          }
        }
      }
    }
  }
}
```

## Partial Overrides

You can override just part of a schedule:

```json
// Only change weekday schedule, keep weekend from base config
POST /simulations
{
  "cfg_id": "household-id",
  "appliance_patterns": {
    "dishwasher": {
      "schedule": {
        "weekday": {
          "hour_probabilities": {
            "18-22": 1.0  // Only override weekday
          }
        }
        // weekend will use base config schedule
      }
    }
  }
}
```

## Backward Compatibility

- **Without schedule**: Uses `activations_per_day` with random placement (old behavior)
- **With schedule**: Uses probabilistic weekly schedule (new behavior)
- **Mixed**: Can have some appliances with schedule, others without

## Best Practices

1. **Keep base config simple**: Store common/default schedules in base config
2. **Use overrides for testing**: Test different schedules via `appliance_patterns`
3. **Document scenarios**: Name scenarios clearly (e.g., "high-usage", "evening-only")
4. **Compare results**: Use same time period for fair comparison
5. **Use seeds**: Set `seed` in appliance_patterns for reproducible results

## Example: Complete Testing Workflow

```python
# 1. Create base household config (once)
base_config = {
  "name": "dublin_household",
  "config": {
    "location": "dublin",
    "appliance_templates": {
      "dishwasher": {
        "nominal_power": 1.8,
        "duration_min": 120,
        "schedule": {
          "activations_per_week": 7,
          "weekday": {"hour_probabilities": {"18-22": 0.6}},
          "weekend": {"hour_probabilities": {"19-23": 0.5}}
        }
      }
    }
  }
}
config_id = create_config(base_config)

# 2. Test different schedules (multiple scenarios)
scenarios = [
  {
    "name": "low_usage",
    "appliance_patterns": {
      "dishwasher": {"schedule": {"activations_per_week": 3, ...}}
    }
  },
  {
    "name": "high_usage", 
    "appliance_patterns": {
      "dishwasher": {"schedule": {"activations_per_week": 10, ...}}
    }
  },
  {
    "name": "morning_person",
    "appliance_patterns": {
      "dishwasher": {"schedule": {"weekday": {"hour_probabilities": {"6-9": 0.8}}}}
    }
  }
]

for scenario in scenarios:
  create_simulation({
    "cfg_id": config_id,  # Same base config!
    "start_time": "2024-01-01 00:00:00",
    "stop_time": "2024-01-07 23:59:59",
    "appliance_patterns": scenario["appliance_patterns"]
  })
```

