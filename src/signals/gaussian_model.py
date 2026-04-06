"""
Gaussian Probability Model — Calculate probability of temperature threshold
"""
from scipy import stats
from typing import Literal
import logging

logger = logging.getLogger(__name__)


# RMSE by forecast lead time (based on aviation weather accuracy studies)
RMSE_BY_LEAD_TIME = {
    6: 1.5,    # 0-6 hours: ±1.5°C
    12: 2.5,   # 6-12 hours: ±2.5°C
    24: 3.5,   # 12-24 hours: ±3.5°C
    48: 5.0,   # 24-48 hours: ±5.0°C
    72: 7.5    # 48+ hours: ±7.5°C
}


def get_rmse_for_lead_time(hours: float) -> float:
    """
    Get appropriate RMSE for forecast lead time
    
    Args:
        hours: Hours until resolution
        
    Returns:
        RMSE (standard deviation) in °C
    """
    if hours <= 6:
        return RMSE_BY_LEAD_TIME[6]
    elif hours <= 12:
        return RMSE_BY_LEAD_TIME[12]
    elif hours <= 24:
        return RMSE_BY_LEAD_TIME[24]
    elif hours <= 48:
        return RMSE_BY_LEAD_TIME[48]
    else:
        return RMSE_BY_LEAD_TIME[72]


def calculate_probability(
    current_temp_c: float,
    trend_per_hour: float,
    hours_to_resolution: float,
    threshold_c: float,
    threshold_type: Literal['above', 'below'] = 'above'
) -> float:
    """
    Calculate probability of temperature reaching threshold using Gaussian model
    
    Args:
        current_temp_c: Current temperature in Celsius
        trend_per_hour: Temperature change rate (°C/hour)
        hours_to_resolution: Hours remaining until market resolves
        threshold_c: Threshold temperature in Celsius
        threshold_type: 'above' or 'below'
        
    Returns:
        Probability (0.0 to 1.0)
        
    Example:
        Current: 15.8°C, Trend: +0.3°C/hr, Hours: 6, Threshold: 16°C
        → Projected: 15.8 + (0.3 * 6) = 17.6°C
        → RMSE: 1.5°C (6-hour lead time)
        → P(temp > 16°C) = 1 - CDF(16, mean=17.6, std=1.5) = 0.856 (85.6%)
    """
    # Project temperature at resolution time
    projected_temp = current_temp_c + (trend_per_hour * hours_to_resolution)
    
    # Get appropriate RMSE for lead time
    rmse = get_rmse_for_lead_time(hours_to_resolution)
    
    # Create normal distribution
    distribution = stats.norm(loc=projected_temp, scale=rmse)
    
    # Calculate probability
    if threshold_type == 'above':
        # P(X > threshold) = 1 - CDF(threshold)
        probability = 1.0 - distribution.cdf(threshold_c)
    else:  # below
        # P(X < threshold) = CDF(threshold)
        probability = distribution.cdf(threshold_c)
    
    # Clamp to valid range
    probability = max(0.0, min(1.0, probability))
    
    logger.debug(
        f"Gaussian model: current={current_temp_c:.1f}°C, "
        f"trend={trend_per_hour:.2f}°C/hr, hours={hours_to_resolution:.1f}, "
        f"projected={projected_temp:.1f}°C, rmse={rmse:.1f}°C, "
        f"threshold={threshold_c:.1f}°C {threshold_type}, "
        f"probability={probability:.3f}"
    )
    
    return probability


