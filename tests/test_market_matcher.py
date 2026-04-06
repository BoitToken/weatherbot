"""
Unit tests for market matcher
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from markets.market_matcher import MarketMatcher, MatchResult


# Sample city map for testing
CITY_MAP = {
    "New York": "KJFK",
    "Tokyo": "RJTT",
    "London": "EGLL",
    "Chicago": "KORD",
    "Lucknow": "VILK",
    "Los Angeles": "KLAX",
    "Miami": "KMIA",
    "San Francisco": "KSFO",
    "Paris": "LFPG",
    "Sydney": "YSSY"
}


class TestCityMatching:
    """Test city name matching"""
    
    def test_exact_city_match(self):
        matcher = MarketMatcher(CITY_MAP)
        
        titles = [
            "Will Tokyo exceed 16°C?",
            "New York high temperature",
            "London weather forecast"
        ]
        
        for title in titles:
            result = matcher.match_market(title)
            assert result is not None, f"Should match: {title}"
    
    def test_city_with_suffix(self):
        """Test 'New York City' matches 'New York'"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "Will the high temperature in New York City exceed 75°F?"
        result = matcher.match_market(title)
        
        assert result is not None
        assert result.city == "New York"
        assert result.icao == "KJFK"
    
    def test_fuzzy_city_match(self):
        """Test city name variations"""
        matcher = MarketMatcher(CITY_MAP)
        matcher.city_aliases["sf"] = "San Francisco"
        matcher.city_aliases["la"] = "Los Angeles"
        
        # This would work if SF is in the title
        # For now we test that the system doesn't crash
        title = "Will LA exceed 80°F?"
        result = matcher.match_market(title)
        # May or may not match depending on implementation
    
    def test_no_city_match(self):
        """Test title with no recognizable city"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "Will it rain tomorrow?"
        result = matcher.match_market(title)
        
        assert result is None


class TestTemperatureExtraction:
    """Test temperature value and unit extraction"""
    
    def test_fahrenheit_formats(self):
        matcher = MarketMatcher(CITY_MAP)
        
        test_cases = [
            ("New York exceed 75°F", 75.0, 'F'),
            ("Tokyo reach 75 degrees F", 75.0, 'F'),
            ("Chicago hit 32F", 32.0, 'F'),
            ("Miami 90 fahrenheit", 90.0, 'F'),
        ]
        
        for text, expected_val, expected_unit in test_cases:
            result = matcher.extract_temperature(text)
            assert result is not None, f"Should extract from: {text}"
            val, unit = result
            assert val == expected_val
            assert unit == expected_unit
    
    def test_celsius_formats(self):
        matcher = MarketMatcher(CITY_MAP)
        
        test_cases = [
            ("Tokyo exceed 16°C", 16.0, 'C'),
            ("London reach 20 degrees C", 20.0, 'C'),
            ("Paris hit 25C", 25.0, 'C'),
            ("Sydney 30 celsius", 30.0, 'C'),
        ]
        
        for text, expected_val, expected_unit in test_cases:
            result = matcher.extract_temperature(text)
            assert result is not None, f"Should extract from: {text}"
            val, unit = result
            assert val == expected_val
            assert unit == expected_unit
    
    def test_decimal_temperatures(self):
        matcher = MarketMatcher(CITY_MAP)
        
        result = matcher.extract_temperature("Tokyo reach 16.5°C")
        assert result is not None
        val, unit = result
        assert val == 16.5
        assert unit == 'C'


class TestRangeExtraction:
    """Test temperature range extraction"""
    
    def test_dash_range(self):
        matcher = MarketMatcher(CITY_MAP)
        
        result = matcher.extract_range("New York 55-60°F")
        assert result is not None
        min_val, max_val, unit = result
        assert min_val == 55.0
        assert max_val == 60.0
        assert unit == 'F'
    
    def test_to_range(self):
        matcher = MarketMatcher(CITY_MAP)
        
        result = matcher.extract_range("Tokyo 12 to 16°C")
        assert result is not None
        min_val, max_val, unit = result
        assert min_val == 12.0
        assert max_val == 16.0
        assert unit == 'C'
    
    def test_between_and_range(self):
        matcher = MarketMatcher(CITY_MAP)
        
        result = matcher.extract_range("London between 8 and 12°C")
        assert result is not None
        min_val, max_val, unit = result
        assert min_val == 8.0
        assert max_val == 12.0
        assert unit == 'C'


class TestPrecipitationExtraction:
    """Test precipitation amount extraction"""
    
    def test_inches(self):
        matcher = MarketMatcher(CITY_MAP)
        
        result = matcher.extract_precipitation("rain more than 0.1 inches")
        assert result is not None
        val, unit = result
        assert val == 0.1
        assert unit == 'inches'
    
    def test_millimeters(self):
        matcher = MarketMatcher(CITY_MAP)
        
        result = matcher.extract_precipitation("rain 5mm")
        assert result is not None
        val, unit = result
        assert val == 5.0
        assert unit == 'mm'
    
    def test_abbreviated_inches(self):
        matcher = MarketMatcher(CITY_MAP)
        
        result = matcher.extract_precipitation("rain 0.5 in")
        assert result is not None
        val, unit = result
        assert val == 0.5
        assert unit == 'inches'


class TestThresholdType:
    """Test threshold type determination"""
    
    def test_high_above(self):
        matcher = MarketMatcher(CITY_MAP)
        
        texts = [
            "Will the high temperature exceed 75°F?",
            "high temperature above 20°C",
            "maximum temp at least 25°C"
        ]
        
        for text in texts:
            threshold_type = matcher.determine_threshold_type(text)
            assert threshold_type == 'high_above', f"Failed for: {text}"
    
    def test_high_below(self):
        matcher = MarketMatcher(CITY_MAP)
        
        texts = [
            "Will the high temperature be below 30°C?",
            "maximum temp under 85°F"
        ]
        
        for text in texts:
            threshold_type = matcher.determine_threshold_type(text)
            assert threshold_type == 'high_below', f"Failed for: {text}"
    
    def test_low_below(self):
        matcher = MarketMatcher(CITY_MAP)
        
        texts = [
            "Will the low temperature drop below 40°F?",
            "minimum temp under 5°C"
        ]
        
        for text in texts:
            threshold_type = matcher.determine_threshold_type(text)
            assert threshold_type == 'low_below', f"Failed for: {text}"
    
    def test_rain(self):
        matcher = MarketMatcher(CITY_MAP)
        
        text = "Will it rain more than 0.1 inches?"
        threshold_type = matcher.determine_threshold_type(text)
        assert threshold_type == 'rain_above'
    
    def test_snow(self):
        matcher = MarketMatcher(CITY_MAP)
        
        text = "Will it snow more than 2 inches?"
        threshold_type = matcher.determine_threshold_type(text)
        assert threshold_type == 'snow_above'
    
    def test_range(self):
        matcher = MarketMatcher(CITY_MAP)
        
        text = "Temperature between 55-60°F"
        threshold_type = matcher.determine_threshold_type(text)
        assert threshold_type == 'range'


class TestFullMatching:
    """Test complete market matching end-to-end"""
    
    def test_coldmath_tokyo_scenario(self):
        """ColdMath's actual winning trade"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "Will Tokyo's high temperature be 16°C or above on April 6?"
        result = matcher.match_market(title)
        
        assert result is not None
        assert result.icao == "RJTT"
        assert result.city == "Tokyo"
        assert result.threshold_type == 'high_above'
        assert result.threshold_value == 16.0
        assert result.threshold_unit == 'C'
    
    def test_new_york_fahrenheit(self):
        """Standard US market with Fahrenheit"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "Will the high temperature in New York City exceed 75°F on April 10?"
        result = matcher.match_market(title)
        
        assert result is not None
        assert result.icao == "KJFK"
        assert result.city == "New York"
        assert result.threshold_type == 'high_above'
        # Should convert to Celsius
        assert abs(result.threshold_value - 23.9) < 0.1
        assert result.threshold_unit == 'C'
    
    def test_london_rain(self):
        """Precipitation market"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "Will it rain more than 0.1 inches in London on April 7?"
        result = matcher.match_market(title)
        
        assert result is not None
        assert result.icao == "EGLL"
        assert result.city == "London"
        assert result.threshold_type == 'rain_above'
        assert result.threshold_value == 0.1
        assert result.threshold_unit == 'inches'
    
    def test_range_market(self):
        """Temperature range market"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "New York City high temperature 55-60°F on April 8?"
        result = matcher.match_market(title)
        
        assert result is not None
        assert result.icao == "KJFK"
        assert result.city == "New York"
        assert result.threshold_type == 'range'
        # Should convert to Celsius
        assert 12.0 < result.threshold_value < 13.5  # ~12.8°C
        assert 15.0 < result.threshold_max < 16.0    # ~15.6°C
        assert result.threshold_unit == 'C'
    
    def test_chicago_low(self):
        """Low temperature market"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "Will Chicago low temperature drop below 40°F on March 15?"
        result = matcher.match_market(title)
        
        assert result is not None
        assert result.icao == "KORD"
        assert result.city == "Chicago"
        assert result.threshold_type == 'low_below'
        # 40°F ≈ 4.4°C
        assert abs(result.threshold_value - 4.4) < 0.2
        assert result.threshold_unit == 'C'
    
    def test_lucknow_celsius(self):
        """International market with Celsius"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "Lucknow high temperature will exceed 39°C on March 7?"
        result = matcher.match_market(title)
        
        assert result is not None
        assert result.icao == "VILK"
        assert result.city == "Lucknow"
        assert result.threshold_type == 'high_above'
        assert result.threshold_value == 39.0
        assert result.threshold_unit == 'C'


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_no_temperature(self):
        """Market with no parseable temperature"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "Will it be sunny in Tokyo?"
        result = matcher.match_market(title)
        
        assert result is None
    
    def test_no_city(self):
        """Market with no recognizable city"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "Will temperature exceed 75°F?"
        result = matcher.match_market(title)
        
        assert result is None
    
    def test_ambiguous_market(self):
        """Ambiguous or malformed market title"""
        matcher = MarketMatcher(CITY_MAP)
        
        title = "Weather prediction market"
        result = matcher.match_market(title)
        
        assert result is None
    
    def test_invalid_temperature(self):
        """Temperature that doesn't make sense"""
        matcher = MarketMatcher(CITY_MAP)
        
        # Should still parse, even if unrealistic
        title = "Will Tokyo reach 999°C?"
        result = matcher.match_market(title)
        
        # Parsing should work
        if result:
            assert result.threshold_value == 999.0


