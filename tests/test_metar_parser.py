"""
Unit tests for METAR parser.
Tests parsing of real METAR strings from various weather conditions.
"""
import pytest
from src.data.metar_parser import parse_metar, parse_taf


class TestMetarParser:
    """Test cases for METAR parsing."""
    
    def test_parse_standard_metar(self):
        """Test parsing a standard METAR with common fields."""
        metar = "KJFK 061451Z 27015G25KT 10SM FEW250 08/M03 A3012"
        result = parse_metar(metar)
        
        assert result['station'] == 'KJFK'
        assert result['temperature_c'] == pytest.approx(8.0, abs=0.1)
        assert result['dewpoint_c'] == pytest.approx(-3.0, abs=0.1)
        assert result['wind_speed_kt'] == pytest.approx(15.0, abs=0.1)
        assert result['wind_dir'] == 270
        assert result['cloud_cover'] == 'FEW'
        assert result['raw'] == metar
    
    def test_parse_negative_temperature(self):
        """Test parsing METAR with negative temperature (M prefix)."""
        metar = "EGLL 061420Z 24008KT 9999 FEW040 M05/M10 Q1023"
        result = parse_metar(metar)
        
        assert result['station'] == 'EGLL'
        assert result['temperature_c'] == pytest.approx(-5.0, abs=0.1)
        assert result['dewpoint_c'] == pytest.approx(-10.0, abs=0.1)
        assert result['wind_speed_kt'] == pytest.approx(8.0, abs=0.1)
        assert result['wind_dir'] == 240
    
    def test_parse_overcast_conditions(self):
        """Test parsing METAR with overcast cloud cover."""
        metar = "RJTT 061430Z 36012KT 9999 OVC035 16/09 Q1015"
        result = parse_metar(metar)
        
        assert result['station'] == 'RJTT'
        assert result['temperature_c'] == pytest.approx(16.0, abs=0.1)
        assert result['dewpoint_c'] == pytest.approx(9.0, abs=0.1)
        assert result['cloud_cover'] == 'OVERCAST'
    
    def test_parse_clear_sky(self):
        """Test parsing METAR with clear sky (SKC)."""
        metar = "YSSY 061430Z 03015KT CAVOK 22/16 Q1018"
        result = parse_metar(metar)
        
        assert result['station'] == 'YSSY'
        assert result['temperature_c'] == pytest.approx(22.0, abs=0.1)
        assert result['dewpoint_c'] == pytest.approx(16.0, abs=0.1)
        # CAVOK implies clear sky
    
    def test_parse_haze_conditions(self):
        """Test parsing METAR with haze and reduced visibility."""
        metar = "VIDP 061430Z 09004KT 4000 HZ NSC 28/14 Q1012"
        result = parse_metar(metar)
        
        assert result['station'] == 'VIDP'
        assert result['temperature_c'] == pytest.approx(28.0, abs=0.1)
        assert result['dewpoint_c'] == pytest.approx(14.0, abs=0.1)
        assert result['wind_speed_kt'] == pytest.approx(4.0, abs=0.1)
    
    def test_parse_variable_wind(self):
        """Test parsing METAR with variable wind direction."""
        metar = "KORD 061456Z VRB03KT 10SM CLR 15/M02 A3015"
        result = parse_metar(metar)
        
        assert result['station'] == 'KORD'
        assert result['temperature_c'] == pytest.approx(15.0, abs=0.1)
        assert result['dewpoint_c'] == pytest.approx(-2.0, abs=0.1)
        assert result['wind_speed_kt'] == pytest.approx(3.0, abs=0.1)
        assert result['wind_dir'] is None  # Variable wind has no direction
        assert result['cloud_cover'] == 'CLEAR'
    
    def test_parse_multiple_cloud_layers(self):
        """Test parsing METAR with multiple cloud layers (uses most significant)."""
        metar = "KLAX 061453Z 25008KT 10SM FEW015 SCT025 BKN035 18/12 A2990"
        result = parse_metar(metar)
        
        assert result['station'] == 'KLAX'
        assert result['temperature_c'] == pytest.approx(18.0, abs=0.1)
        # Should report BROKEN as most significant (BKN > SCT > FEW)
        assert result['cloud_cover'] == 'BROKEN'
    
    def test_parse_thunderstorm(self):
        """Test parsing METAR with thunderstorm."""
        metar = "KMIA 061453Z 18012KT 5SM +TSRA BKN020CB 25/22 A2985"
        result = parse_metar(metar)
        
        assert result['station'] == 'KMIA'
        assert result['temperature_c'] == pytest.approx(25.0, abs=0.1)
        assert result['cloud_cover'] == 'BROKEN'


class TestTafParser:
    """Test cases for TAF parsing."""
    
    def test_parse_simple_taf(self):
        """Test parsing TAF with temperature forecast."""
        taf = "TAF KJFK 061120Z 0612/0718 27015G25KT P6SM FEW250 TX15/0621Z TN05/0612Z"
        result = parse_taf(taf)
        
        assert result['forecast_high'] == 15.0
        assert result['forecast_low'] == 5.0
    
    def test_parse_taf_negative_temps(self):
        """Test parsing TAF with negative temperatures."""
        taf = "TAF CYYZ 061120Z 0612/0718 30012KT P6SM FEW050 TXM02/0618Z TNM10/0606Z"
        result = parse_taf(taf)
        
        assert result['forecast_high'] == -2.0
        assert result['forecast_low'] == -10.0
    
    def test_parse_taf_with_weather(self):
        """Test parsing TAF with significant weather codes."""
        taf = "TAF EGLL 061120Z 0612/0718 24012KT 9999 -RA SCT020 TX12/0615Z TN08/0606Z"
        result = parse_taf(taf)
        
        assert result['forecast_high'] == 12.0
        assert result['forecast_low'] == 8.0
        assert 'RA' in str(result['significant_weather'])  # Rain
    
    def test_parse_taf_no_temps(self):
        """Test parsing TAF without temperature forecast."""
        taf = "TAF YSSY 061120Z 0612/0718 03015KT 9999 SCT025"
        result = parse_taf(taf)
        
        assert result['forecast_high'] is None
        assert result['forecast_low'] is None
    
    def test_parse_taf_variable_winds(self):
        """Test parsing TAF with varying wind conditions."""
        taf = "TAF RJTT 061120Z 0612/0718 36005KT 9999 FEW030 TEMPO 0615/0618 36015G25KT TX18/0606Z TN10/0618Z"
        result = parse_taf(taf)
        
        assert result['forecast_high'] == 18.0
        assert result['forecast_low'] == 10.0
        # Should detect wind change
        assert len(result['wind_changes']) > 0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
