"""
City to ICAO airport code mapping for weather data.
Covers 50 major cities worldwide with primary and alternate codes.
"""

# City -> ICAO mapping (primary codes)
CITY_TO_ICAO = {
    # United States (15 cities)
    "New York": "KJFK",
    "Los Angeles": "KLAX",
    "Chicago": "KORD",
    "Houston": "KIAH",
    "Phoenix": "KPHX",
    "Philadelphia": "KPHL",
    "San Antonio": "KSAT",
    "San Diego": "KSAN",
    "Dallas": "KDFW",
    "San Jose": "KSJC",
    "Austin": "KAUS",
    "Jacksonville": "KJAX",
    "San Francisco": "KSFO",
    "Seattle": "KSEA",
    "Denver": "KDEN",
    
    # Europe (8 cities)
    "London": "EGLL",
    "Paris": "LFPG",
    "Berlin": "EDDB",
    "Madrid": "LEMD",
    "Rome": "LIRF",
    "Amsterdam": "EHAM",
    "Brussels": "EBBR",
    "Vienna": "LOWW",
    
    # Asia-Pacific (7 cities)
    "Tokyo": "RJTT",
    "Seoul": "RKSI",
    "Beijing": "ZBAA",
    "Shanghai": "ZSSS",
    "Hong Kong": "VHHH",
    "Singapore": "WSSS",
    "Sydney": "YSSY",
    
    # India (10 cities)
    "Delhi": "VIDP",
    "Mumbai": "VABB",
    "Bangalore": "VOBL",
    "Kolkata": "VECC",
    "Chennai": "VOMM",
    "Hyderabad": "VOHS",
    "Pune": "VAPO",
    "Ahmedabad": "VAAH",
    "Jaipur": "VIJP",
    "Goa": "VOGO",
    
    # Americas (5 cities)
    "Toronto": "CYYZ",
    "Mexico City": "MMMX",
    "São Paulo": "SBGR",
    "Buenos Aires": "SAEZ",
    "Lima": "SPJC",
    
    # Middle East & Africa (5 cities)
    "Dubai": "OMDB",
    "Tel Aviv": "LLBG",
    "Johannesburg": "FAJS",
    "Cairo": "HECA",
    "Istanbul": "LTFM",
}

# Alternate ICAO codes for cities with multiple airports
ALTERNATE_CODES = {
    "New York": ["KLGA", "KEWR"],  # LaGuardia, Newark
    "Los Angeles": ["KBUR", "KSNA"],  # Burbank, John Wayne
    "Chicago": ["KMDW"],  # Midway
    "London": ["EGSS", "EGLC"],  # Stansted, City
    "Paris": ["LFPO"],  # Orly
    "Tokyo": ["RJAA"],  # Narita
    "São Paulo": ["SBSP"],  # Congonhas
    "Delhi": ["VIDD"],  # Indira Gandhi (alternate code)
    "Mumbai": ["VABB"],  # Chhatrapati Shivaji
    "Istanbul": ["LTBA"],  # Atatürk
}

# Reverse mapping: ICAO -> City
ICAO_TO_CITY = {}
for city, icao in CITY_TO_ICAO.items():
    ICAO_TO_CITY[icao] = city
    # Add alternates
    if city in ALTERNATE_CODES:
        for alt_icao in ALTERNATE_CODES[city]:
            ICAO_TO_CITY[alt_icao] = city


def get_icao(city_name: str) -> str:
    """
    Get primary ICAO code for a city.
    
    Args:
        city_name: Name of the city
        
    Returns:
        ICAO code (4 letters)
        
    Raises:
        KeyError: If city not found
    """
    return CITY_TO_ICAO[city_name]


def get_city(icao_code: str) -> str:
    """
    Get city name from ICAO code.
    
    Args:
        icao_code: 4-letter ICAO airport code
        
    Returns:
        City name
        
    Raises:
        KeyError: If ICAO code not found
    """
    return ICAO_TO_CITY[icao_code]


def get_all_stations() -> list[str]:
    """
    Get list of all primary ICAO station codes.
    
    Returns:
        List of ICAO codes (sorted alphabetically)
    """
    return sorted(CITY_TO_ICAO.values())


def get_all_cities() -> list[str]:
    """
    Get list of all city names.
    
    Returns:
        List of city names (sorted alphabetically)
    """
    return sorted(CITY_TO_ICAO.keys())


def get_alternates(city_name: str) -> list[str]:
    """
    Get alternate ICAO codes for a city.
    
    Args:
        city_name: Name of the city
        
    Returns:
        List of alternate ICAO codes (empty if none)
    """
    return ALTERNATE_CODES.get(city_name, [])


# Quick stats
def get_stats():
    """Get statistics about the city map."""
    return {
        "total_cities": len(CITY_TO_ICAO),
        "total_icao_codes": len(ICAO_TO_CITY),
        "cities_with_alternates": len(ALTERNATE_CODES),
        "total_stations": len(get_all_stations()),
    }


if __name__ == "__main__":
    # Test the module
    print("City Map Statistics:")
    stats = get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\nSample mappings:")
    for city in ["New York", "London", "Tokyo", "Delhi", "Dubai"]:
        icao = get_icao(city)
        alts = get_alternates(city)
        print(f"  {city}: {icao}" + (f" (alternates: {', '.join(alts)})" if alts else ""))
    
    print(f"\nAll stations ({len(get_all_stations())}):")
    print(f"  {', '.join(get_all_stations()[:10])}...")
