"""
METAR and TAF parser module using python-metar library.
Extracts structured weather data from METAR/TAF strings.
"""
from metar.Metar import Metar
from typing import Optional, Dict, Any
import re


def parse_metar(raw: str) -> Dict[str, Any]:
    """
    Parse METAR string into structured data.
    
    Args:
        raw: Raw METAR string (e.g., "KJFK 061451Z 27015G25KT 10SM FEW250 08/M03 A3012")
        
    Returns:
        Dictionary with parsed fields:
        {
            'temperature_c': float,
            'dewpoint_c': float,
            'wind_speed_kt': float,
            'wind_dir': int,
            'visibility_m': float,
            'pressure_hpa': float,
            'cloud_cover': str,
            'station': str,
            'time': datetime,
            'raw': str
        }
    """
    result = {
        'temperature_c': None,
        'dewpoint_c': None,
        'wind_speed_kt': None,
        'wind_dir': None,
        'visibility_m': None,
        'pressure_hpa': None,
        'cloud_cover': 'UNKNOWN',
        'station': None,
        'time': None,
        'raw': raw
    }
    
    try:
        # Parse using python-metar
        obs = Metar(raw)
        
        # Station
        result['station'] = obs.station_id
        
        # Time
        result['time'] = obs.time
        
        # Temperature (handle None and convert Value objects)
        if obs.temp:
            result['temperature_c'] = obs.temp.value("C")
        
        # Dewpoint (handle None and convert Value objects)
        if obs.dewpt:
            result['dewpoint_c'] = obs.dewpt.value("C")
        
        # Wind speed
        if obs.wind_speed:
            result['wind_speed_kt'] = obs.wind_speed.value("KT")
        
        # Wind direction (handle variable wind)
        if obs.wind_dir:
            if isinstance(obs.wind_dir, str):
                # Variable wind
                result['wind_dir'] = None
            else:
                result['wind_dir'] = int(obs.wind_dir.value())
        
        # Visibility
        if obs.vis:
            result['visibility_m'] = obs.vis.value("M")
        
        # Pressure
        if obs.press:
            result['pressure_hpa'] = obs.press.value("HPA")
        
        # Cloud cover (get most significant)
        if obs.sky:
            cloud_levels = []
            for sky_condition in obs.sky:
                cloud_levels.append(sky_condition[0])
            
            # Priority: OVC > BKN > SCT > FEW > SKC/CLR
            if "OVC" in cloud_levels:
                result['cloud_cover'] = "OVERCAST"
            elif "BKN" in cloud_levels:
                result['cloud_cover'] = "BROKEN"
            elif "SCT" in cloud_levels:
                result['cloud_cover'] = "SCATTERED"
            elif "FEW" in cloud_levels:
                result['cloud_cover'] = "FEW"
            elif "SKC" in cloud_levels or "CLR" in cloud_levels:
                result['cloud_cover'] = "CLEAR"
        
    except Exception as e:
        # If parsing fails, try to extract manually
        result = _parse_metar_fallback(raw)
    
    return result


def _parse_metar_fallback(raw: str) -> Dict[str, Any]:
    """
    Fallback parser using regex when python-metar fails.
    
    Args:
        raw: Raw METAR string
        
    Returns:
        Dictionary with parsed fields (best effort)
    """
    result = {
        'temperature_c': None,
        'dewpoint_c': None,
        'wind_speed_kt': None,
        'wind_dir': None,
        'visibility_m': None,
        'pressure_hpa': None,
        'cloud_cover': 'UNKNOWN',
        'station': None,
        'time': None,
        'raw': raw
    }
    
    # Extract station (first 4 letters)
    station_match = re.match(r'^([A-Z]{4})', raw)
    if station_match:
        result['station'] = station_match.group(1)
    
    # Extract temperature/dewpoint (e.g., "08/M03" or "M05/M10")
    temp_match = re.search(r'\s(M?\d{2})/(M?\d{2})\s', raw)
    if temp_match:
        temp_str = temp_match.group(1)
        dewp_str = temp_match.group(2)
        
        # Handle negative temps (M prefix)
        result['temperature_c'] = -float(temp_str[1:]) if temp_str.startswith('M') else float(temp_str)
        result['dewpoint_c'] = -float(dewp_str[1:]) if dewp_str.startswith('M') else float(dewp_str)
    
    # Extract wind (e.g., "27015KT" or "27015G25KT")
    wind_match = re.search(r'\s(\d{3}|VRB)(\d{2,3})(G\d{2,3})?KT\s', raw)
    if wind_match:
        dir_str = wind_match.group(1)
        result['wind_dir'] = int(dir_str) if dir_str != 'VRB' else None
        result['wind_speed_kt'] = float(wind_match.group(2))
    
    # Extract visibility (e.g., "10SM")
    vis_match = re.search(r'\s(\d+)SM\s', raw)
    if vis_match:
        vis_miles = float(vis_match.group(1))
        result['visibility_m'] = vis_miles * 1609.34  # miles to meters
    
    # Extract altimeter (e.g., "A3012")
    alt_match = re.search(r'\sA(\d{4})\s*$', raw)
    if alt_match:
        alt_inhg = float(alt_match.group(1)) / 100.0
        result['pressure_hpa'] = alt_inhg * 33.8639  # inHg to hPa
    
    # Extract cloud cover
    if "SKC" in raw or "CLR" in raw:
        result['cloud_cover'] = "CLEAR"
    elif "OVC" in raw:
        result['cloud_cover'] = "OVERCAST"
    elif "BKN" in raw:
        result['cloud_cover'] = "BROKEN"
    elif "SCT" in raw:
        result['cloud_cover'] = "SCATTERED"
    elif "FEW" in raw:
        result['cloud_cover'] = "FEW"
    
    return result


