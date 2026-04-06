"""
Unit tests for Gaussian probability model
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from signals.gaussian_model import (
    calculate_probability,
    calculate_range_probability,
    calculate_confidence_interval,
    get_rmse_for_lead_time
)


class TestRMSE:
    """Test RMSE selection by lead time"""
    
    def test_rmse_0_to_6_hours(self):
        assert get_rmse_for_lead_time(3) == 1.5
        assert get_rmse_for_lead_time(6) == 1.5
    
    def test_rmse_6_to_12_hours(self):
        assert get_rmse_for_lead_time(8) == 2.5
        assert get_rmse_for_lead_time(12) == 2.5
    
    def test_rmse_12_to_24_hours(self):
        assert get_rmse_for_lead_time(18) == 3.5
        assert get_rmse_for_lead_time(24) == 3.5
    
    def test_rmse_24_to_48_hours(self):
        assert get_rmse_for_lead_time(36) == 5.0
        assert get_rmse_for_lead_time(48) == 5.0
    
    def test_rmse_over_48_hours(self):
        assert get_rmse_for_lead_time(60) == 7.5
        assert get_rmse_for_lead_time(100) == 7.5


class TestProbabilityAbove:
    """Test probability calculations for 'above' threshold"""
    
    def test_coldmath_tokyo_scenario(self):
        """
        ColdMath's actual trade: Tokyo hitting 16°C
        Current: 15.8°C, Trend: +0.3°C/hr, Hours: 6, Threshold: 16°C
        Projected: 15.8 + (0.3 * 6) = 17.6°C
        RMSE: 1.5°C
        Should be high probability (>80%)
        """
        prob = calculate_probability(15.8, 0.3, 6, 16.0, 'above')
        assert prob > 0.80, f"Expected >80%, got {prob:.1%}"
        assert prob < 0.95, f"Expected <95%, got {prob:.1%}"
    
    def test_easy_win(self):
        """
        Already above threshold and trending up
        Current: 18°C, Trend: +0.5°C/hr, Hours: 4, Threshold: 16°C
        Should be very high probability (>95%)
        """
        prob = calculate_probability(18.0, 0.5, 4, 16.0, 'above')
        assert prob > 0.95, f"Expected >95%, got {prob:.1%}"
    
    def test_unlikely_scenario(self):
        """
        Far below threshold with negative trend
        Current: 10°C, Trend: -0.3°C/hr, Hours: 6, Threshold: 20°C
        Should be very low probability (<5%)
        """
        prob = calculate_probability(10.0, -0.3, 6, 20.0, 'above')
        assert prob < 0.05, f"Expected <5%, got {prob:.1%}"
    
    def test_coin_flip(self):
        """
        Projected temp equals threshold
        Current: 15°C, Trend: 0°C/hr, Hours: 6, Threshold: 15°C
        Should be around 50% (slightly less due to normal distribution)
        """
        prob = calculate_probability(15.0, 0.0, 6, 15.0, 'above')
        assert 0.45 < prob < 0.55, f"Expected ~50%, got {prob:.1%}"
    
    def test_zero_trend(self):
        """
        No temperature change expected
        Current: 20°C, Trend: 0°C/hr, Hours: 12, Threshold: 22°C
        """
        prob = calculate_probability(20.0, 0.0, 12, 22.0, 'above')
        # With RMSE 2.5°C, threshold is 0.8 std deviations away
        assert 0.15 < prob < 0.25, f"Expected ~20%, got {prob:.1%}"
    
    def test_long_forecast(self):
        """
        Long lead time should have lower certainty
        Current: 10°C, Trend: +0.5°C/hr, Hours: 60, Threshold: 35°C
        Projected: 40°C, but RMSE is 7.5°C (high uncertainty)
        """
        prob = calculate_probability(10.0, 0.5, 60, 35.0, 'above')
        # Should still be reasonably high but not extreme
        assert 0.60 < prob < 0.85, f"Expected 60-85%, got {prob:.1%}"


class TestProbabilityBelow:
    """Test probability calculations for 'below' threshold"""
    
    def test_cold_front_scenario(self):
        """
        Temperature dropping below threshold
        Current: 8°C, Trend: -0.4°C/hr, Hours: 10, Threshold: 5°C
        Projected: 8 - 4 = 4°C (below threshold)
        """
        prob = calculate_probability(8.0, -0.4, 10, 5.0, 'below')
        assert prob > 0.60, f"Expected >60%, got {prob:.1%}"
    
    def test_already_below(self):
        """
        Already below and continuing to drop
        Current: 3°C, Trend: -0.2°C/hr, Hours: 6, Threshold: 5°C
        Should be very high probability
        """
        prob = calculate_probability(3.0, -0.2, 6, 5.0, 'below')
        assert prob > 0.90, f"Expected >90%, got {prob:.1%}"
    
    def test_warming_trend(self):
        """
        Warming up, unlikely to drop below
        Current: 12°C, Trend: +0.5°C/hr, Hours: 8, Threshold: 10°C
        Should be low probability
        """
        prob = calculate_probability(12.0, 0.5, 8, 10.0, 'below')
        assert prob < 0.10, f"Expected <10%, got {prob:.1%}"


class TestRangeProbability:
    """Test probability calculations for temperature ranges"""
    
    def test_projected_in_middle(self):
        """
        Projected temp in middle of range
        Current: 10°C, Trend: +0.5°C/hr, Hours: 8, Range: 12-16°C
        Projected: 14°C (center of range)
        """
        prob = calculate_range_probability(10.0, 0.5, 8, 12.0, 16.0)
        assert prob > 0.50, f"Expected >50%, got {prob:.1%}"
        assert prob < 0.75, f"Expected <75%, got {prob:.1%}"
    
    def test_projected_below_range(self):
        """
        Projected temp below range
        Current: 5°C, Trend: +0.2°C/hr, Hours: 6, Range: 10-15°C
        Projected: 6.2°C (below range)
        """
        prob = calculate_range_probability(5.0, 0.2, 6, 10.0, 15.0)
        assert prob < 0.30, f"Expected <30%, got {prob:.1%}"
    
    def test_projected_above_range(self):
        """
        Projected temp above range
        Current: 20°C, Trend: +0.3°C/hr, Hours: 10, Range: 12-18°C
        Projected: 23°C (above range)
        """
        prob = calculate_range_probability(20.0, 0.3, 10, 12.0, 18.0)
        assert prob < 0.30, f"Expected <30%, got {prob:.1%}"
    
    def test_narrow_range(self):
        """
        Very narrow range (2°C)
        Current: 14°C, Trend: 0°C/hr, Hours: 6, Range: 14-16°C
        """
        prob = calculate_range_probability(14.0, 0.0, 6, 14.0, 16.0)
        assert 0.30 < prob < 0.60, f"Expected 30-60%, got {prob:.1%}"
    
    def test_wide_range(self):
        """
        Very wide range (10°C)
        Current: 15°C, Trend: 0°C/hr, Hours: 12, Range: 10-20°C
        """
        prob = calculate_range_probability(15.0, 0.0, 12, 10.0, 20.0)
        assert prob > 0.70, f"Expected >70%, got {prob:.1%}"


class TestConfidenceInterval:
    """Test confidence interval calculations"""
    
    def test_95_percent_ci(self):
        """
        95% confidence interval should be ~2 standard deviations
        Current: 15°C, Trend: +0.3°C/hr, Hours: 12
        Projected: 18.6°C, RMSE: 2.5°C
        95% CI should be roughly [13.6, 23.6]
        """
        lower, upper = calculate_confidence_interval(15.0, 0.3, 12, 0.95)
        projected = 15.0 + (0.3 * 12)
        
        # Check that interval is roughly ±2 * RMSE
        assert abs((projected - lower) - 4.9) < 0.5, f"Lower bound off: {lower}"
        assert abs((upper - projected) - 4.9) < 0.5, f"Upper bound off: {upper}"
    
    def test_short_lead_time_narrow_ci(self):
        """
        Short lead time should have narrower confidence interval
        Hours: 3 (RMSE 1.5°C) vs Hours: 60 (RMSE 7.5°C)
        """
        lower_short, upper_short = calculate_confidence_interval(15.0, 0.0, 3, 0.95)
        lower_long, upper_long = calculate_confidence_interval(15.0, 0.0, 60, 0.95)
        
        width_short = upper_short - lower_short
        width_long = upper_long - lower_long
        
        assert width_short < width_long, "Short-term CI should be narrower"
        assert width_long / width_short > 3, "Long-term CI should be significantly wider"


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_probability_bounds(self):
        """All probabilities should be between 0 and 1"""
        test_cases = [
            (0.0, 0.0, 24, 10.0, 'above'),
            (50.0, 2.0, 48, 0.0, 'above'),
            (-10.0, -1.0, 12, -20.0, 'below'),
        ]
        
        for args in test_cases:
            prob = calculate_probability(*args)
            assert 0.0 <= prob <= 1.0, f"Probability out of bounds: {prob}"
    
    def test_negative_temperatures(self):
        """Should handle negative temperatures correctly"""
        prob = calculate_probability(-5.0, -0.3, 8, -8.0, 'below')
        assert 0.0 <= prob <= 1.0
    
    def test_extreme_trends(self):
        """Should handle extreme temperature trends"""
        prob = calculate_probability(20.0, 5.0, 10, 60.0, 'above')
        assert 0.0 <= prob <= 1.0
    
    def test_zero_hours(self):
        """Should handle zero hours to resolution"""
        # When hours = 0, should be based on current temp only
        prob_above = calculate_probability(18.0, 0.5, 0, 16.0, 'above')
        assert prob_above > 0.90, "Current temp already above threshold"
        
        prob_below = calculate_probability(14.0, 0.5, 0, 16.0, 'above')
        assert prob_below < 0.10, "Current temp below threshold"


def test_integration_scenario():
    """
    Full integration test: ColdMath's $12,452 win
    Tokyo hitting 16°C on March 20
    Market priced at $0.02 (2% probability)
    Our model: ~85% probability
    Edge: 83% (massive mismatch)
    """
    # Scenario: 9:00 AM, market resolves at 11:59 PM (15 hours)
    current_temp = 15.8
    trend = 0.3  # +0.3°C per hour
    hours = 15
    threshold = 16.0
    
    prob = calculate_probability(current_temp, trend, hours, threshold, 'above')
    
    # Our model should show high probability
    assert prob > 0.75, f"Model probability too low: {prob:.1%}"
    
    # Calculate edge vs market
    market_price = 0.02
    edge = prob - market_price
    
    assert edge > 0.70, f"Edge too low: {edge:.1%}"
    
    # This should definitely be flagged for trading
    MIN_EDGE_ALERT = 0.15
    assert edge > MIN_EDGE_ALERT, "Signal should be flagged"
    
    print(f"\n✅ ColdMath Scenario Validation:")
    print(f"   Current: {current_temp}°C, Trend: +{trend}°C/hr")
    print(f"   Hours: {hours}, Threshold: {threshold}°C")
    print(f"   Our probability: {prob:.1%}")
    print(f"   Market price: {market_price:.1%}")
    print(f"   Edge: {edge:+.1%}")
    print(f"   Result: STRONG BUY signal\n")


if __name__ == "__main__":
    # Run pytest with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
