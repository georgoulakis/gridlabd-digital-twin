# unit_converters.py
"""
Unit conversion utilities for GridLAB-D Digital Twin API
Converts between SI/metric units (partners) and GridLAB-D units
"""

# ==================== TEMPERATURE CONVERSIONS ====================

def celsius_to_fahrenheit(celsius):
    """Convert Celsius to Fahrenheit"""
    if celsius is None:
        return None
    return (celsius * 9/5) + 32

def fahrenheit_to_celsius(fahrenheit):
    """Convert Fahrenheit to Celsius"""
    if fahrenheit is None:
        return None
    return (fahrenheit - 32) * 5/9

# ==================== AREA CONVERSIONS ====================

def sqm_to_sqft(square_meters):
    """Convert square meters to square feet"""
    if square_meters is None:
        return None
    return square_meters * 10.7639

def sqft_to_sqm(square_feet):
    """Convert square feet to square meters"""
    if square_feet is None:
        return None
    return square_feet / 10.7639

# ==================== LENGTH CONVERSIONS ====================

def meters_to_feet(meters):
    """Convert meters to feet"""
    if meters is None:
        return None
    return meters * 3.28084

def feet_to_meters(feet):
    """Convert feet to meters"""
    if feet is None:
        return None
    return feet / 3.28084

# ==================== POWER CONVERSIONS ====================

def watts_to_kw(watts):
    """Convert watts to kilowatts"""
    if watts is None:
        return None
    return watts / 1000

def kw_to_watts(kw):
    """Convert kilowatts to watts"""
    if kw is None:
        return None
    return kw * 1000

# ==================== ENERGY CONVERSIONS ====================

def kwh_to_wh(kwh):
    """Convert kWh to Wh"""
    if kwh is None:
        return None
    return kwh * 1000

def wh_to_kwh(wh):
    """Convert Wh to kWh"""
    if wh is None:
        return None
    return wh / 1000

def joules_to_kwh(joules):
    """Convert Joules to kWh"""
    if joules is None:
        return None
    return joules / 3600000

def kwh_to_joules(kwh):
    """Convert kWh to Joules"""
    if kwh is None:
        return None
    return kwh * 3600000

# ==================== VOLUME CONVERSIONS ====================

def liters_to_gallons(liters):
    """Convert liters to US gallons"""
    if liters is None:
        return None
    return liters * 0.264172

def gallons_to_liters(gallons):
    """Convert US gallons to liters"""
    if gallons is None:
        return None
    return gallons / 0.264172

# ==================== THERMAL RESISTANCE CONVERSIONS ====================

def rsi_to_rvalue(rsi):
    """Convert RSI (m²·K/W) to R-value (ft²·°F·h/BTU)"""
    if rsi is None:
        return None
    return rsi * 5.678263

def rvalue_to_rsi(rvalue):
    """Convert R-value to RSI"""
    if rvalue is None:
        return None
    return rvalue / 5.678263

# ==================== UA VALUE CONVERSIONS ====================

def ua_w_per_k_to_btu_per_h_f(ua_w_k):
    """Convert UA from W/K to BTU/h·°F"""
    if ua_w_k is None:
        return None
    return ua_w_k * 1.8953

def ua_btu_per_h_f_to_w_per_k(ua_btu):
    """Convert UA from BTU/h·°F to W/K"""
    if ua_btu is None:
        return None
    return ua_btu / 1.8953


# ==================== CONFIG CONVERSION (Partner Units → GridLAB-D) ====================