def calculate_range_probability(
    current_temp_c: float,
    trend_per_hour: float,
    hours_to_resolution: float,
    threshold_min_c: float,
    threshold_max_c: float
) -> float:
    """
    Calculate probability of temperature falling within a range
    
    Args:
        current_temp_c: Current temperature in Celsius
        trend_per_hour: Temperature change rate (°C/hour)
        hours_to_resolution: Hours remaining until market resolves
        threshold_min_c: Minimum threshold in Celsius
        threshold_max_c: Maximum threshold in Celsius
        
    Returns:
        Probability (0.0 to 1.0)
        
    Example:
        Current: 10°C, Trend: +0.5°C/hr, Hours: 8, Range: 12-16°C
        → Projected: 10 + (0.5 * 8) = 14°C
        → RMSE: 2.5°C (8-hour lead time)
        → P(12°C < temp < 16°C) = CDF(16) - CDF(12) = 0.575 (57.5%)
    """
    # Project temperature at resolution time
    projected_temp = current_temp_c + (trend_per_hour * hours_to_resolution)
    
    # Get appropriate RMSE for lead time
    rmse = get_rmse_for_lead_time(hours_to_resolution)
    
    # Create normal distribution
    distribution = stats.norm(loc=projected_temp, scale=rmse)
    
    # P(min < X < max) = CDF(max) - CDF(min)
    probability = distribution.cdf(threshold_max_c) - distribution.cdf(threshold_min_c)
    
    # Clamp to valid range
    probability = max(0.0, min(1.0, probability))
    
    logger.debug(
        f"Range probability: current={current_temp_c:.1f}°C, "
        f"trend={trend_per_hour:.2f}°C/hr, hours={hours_to_resolution:.1f}, "
        f"projected={projected_temp:.1f}°C, rmse={rmse:.1f}°C, "
        f"range={threshold_min_c:.1f}-{threshold_max_c:.1f}°C, "
        f"probability={probability:.3f}"
    )
    
    return probability


def calculate_confidence_interval(
    current_temp_c: float,
    trend_per_hour: float,
    hours_to_resolution: float,
    confidence_level: float = 0.95
) -> tuple[float, float]:
    """
    Calculate confidence interval for projected temperature
    
    Args:
        current_temp_c: Current temperature in Celsius
        trend_per_hour: Temperature change rate (°C/hour)
        hours_to_resolution: Hours remaining until market resolves
        confidence_level: Confidence level (default 0.95 for 95%)
        
    Returns:
        (lower_bound, upper_bound) in Celsius
    """
    projected_temp = current_temp_c + (trend_per_hour * hours_to_resolution)
    rmse = get_rmse_for_lead_time(hours_to_resolution)
    
    distribution = stats.norm(loc=projected_temp, scale=rmse)
    
    alpha = 1 - confidence_level
    lower = distribution.ppf(alpha / 2)
    upper = distribution.ppf(1 - alpha / 2)
    
    return (lower, upper)


# Example usage and validation
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Gaussian Probability Model - Examples\n")
    
    # Example 1: ColdMath's Tokyo trade
    print("Example 1: Tokyo high temperature exceeds 16°C")
    print("Current: 15.8°C, Trend: +0.3°C/hr, Hours: 6")
    prob = calculate_probability(15.8, 0.3, 6, 16.0, 'above')
    print(f"Probability: {prob:.1%}\n")
    
    # Example 2: New York high above 75°F (23.9°C)
    print("Example 2: New York high exceeds 23.9°C (75°F)")
    print("Current: 18°C, Trend: +0.5°C/hr, Hours: 8")
    prob = calculate_probability(18.0, 0.5, 8, 23.9, 'above')
    print(f"Probability: {prob:.1%}\n")
    
    # Example 3: London low below 5°C
    print("Example 3: London low below 5°C")
    print("Current: 8°C, Trend: -0.4°C/hr, Hours: 10")
    prob = calculate_probability(8.0, -0.4, 10, 5.0, 'below')
    print(f"Probability: {prob:.1%}\n")
    
    # Example 4: Range (12-16°C)
    print("Example 4: Temperature in range 12-16°C")
    print("Current: 10°C, Trend: +0.5°C/hr, Hours: 8")
    prob = calculate_range_probability(10.0, 0.5, 8, 12.0, 16.0)
    print(f"Probability: {prob:.1%}\n")
    
    # Example 5: Confidence intervals
    print("Example 5: 95% Confidence interval")
    print("Current: 15°C, Trend: +0.3°C/hr, Hours: 12")
    projected = 15.0 + (0.3 * 12)
    lower, upper = calculate_confidence_interval(15.0, 0.3, 12)
    print(f"Projected: {projected:.1f}°C")
    print(f"95% CI: [{lower:.1f}°C, {upper:.1f}°C]\n")
