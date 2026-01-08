# appliance_pattern_generator.py
"""
Appliance pattern generation module for GridLAB-D Digital Twin
"""
import os
import json
import pickle
import numpy as np
from scipy import interpolate
from scipy.signal import savgol_filter
from fastdtw import fastdtw
from datetime import datetime, timedelta
import csv
import random
from collections import defaultdict

# ---------- Pattern Loading ----------
def load_extracted_patterns(patterns_directory='Appliance3_patterns', pattern_filename=None):
    """
    Load extracted appliance patterns from JSON or PICKLE.
    Returns a list of template patterns.
    """
    if pattern_filename is None:
        json_file = os.path.join(patterns_directory, 'Appliance3_time_warping_patterns.json')
        pkl_file = os.path.join(patterns_directory, 'Appliance3_time_warping_patterns.pkl')
        
        if os.path.exists(json_file):
            pattern_filename = json_file
        elif os.path.exists(pkl_file):
            pattern_filename = pkl_file
        else:
            raise FileNotFoundError(f"No pattern files found in {patterns_directory}")
    
    with open(pattern_filename, 'rb' if pattern_filename.endswith('.pkl') else 'r') as f:
        data = pickle.load(f) if pattern_filename.endswith('.pkl') else json.load(f)
    
    return data['time_warping_patterns']

# ---------- Utilities ----------
def normalize_pattern(seq):
    arr = np.array(seq, dtype=float)
    mn, mx = arr.min(), arr.max()
    return np.full_like(arr, 0.5) if mx == mn else (arr - mn) / (mx - mn)

def scale_pattern(norm, nominal, baseline=0):
    return norm * (nominal - baseline) + baseline

def interp_pattern(pattern, duration_min, timestep_sec=7, kind='cubic'):
    L = len(pattern)
    steps = int(duration_min * 60 / timestep_sec)
    if steps == L:
        return pattern
    x0 = np.linspace(0, 1, L)
    xt = np.linspace(0, 1, steps)
    return interpolate.interp1d(x0, pattern, kind=kind, bounds_error=False, fill_value='extrapolate')(xt)

def align_dtw(template, ref):
    dist = lambda x, y: abs(x - y)
    _, path = fastdtw(template, ref, dist=dist)
    aligned = np.zeros(len(ref))
    counts = np.zeros(len(ref))
    for i_t, i_r in path:
        aligned[i_r] += template[i_t]
        counts[i_r] += 1
    counts[counts == 0] = 1
    return aligned / counts

# ---------- Generation Methods ----------
def generate_weighted_average(templates, nominal, duration_min, baseline=0, timestep_sec=7):
    weights = []
    processed = []
    for tpl in templates:
        tpl_power = tpl['statistical_features']['max_power']
        tpl_dur = tpl['total_duration_seconds'] / 60
        pw = 1 / (1 + abs(tpl_power - nominal) / nominal)
        dw = 1 / (1 + abs(tpl_dur - duration_min) / duration_min)
        w = pw * dw
        weights.append(w)
        norm = normalize_pattern(tpl['power_sequence'])
        scaled = scale_pattern(norm, nominal, baseline)
        proc = interp_pattern(scaled, duration_min, timestep_sec)
        processed.append(proc)
    
    w_arr = np.array(weights)
    w_arr /= w_arr.sum()
    avg = np.zeros_like(processed[0])
    for proc, w in zip(processed, w_arr):
        if len(proc) != len(avg):
            proc = interp_pattern(proc, duration_min, timestep_sec)
        avg += proc * w
    return np.clip(avg, 0, None)