def parse_taf(raw: str) -> Dict[str, Any]:
    """
    Parse TAF string to extract forecast temperature range.
    
    Args:
        raw: Raw TAF string
        
    Returns:
        Dictionary with forecast data:
        {
            'forecast_high': float,
            'forecast_low': float,
            'significant_weather': list[str],
            'wind_changes': list[str]
        }
    """
    result = {
        'forecast_high': None,
        'forecast_low': None,
        'significant_weather': [],
        'wind_changes': []
    }
    
    # Extract all temperature mentions (TX and TN)
    # Format: TX15/0612Z TN08/0600Z
    temps = []
    
    # Maximum temperature (TX)
    tx_matches = re.findall(r'TX(M?\d{2})/\d{4}Z', raw)
    for tx in tx_matches:
        temp = -float(tx[1:]) if tx.startswith('M') else float(tx)
        temps.append(temp)
    
    # Minimum temperature (TN)
    tn_matches = re.findall(r'TN(M?\d{2})/\d{4}Z', raw)
    for tn in tn_matches:
        temp = -float(tn[1:]) if tn.startswith('M') else float(tn)
        temps.append(temp)
    
    if temps:
        result['forecast_high'] = max(temps)
        result['forecast_low'] = min(temps)
    
    # Extract significant weather codes
    wx_codes = re.findall(r'\s(-|\+)?(TS|RA|SN|FG|BR|DZ|GR|GS|PL|SG|IC|UP|FZ)\s', raw)
    result['significant_weather'] = [''.join(wx) for wx in wx_codes]
    
    # Extract wind changes (simplified - just note if winds vary significantly)
    wind_matches = re.findall(r'(\d{3}|VRB)(\d{2,3})KT', raw)
    if len(wind_matches) > 1:
        wind_speeds = [int(w[1]) for w in wind_matches]
        if max(wind_speeds) - min(wind_speeds) > 10:
            result['wind_changes'].append(f"Variable {min(wind_speeds)}-{max(wind_speeds)}KT")
    
    return result


if __name__ == "__main__":
    # Test cases
    test_metars = [
        "KJFK 061451Z 27015G25KT 10SM FEW250 08/M03 A3012",
        "EGLL 061420Z 24008KT 9999 FEW040 11/07 Q1023",
        "RJTT 061430Z 36012KT 9999 FEW025 SCT035 16/09 Q1015",
        "VIDP 061430Z 09004KT 4000 HZ NSC 28/14 Q1012",
        "YSSY 061430Z 03015KT CAVOK 22/16 Q1018",
    ]
    
    print("Testing METAR parser:")
    print("=" * 70)
    
    for metar in test_metars:
        print(f"\nRaw: {metar}")
        parsed = parse_metar(metar)
        print(f"Station: {parsed['station']}")
        print(f"Temp: {parsed['temperature_c']}°C, Dewpoint: {parsed['dewpoint_c']}°C")
        print(f"Wind: {parsed['wind_dir']}° @ {parsed['wind_speed_kt']}kt")
        print(f"Visibility: {parsed['visibility_m']}m")
        print(f"Pressure: {parsed['pressure_hpa']}hPa")
        print(f"Clouds: {parsed['cloud_cover']}")
    
    print("\n" + "=" * 70)
    print("\nTesting TAF parser:")
    test_taf = "TAF KJFK 061120Z 0612/0718 27015G25KT P6SM FEW250 TX15/0621Z TN05/0612Z"
    print(f"Raw: {test_taf}")
    parsed_taf = parse_taf(test_taf)
    print(f"Forecast High: {parsed_taf['forecast_high']}°C")
    print(f"Forecast Low: {parsed_taf['forecast_low']}°C")
    print(f"Significant Weather: {parsed_taf['significant_weather']}")