def convert_partner_config_to_gridlabd(partner_config):
    """
    Convert partner's configuration (SI/metric units) to GridLAB-D units.
    Creates a new dict without modifying the original.
    
    Partner units:
    - Temperature: Celsius
    - Area: square meters
    - Length: meters
    - Power: watts or kW
    - Volume: liters
    - Thermal resistance: RSI (m²·K/W)
    - UA: W/K
    
    GridLAB-D units:
    - Temperature: Fahrenheit
    - Area: square feet
    - Length: feet
    - Power: watts or kW
    - Volume: gallons
    - Thermal resistance: R-value (ft²·°F·h/BTU)
    - UA: BTU/h·°F
    """
    config = dict(partner_config)
    
    # Temperature conversions
    if 'cooling_setpoint' in config:
        config['cooling_setpoint'] = celsius_to_fahrenheit(config['cooling_setpoint'])
    if 'heating_setpoint' in config:
        config['heating_setpoint'] = celsius_to_fahrenheit(config['heating_setpoint'])
    if 'design_cooling_setpoint' in config:
        config['design_cooling_setpoint'] = celsius_to_fahrenheit(config['design_cooling_setpoint'])
    if 'design_heating_setpoint' in config:
        config['design_heating_setpoint'] = celsius_to_fahrenheit(config['design_heating_setpoint'])
    if 'thermostat_deadband' in config:
        # Deadband is a temperature difference, conversion factor is the same
        config['thermostat_deadband'] = config['thermostat_deadband'] * 1.8
    
    # Area conversions
    if 'floor_area' in config:
        config['floor_area'] = sqm_to_sqft(config['floor_area'])
    
    # Length conversions
    if 'ceiling_height' in config:
        config['ceiling_height'] = meters_to_feet(config['ceiling_height'])
    
    # Thermal resistance conversions (R-values)
    if 'Rwall' in config:
        config['Rwall'] = rsi_to_rvalue(config['Rwall'])
    if 'Rroof' in config:
        config['Rroof'] = rsi_to_rvalue(config['Rroof'])
    if 'Rfloor' in config:
        config['Rfloor'] = rsi_to_rvalue(config['Rfloor'])
    if 'Rwindows' in config:
        config['Rwindows'] = rsi_to_rvalue(config['Rwindows'])
    
    # UA value conversion
    if 'envelope_UA' in config:
        config['envelope_UA'] = ua_w_per_k_to_btu_per_h_f(config['envelope_UA'])
    
    # Waterheater conversions
    if 'objects' in config and 'waterheater' in config['objects']:
        for wh_name, wh_config in config['objects']['waterheater'].items():
            if 'tank_volume' in wh_config:
                wh_config['tank_volume'] = liters_to_gallons(wh_config['tank_volume'])
            if 'tank_setpoint' in wh_config:
                wh_config['tank_setpoint'] = celsius_to_fahrenheit(wh_config['tank_setpoint'])
            if 'tank_UA' in wh_config:
                wh_config['tank_UA'] = ua_w_per_k_to_btu_per_h_f(wh_config['tank_UA'])
    
    # Solar panel area (if in m²)
    if 'solar_config' in config and 'area' in config['solar_config']:
        config['solar_config']['area'] = sqm_to_sqft(config['solar_config']['area'])
    
    return config


# ==================== RESULTS CONVERSION (GridLAB-D → Partner Units) ====================

def convert_gridlabd_results_to_partner(results_df):
    """
    Convert GridLAB-D simulation results to partner units (SI/metric).
    
    Assumes results_df is a pandas DataFrame with GridLAB-D output columns.
    Common columns to convert:
    - *:temperature → Celsius
    - *:power.real → keep as watts
    - *:measured_real_energy → convert to kWh
    - *:voltage* → keep as volts
    """
    import pandas as pd
    
    df = results_df.copy()
    
    # Temperature columns (convert F to C)
    temp_columns = [col for col in df.columns if 'temperature' in col.lower() or 'setpoint' in col.lower()]
    for col in temp_columns:
        df[col] = df[col].apply(fahrenheit_to_celsius)
    
    # Energy columns (convert Wh to kWh if needed)
    energy_columns = [col for col in df.columns if 'energy' in col.lower()]
    for col in energy_columns:
        # GridLAB-D typically outputs in Wh
        df[col] = df[col].apply(wh_to_kwh)
    
    # Power columns already in watts, optionally convert to kW
    # Uncomment if partners prefer kW:
    # power_columns = [col for col in df.columns if 'power' in col.lower() and 'real' in col.lower()]
    # for col in power_columns:
    #     df[col] = df[col].apply(watts_to_kw)
    
    return df


# ==================== HELPER: FIELD MAPPING ====================

# Map of partner field names to GridLAB-D field names (if different)
PARTNER_TO_GRIDLABD_FIELDS = {
    'temperature_celsius': 'temperature',  # Will be converted to F
    'area_sqm': 'area',  # Will be converted to sqft
    # Add more mappings as needed
}

GRIDLABD_TO_PARTNER_FIELDS = {
    'temperature': 'temperature_celsius',
    'area': 'area_sqm',
    # Reverse mappings
}


# ==================== VALIDATION HELPERS ====================

def validate_temperature_range(temp_celsius, min_c=-50, max_c=60):
    """Validate temperature is in reasonable range"""
    if temp_celsius is None:
        return True
    return min_c <= temp_celsius <= max_c

def validate_area_range(area_sqm, min_sqm=10, max_sqm=1000):
    """Validate area is in reasonable range"""
    if area_sqm is None:
        return True
    return min_sqm <= area_sqm <= max_sqm


# ==================== UNIT DETECTION ====================

def detect_units(config):
    """
    Attempt to detect if config is already in GridLAB-D units or partner units.
    Returns: 'gridlabd', 'partner', or 'unknown'
    """
    # Heuristic: GridLAB-D uses Fahrenheit (typically 60-80 for setpoints)
    # Partner uses Celsius (typically 15-27 for setpoints)
    
    if 'cooling_setpoint' in config:
        temp = config['cooling_setpoint']
        if isinstance(temp, (int, float)):
            if 15 <= temp <= 30:
                return 'partner'  # Likely Celsius
            elif 60 <= temp <= 85:
                return 'gridlabd'  # Likely Fahrenheit
    
    if 'floor_area' in config:
        area = config['floor_area']
        if isinstance(area, (int, float)):
            if area < 500:
                return 'partner'  # Likely m² (typical house 50-300 m²)
            elif area > 500:
                return 'gridlabd'  # Likely ft² (typical house 1000-3000 ft²)
    
    return 'unknown'