def generate_interpolation(templates, nominal, duration_min, baseline=0, timestep_sec=7):
    diffs = [abs(t['statistical_features']['max_power'] - nominal) for t in templates]
    idx = np.argsort(diffs)
    if len(idx) == 1:
        tpl = templates[idx[0]]
        seq = normalize_pattern(tpl['power_sequence'])
        return interp_pattern(scale_pattern(seq, nominal, baseline), duration_min, timestep_sec)
    
    t1, t2 = templates[idx[0]], templates[idx[1]]
    seq1 = normalize_pattern(t1['power_sequence'])
    seq2 = normalize_pattern(t2['power_sequence'])
    s1 = interp_pattern(scale_pattern(seq1, nominal, baseline), duration_min, timestep_sec)
    s2 = interp_pattern(scale_pattern(seq2, nominal, baseline), duration_min, timestep_sec)
    p1, p2 = t1['statistical_features']['max_power'], t2['statistical_features']['max_power']
    alpha = 0.5 if p1 == p2 else (nominal - p1) / (p2 - p1)
    alpha = np.clip(alpha, 0, 1)
    return (1 - alpha) * s1 + alpha * s2

def generate_scaling(templates, nominal, duration_min, baseline=0, timestep_sec=7, index=0):
    tpl = templates[index] if index < len(templates) else templates[0]
    seq = normalize_pattern(tpl['power_sequence'])
    return interp_pattern(scale_pattern(seq, nominal, baseline), duration_min, timestep_sec)

# ---------- High-Level Function ----------
def generate_single_activation_pattern(templates_dir, nominal, duration_min, method='weighted', 
                                      baseline=0, timestep_native=7, output_timestep=60, ref_index=0):
    """
    Generate a single activation pattern.
    Returns the power values (not timestamps).
    """
    templates = load_extracted_patterns(templates_dir)
    
    if method == 'weighted':
        pattern_native = generate_weighted_average(templates, nominal, duration_min, baseline, timestep_native)
    elif method == 'interpolate':
        pattern_native = generate_interpolation(templates, nominal, duration_min, baseline, timestep_native)
    elif method == 'scaling':
        pattern_native = generate_scaling(templates, nominal, duration_min, baseline, timestep_native)
    elif method == 'dtw':
        ref_seq = normalize_pattern(templates[ref_index]['power_sequence'])
        ref_scaled = scale_pattern(ref_seq, nominal, baseline)
        ref_interp = interp_pattern(ref_scaled, duration_min, timestep_native)
        warped = []
        for tpl in templates:
            seq = normalize_pattern(tpl['power_sequence'])
            scaled = scale_pattern(seq, nominal, baseline)
            interp = interp_pattern(scaled, duration_min, timestep_native)
            warped.append(align_dtw(interp, ref_interp))
        pattern_native = np.clip(np.mean(np.vstack(warped), axis=0), 0, None)
    else:
        raise ValueError(f"Unknown method {method}")
    
    # Resample to output_timestep
    num_output_steps = int((duration_min * 60) / output_timestep)
    x_native = np.arange(len(pattern_native)) * timestep_native
    x_output = np.arange(num_output_steps) * output_timestep
    power_values = np.interp(x_output, x_native, pattern_native)
    return power_values.tolist()