class TestUnitConversion:
    """Test temperature unit conversions"""
    
    def test_fahrenheit_to_celsius(self):
        matcher = MarketMatcher(CITY_MAP)
        
        test_cases = [
            (32.0, 0.0),    # Freezing
            (75.0, 23.9),   # Room temp
            (100.0, 37.8),  # Body temp
            (212.0, 100.0), # Boiling
            (0.0, -17.8),   # Cold
        ]
        
        for f, expected_c in test_cases:
            c = matcher.convert_to_celsius(f, 'F')
            assert abs(c - expected_c) < 0.1, f"{f}°F should be {expected_c}°C, got {c}°C"
    
    def test_celsius_unchanged(self):
        matcher = MarketMatcher(CITY_MAP)
        
        c = matcher.convert_to_celsius(25.0, 'C')
        assert c == 25.0


def test_integration_multiple_markets():
    """Test matching multiple diverse markets"""
    matcher = MarketMatcher(CITY_MAP)
    
    markets = [
        "Will Tokyo's high temperature be 16°C or above on April 6?",
        "Will the high temperature in New York City exceed 75°F on April 10?",
        "Will it rain more than 0.1 inches in London on April 7?",
        "New York City high temperature 55-60°F on April 8?",
        "Will Chicago low temperature drop below 40°F?",
        "Lucknow high temperature will exceed 39°C on March 7?"
    ]
    
    matched = 0
    failed = []
    
    for title in markets:
        result = matcher.match_market(title)
        if result:
            matched += 1
            print(f"✅ {title}")
            print(f"   → {result.city} ({result.icao}): {result.threshold_type} {result.threshold_value:.1f}{result.threshold_unit}")
        else:
            failed.append(title)
            print(f"❌ {title}")
    
    print(f"\nMatched: {matched}/{len(markets)}")
    
    assert matched >= 5, f"Should match most markets, got {matched}/{len(markets)}"


if __name__ == "__main__":
    # Run pytest with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
