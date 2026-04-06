"""
Market Matcher — Parse Polymarket titles and match to ICAO stations
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Matched market details"""
    icao: str
    city: str
    threshold_type: str  # 'high_above', 'high_below', 'low_above', 'low_below', 'range', 'rain_above', 'snow_above'
    threshold_value: float
    threshold_unit: str  # 'C', 'F', 'inches', 'mm'
    threshold_max: Optional[float] = None  # For range type
    market_date: Optional[datetime] = None


class MarketMatcher:
    """Match Polymarket weather market titles to ICAO stations"""
    
    def __init__(self, city_map: dict = None):
        """
        Initialize with city → ICAO mapping
        city_map format: {"New York": "KJFK", "Tokyo": "RJTT", ...}
        """
        self.city_map = city_map or {}
        
        # Common city name variations
        self.city_aliases = {
            "nyc": "New York",
            "new york city": "New York",
            "la": "Los Angeles",
            "sf": "San Francisco",
            "dc": "Washington",
        }
    
    def normalize_city(self, city: str) -> str:
        """Normalize city name for matching"""
        city_lower = city.lower().strip()
        return self.city_aliases.get(city_lower, city.title())
    
    def fuzzy_match_city(self, text: str) -> Optional[str]:
        """
        Fuzzy match city name in text
        Returns normalized city name if found
        """
        text_lower = text.lower()
        
        # Try exact matches first
        for city in self.city_map.keys():
            if city.lower() in text_lower:
                return city
        
        # Try aliases
        for alias, city in self.city_aliases.items():
            if alias in text_lower and city in self.city_map:
                return city
        
        return None
    
    def extract_temperature(self, text: str) -> Optional[Tuple[float, str]]:
        """
        Extract temperature value and unit from text
        Returns (value, unit) or None
        """
        # Pattern: "75°F", "75 degrees F", "75F", "16°C", "16 celsius"
        patterns = [
            r'(\d+\.?\d*)\s*°?\s*([CF])\b',
            r'(\d+\.?\d*)\s*degrees?\s*([CF])',
            r'(\d+\.?\d*)\s*celsius',
            r'(\d+\.?\d*)\s*fahrenheit'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                unit = match.group(2).upper() if len(match.groups()) > 1 else ('C' if 'celsius' in text.lower() else 'F')
                return (value, unit)
        
        return None
    
    def extract_range(self, text: str) -> Optional[Tuple[float, float, str]]:
        """
        Extract temperature range from text
        Returns (min, max, unit) or None
        """
        # Pattern: "55-60°F", "55 to 60 degrees", "between 55 and 60F"
        patterns = [
            r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*°?\s*([CF])',
            r'(\d+\.?\d*)\s+to\s+(\d+\.?\d*)\s*°?\s*([CF])',
            r'between\s+(\d+\.?\d*)\s+and\s+(\d+\.?\d*)\s*°?\s*([CF])'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                min_val = float(match.group(1))
                max_val = float(match.group(2))
                unit = match.group(3).upper()
                return (min_val, max_val, unit)
        
        return None
    
    def extract_precipitation(self, text: str) -> Optional[Tuple[float, str]]:
        """
        Extract precipitation amount and unit
        Returns (value, unit) or None
        """
        # Pattern: "0.1 inches", "5mm", "0.5 in"
        patterns = [
            r'(\d+\.?\d*)\s*(inches?|in)\b',
            r'(\d+\.?\d*)\s*(mm|millimeters?)\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                unit = match.group(2).lower()
                unit = 'inches' if unit.startswith('in') else 'mm'
                return (value, unit)
        
        return None
    
    def convert_to_celsius(self, value: float, unit: str) -> float:
        """Convert temperature to Celsius"""
        if unit == 'F':
            return (value - 32) * 5/9
        return value
    
    def determine_threshold_type(self, text: str) -> str:
        """
        Determine if market is about high/low/range/precipitation
        """
        text_lower = text.lower()
        
        # Precipitation
        if any(word in text_lower for word in ['rain', 'snow', 'precipitation']):
            if 'snow' in text_lower:
                return 'snow_above'
            return 'rain_above'
        
        # Range
        if re.search(r'\d+\s*-\s*\d+', text):
            return 'range'
        
        # High/Low temperature
        is_high = 'high' in text_lower or 'maximum' in text_lower or 'max' in text_lower
        is_low = 'low' in text_lower or 'minimum' in text_lower or 'min' in text_lower
        
        is_above = any(word in text_lower for word in ['exceed', 'above', 'over', 'more than', 'at least', 'or higher'])
        is_below = any(word in text_lower for word in ['below', 'under', 'less than', 'at most', 'or lower'])
        
        if is_high and is_above:
            return 'high_above'
        if is_high and is_below:
            return 'high_below'
        if is_low and is_above:
            return 'low_above'
        if is_low and is_below:
            return 'low_below'
        
        # Default: assume "high above" if ambiguous
        return 'high_above'
    
    def extract_date(self, text: str) -> Optional[datetime]:
        """
        Extract date from market title
        Returns datetime or None
        """
        # Pattern: "April 10", "on April 6", "March 20th"
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        
        for month_name, month_num in months.items():
            pattern = rf'{month_name}\s+(\d+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                day = int(match.group(1))
                year = datetime.utcnow().year
                try:
                    return datetime(year, month_num, day)
                except ValueError:
                    pass
        
        return None
    
    def match_market(self, title: str) -> Optional[MatchResult]:
        """
        Parse market title and match to ICAO station
        
        Examples:
        - "Will the high temperature in New York City exceed 75°F on April 10?"
          → KJFK, high_above, 23.9, C
        - "Will Tokyo's high temperature be 16°C or above on April 6?"
          → RJTT, high_above, 16, C
        - "Will it rain more than 0.1 inches in London on April 7?"
          → EGLL, rain_above, 0.1, inches
        - "New York City high temperature 55-60°F on April 8?"
          → KJFK, range, 12.8-15.6, C
        
        Returns MatchResult or None if can't parse
        """
        try:
            # Extract city
            city = self.fuzzy_match_city(title)
            if not city or city not in self.city_map:
                logger.debug(f"No city match for: {title}")
                return None
            
            icao = self.city_map[city]
            
            # Determine type
            threshold_type = self.determine_threshold_type(title)
            
            # Extract date
            market_date = self.extract_date(title)
            
            # Handle precipitation
            if 'rain' in threshold_type or 'snow' in threshold_type:
                precip = self.extract_precipitation(title)
                if not precip:
                    return None
                value, unit = precip
                
                return MatchResult(
                    icao=icao,
                    city=city,
                    threshold_type=threshold_type,
                    threshold_value=value,
                    threshold_unit=unit,
                    market_date=market_date
                )
            
            # Handle temperature range
            if threshold_type == 'range':
                range_data = self.extract_range(title)
                if not range_data:
                    return None
                min_val, max_val, unit = range_data
                
                # Convert to Celsius
                min_c = self.convert_to_celsius(min_val, unit)
                max_c = self.convert_to_celsius(max_val, unit)
                
                return MatchResult(
                    icao=icao,
                    city=city,
                    threshold_type=threshold_type,
                    threshold_value=min_c,
                    threshold_max=max_c,
                    threshold_unit='C',
                    market_date=market_date
                )
            
            # Handle single temperature threshold
            temp_data = self.extract_temperature(title)
            if not temp_data:
                logger.debug(f"No temperature found in: {title}")
                return None
            
            value, unit = temp_data
            value_c = self.convert_to_celsius(value, unit)
            
            return MatchResult(
                icao=icao,
                city=city,
                threshold_type=threshold_type,
                threshold_value=value_c,
                threshold_unit='C',
                market_date=market_date
            )
            
        except Exception as e:
            logger.error(f"Error matching market '{title}': {e}")
            return None


def test_matcher():
    """Test market matcher with example titles"""
    
    # Sample city map
    city_map = {
        "New York": "KJFK",
        "Tokyo": "RJTT",
        "London": "EGLL",
        "Chicago": "KORD",
        "Lucknow": "VILK"
    }
    
    matcher = MarketMatcher(city_map)
    
    test_cases = [
        "Will the high temperature in New York City exceed 75°F on April 10?",
        "Will Tokyo's high temperature be 16°C or above on April 6?",
        "Will it rain more than 0.1 inches in London on April 7?",
        "New York City high temperature 55-60°F on April 8?",
        "Will Chicago low temperature drop below 40°F on March 15?",
        "Lucknow high temperature will exceed 39°C on March 7?"
    ]
    
    print("\nMarket Matcher Test Results:\n")
    for title in test_cases:
        result = matcher.match_market(title)
        if result:
            print(f"✅ Title: {title}")
            print(f"   → ICAO: {result.icao}, City: {result.city}")
            print(f"   → Type: {result.threshold_type}")
            print(f"   → Threshold: {result.threshold_value:.1f}{result.threshold_unit}", end="")
            if result.threshold_max:
                print(f" to {result.threshold_max:.1f}{result.threshold_unit}", end="")
            print(f"\n   → Date: {result.market_date}")
        else:
            print(f"❌ Could not match: {title}")
        print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_matcher()