def generate_timeseries_with_activations(templates_dir, nominal, duration_min, start_date, end_date, 
                                        activations_per_day, method='weighted', baseline=0, 
                                        timestep_native=7, output_timestep=60, ref_index=0, seed=None, schedule=None):
    """
    Generate a complete time series with activations.
    
    If schedule is provided, uses probabilistic weekly schedule.
    Otherwise, uses random daily activations (backward compatible).
    
    Args:
        schedule: Optional dict with probabilistic schedule config. If provided, 
                 activations_per_day is ignored and schedule is used instead.
    """
    # If schedule provided, use probabilistic scheduling
    if schedule is not None:
        return generate_timeseries_with_probabilistic_schedule(
            templates_dir, nominal, duration_min, start_date, end_date,
            schedule, method, baseline, timestep_native, output_timestep, ref_index, seed
        )
    
    # Otherwise, use original random daily logic (backward compatible)
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    
    # Parse dates if strings
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
    
    # Generate the activation pattern once
    activation_pattern = generate_single_activation_pattern(
        templates_dir, nominal, duration_min, method, baseline, timestep_native, output_timestep, ref_index
    )
    
    activation_timesteps = len(activation_pattern)
    
    # Create time series structure
    current = start_date
    timeseries = []
    while current <= end_date:
        timeseries.append([current, 0.0])
        current += timedelta(seconds=output_timestep)
    
    # Calculate activations for each day
    current_day = start_date.date()
    while current_day <= end_date.date():
        day_indices = []
        for idx, (ts, _) in enumerate(timeseries):
            if ts.date() == current_day:
                day_indices.append(idx)
        
        if len(day_indices) == 0:
            current_day += timedelta(days=1)
            continue
        
        # Calculate how many starting positions are available for this day
        max_start_idx = len(day_indices) - activation_timesteps
        if max_start_idx > 0:
            # Ensure we don't request more activations than possible starting positions
            num_activations = min(activations_per_day, max_start_idx)
            # Sample without replacement to get unique start positions
            if num_activations > 0:
                activation_starts = random.sample(range(max_start_idx), num_activations)
                
                for start_offset in activation_starts:
                    absolute_idx = day_indices[0] + start_offset
                    for i, power_val in enumerate(activation_pattern):
                        if absolute_idx + i < len(timeseries):
                            timeseries[absolute_idx + i][1] = max(timeseries[absolute_idx + i][1], power_val)
        
        current_day += timedelta(days=1)
    
    return [(ts, power) for ts, power in timeseries]


# ---------- Probabilistic Schedule Helpers ----------
def parse_hour_range(hour_str):
    """
    Parse hour range string like "6-9" into (start_hour, end_hour).
    Returns tuple (start, end) where end is exclusive.
    """
    parts = hour_str.split('-')
    if len(parts) != 2:
        raise ValueError(f"Invalid hour range format: {hour_str}. Expected format: '6-9'")
    return int(parts[0]), int(parts[1])


def calculate_timestep_probabilities(hour_probabilities, output_timestep=60):
    """
    Convert hour-based probabilities to per-timestep probabilities.
    
    Args:
        hour_probabilities: Dict like {"6-9": 0.3, "12-14": 0.4}
        output_timestep: Timestep in seconds (default 60)
    
    Returns:
        List of 24 probabilities (one per hour), normalized
    """
    hour_probs = [0.0] * 24
    
    for hour_range, prob in hour_probabilities.items():
        start_hour, end_hour = parse_hour_range(hour_range)
        for hour in range(start_hour, end_hour):
            if 0 <= hour < 24:
                hour_probs[hour] = max(hour_probs[hour], prob)
    
    # Normalize so max probability is preserved but we can scale if needed
    return hour_probs


def is_weekend(date):
    """Check if date is Saturday (5) or Sunday (6)."""
    return date.weekday() >= 5


def generate_timeseries_with_probabilistic_schedule(templates_dir, nominal, duration_min, start_date, end_date,
                                                   schedule_config, method='weighted', baseline=0,
                                                   timestep_native=7, output_timestep=60, ref_index=0, seed=None):
    """
    Generate time series with probabilistic weekly schedule.
    
    Args:
        schedule_config: Dict with:
            - activations_per_week: int
            - weekday: dict with "hour_probabilities" key
            - weekend: dict with "hour_probabilities" key
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    
    # Parse dates
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
    
    # Generate activation pattern
    activation_pattern = generate_single_activation_pattern(
        templates_dir, nominal, duration_min, method, baseline, timestep_native, output_timestep, ref_index
    )
    activation_timesteps = len(activation_pattern)
    
    # Create time series structure
    current = start_date
    timeseries = []
    while current <= end_date:
        timeseries.append([current, 0.0])
        current += timedelta(seconds=output_timestep)
    
    # Calculate probabilities for weekday and weekend
    weekday_probs = calculate_timestep_probabilities(
        schedule_config.get('weekday', {}).get('hour_probabilities', {}),
        output_timestep
    )
    weekend_probs = calculate_timestep_probabilities(
        schedule_config.get('weekend', {}).get('hour_probabilities', {}),
        output_timestep
    )
    
    activations_per_week = schedule_config.get('activations_per_week', 7)
    
    # Group timeseries by week
    weeks = defaultdict(list)
    for idx, (ts, _) in enumerate(timeseries):
        week_start = ts - timedelta(days=ts.weekday())
        week_key = week_start.date()
        weeks[week_key].append((idx, ts))
    
    # Process each week
    for week_start_date, week_timesteps in weeks.items():
        # Calculate target activations for this week (proportional if partial week)
        week_start_datetime = datetime.combine(week_start_date, datetime.min.time())
        week_end_datetime = min(
            week_start_datetime + timedelta(days=7),
            end_date
        )
        days_in_week = (week_end_datetime.date() - week_start_date).days + 1
        target_activations = int(activations_per_week * (days_in_week / 7.0))
        
        # Build probability array for each timestep in this week
        timestep_probs = []
        timestep_indices = []
        
        for idx, ts in week_timesteps:
            hour = ts.hour
            is_weekend_day = is_weekend(ts.date())
            prob = weekend_probs[hour] if is_weekend_day else weekday_probs[hour]
            
            # Check if this timestep can fit an activation (not too close to end)
            if idx + activation_timesteps <= len(timeseries):
                timestep_probs.append(prob)
                timestep_indices.append(idx)
        
        if len(timestep_probs) == 0:
            continue
        
        # Normalize probabilities
        prob_sum = sum(timestep_probs)
        if prob_sum > 0:
            timestep_probs = [p / prob_sum for p in timestep_probs]
        else:
            # If all probabilities are zero, use uniform distribution
            timestep_probs = [1.0 / len(timestep_probs)] * len(timestep_probs)
        
        # Select activation times using weighted random selection
        selected_indices = set()
        attempts = 0
        max_attempts = len(timestep_indices) * 2
        
        while len(selected_indices) < target_activations and attempts < max_attempts:
            attempts += 1
            # Weighted random selection
            selected_idx = np.random.choice(len(timestep_indices), p=timestep_probs)
            absolute_idx = timestep_indices[selected_idx]
            
            # Check for overlap with existing activations
            overlap = False
            for existing_idx in selected_indices:
                if abs(absolute_idx - existing_idx) < activation_timesteps:
                    overlap = True
                    break
            
            if not overlap:
                selected_indices.add(absolute_idx)
        
        # If we didn't get enough activations, fill remaining with highest probability slots
        if len(selected_indices) < target_activations:
            remaining = target_activations - len(selected_indices)
            # Sort by probability (descending) and pick top slots that don't overlap
            sorted_indices = sorted(
                range(len(timestep_indices)),
                key=lambda i: timestep_probs[i],
                reverse=True
            )
            
            for sorted_idx in sorted_indices:
                if len(selected_indices) >= target_activations:
                    break
                absolute_idx = timestep_indices[sorted_idx]
                
                # Check for overlap
                overlap = False
                for existing_idx in selected_indices:
                    if abs(absolute_idx - existing_idx) < activation_timesteps:
                        overlap = True
                        break
                
                if not overlap:
                    selected_indices.add(absolute_idx)
        
        # Place activations
        for absolute_idx in selected_indices:
            for i, power_val in enumerate(activation_pattern):
                if absolute_idx + i < len(timeseries):
                    timeseries[absolute_idx + i][1] = max(timeseries[absolute_idx + i][1], power_val)
    
    return [(ts, power) for ts, power in timeseries]

def save_timeseries_csv(timeseries, filepath, gridlabd_format=True):
    """
    Save time series to CSV with absolute timestamps.
    """
    with open(filepath, 'w', newline='') as f:
        if gridlabd_format:
            for ts, power in timeseries:
                timestamp_str = ts.strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"{timestamp_str},{power:.1f}\n")
        else:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'power'])
            for ts, power in timeseries:
                timestamp_str = ts.strftime('%Y-%m-%d %H:%M:%S')
                writer.writerow([timestamp_str, f"{power:.1f}"])
    
    print(f"Time series saved to CSV: {filepath}")
