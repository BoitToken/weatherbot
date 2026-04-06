"""
Claude Analyzer — Confirm high-edge signals using Claude
"""
import os
import re
from dataclasses import dataclass
from typing import Literal, Optional
import logging

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logging.warning("anthropic package not installed")

from .mismatch_detector import Signal

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Claude's analysis of a trading signal"""
    confidence: Literal['HIGH', 'MEDIUM', 'LOW']
    recommendation: Literal['TRADE', 'ALERT_ONLY', 'SKIP']
    reasoning: str
    factors_considered: list[str]
    risk_warnings: list[str]
    raw_response: str


class ClaudeAnalyzer:
    """Use Claude to confirm high-edge trading signals"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude analyzer
        
        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("anthropic package required: pip install anthropic")
        
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        self.client = Anthropic(api_key=self.api_key)
    
    def build_prompt(self, signal: Signal, metar_raw: str = "", taf_summary: str = "") -> str:
        """
        Build analysis prompt for Claude
        
        Args:
            signal: Trading signal to analyze
            metar_raw: Raw METAR string (if available)
            taf_summary: TAF forecast summary (if available)
        """
        # Calculate projected high temperature
        projected_high = signal.current_temp_c + (signal.trend_per_hour * signal.hours_to_resolution)
        
        # Calculate confidence based on RMSE
        from .gaussian_model import get_rmse_for_lead_time
        rmse = get_rmse_for_lead_time(signal.hours_to_resolution)
        confidence = "HIGH" if rmse < 3.0 else "MEDIUM" if rmse < 5.0 else "LOW"
        
        prompt = f"""Aviation weather data for {signal.city} ({signal.icao}):

METAR: {metar_raw or 'Not available'}
Temperature: {signal.current_temp_c:.1f}°C
Trend: {signal.trend_per_hour:+.2f}°C/hr over recent hours
TAF forecast: {taf_summary or 'Not available'}

Projected temperature at resolution: {projected_high:.1f}°C (confidence: {confidence})
Threshold: {signal.threshold_c:.1f}°C ({signal.threshold_type})
Hours to resolution: {signal.hours_to_resolution:.1f}

Polymarket market: "{signal.market_title}"
Current {signal.recommended_side} price: ${signal.yes_price if signal.recommended_side == 'YES' else signal.no_price:.3f}
Market implied probability: {(signal.yes_price if signal.recommended_side == 'YES' else signal.no_price)*100:.1f}%

Our Gaussian model probability: {signal.our_probability*100:.1f}%
Calculated edge: {signal.edge*100:+.1f}%

Questions:
1. Does the aviation data support our probability estimate?
2. Are there any weather factors our model might miss? (fronts, storms, inversions, local effects)
3. What is your confidence level: HIGH / MEDIUM / LOW
4. What is your recommendation: TRADE / ALERT_ONLY / SKIP
5. If TRADE: confirm which side ({signal.recommended_side}) and why?
6. Any specific risk warnings?

Provide your analysis in a structured format."""
        
        return prompt
    
    def parse_response(self, response_text: str) -> AnalysisResult:
        """
        Parse Claude's response into structured result
        
        Extracts:
        - Confidence: HIGH / MEDIUM / LOW
        - Recommendation: TRADE / ALERT_ONLY / SKIP
        - Reasoning: main analysis text
        - Factors: bullet points of weather factors
        - Warnings: any risk warnings
        """
        text = response_text.strip()
        
        # Extract confidence
        confidence = 'MEDIUM'  # default
        if re.search(r'\bconfidence:?\s*HIGH\b', text, re.IGNORECASE):
            confidence = 'HIGH'
        elif re.search(r'\bconfidence:?\s*LOW\b', text, re.IGNORECASE):
            confidence = 'LOW'
        
        # Extract recommendation
        recommendation = 'ALERT_ONLY'  # default
        if re.search(r'\brecommendation:?\s*TRADE\b', text, re.IGNORECASE):
            recommendation = 'TRADE'
        elif re.search(r'\brecommendation:?\s*SKIP\b', text, re.IGNORECASE):
            recommendation = 'SKIP'
        
        # Extract factors (look for bullet points or numbered lists)
        factors = []
        factor_patterns = [
            r'[-•*]\s*([^\n]+)',
            r'\d+\.\s*([^\n]+)'
        ]
        for pattern in factor_patterns:
            matches = re.findall(pattern, text)
            factors.extend([m.strip() for m in matches if len(m.strip()) > 10])
        
        # Extract warnings (look for "risk", "warning", "caution")
        warnings = []
        warning_lines = re.findall(
            r'(?:risk|warning|caution|note)[:\s]+([^\n]+)',
            text,
            re.IGNORECASE
        )
        warnings.extend([w.strip() for w in warning_lines])
        
        # Full reasoning is the entire response
        reasoning = text
        
        return AnalysisResult(
            confidence=confidence,
            recommendation=recommendation,
            reasoning=reasoning,
            factors_considered=factors[:5],  # Top 5
            risk_warnings=warnings[:3],  # Top 3
            raw_response=response_text
        )
    
    async def analyze_signal(
        self,
        signal: Signal,
        metar_raw: str = "",
        taf_summary: str = "",
        use_sonnet: bool = False
    ) -> AnalysisResult:
        """
        Analyze a trading signal using Claude
        
        Args:
            signal: Trading signal to analyze
            metar_raw: Raw METAR string (if available)
            taf_summary: TAF forecast summary (if available)
            use_sonnet: Use Sonnet instead of Haiku (for high-edge signals >25%)
            
        Returns:
            AnalysisResult with Claude's assessment
        """
        # Choose model based on edge size
        model = "claude-sonnet-4-5" if use_sonnet or abs(signal.edge) > 0.25 else "claude-haiku-4-5"
        
        # Build prompt
        prompt = self.build_prompt(signal, metar_raw, taf_summary)
        
        logger.info(f"Analyzing with {model}: {signal.city} edge={signal.edge:+.1%}")
        
        try:
            # Call Claude API
            message = self.client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            response_text = message.content[0].text
            
            # Parse response
            result = self.parse_response(response_text)
            
            logger.info(
                f"Claude analysis: confidence={result.confidence}, "
                f"recommendation={result.recommendation}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            # Return fallback result
            return AnalysisResult(
                confidence='LOW',
                recommendation='SKIP',
                reasoning=f"Error calling Claude API: {e}",
                factors_considered=[],
                risk_warnings=["API error - manual review required"],
                raw_response=""
            )
    
    def should_analyze(self, signal: Signal, min_edge: float = 0.15) -> bool:
        """
        Determine if signal should be sent to Claude for analysis
        
        Args:
            signal: Trading signal
            min_edge: Minimum edge threshold (default 15%)
            
        Returns:
            True if signal should be analyzed
        """
        return abs(signal.edge) >= min_edge


def test_analyzer():
    """Test Claude analyzer with mock signal"""
    from .mismatch_detector import Signal
    from datetime import datetime
    
    # Create mock signal
    signal = Signal(
        market_id="test123",
        market_title="Will Tokyo's high temperature exceed 16°C on April 6?",
        icao="RJTT",
        city="Tokyo",
        yes_price=0.03,
        no_price=0.97,
        our_probability=0.85,
        edge=0.82,
        recommended_side='YES',
        current_temp_c=15.8,
        trend_per_hour=0.3,
        hours_to_resolution=6.0,
        threshold_c=16.0,
        threshold_type='high_above',
        flagged=True,
        created_at=datetime.utcnow(),
        metadata={}
    )
    
    print("\nClaude Analyzer Test\n")
    print("Signal:")
    print(f"  City: {signal.city} ({signal.icao})")
    print(f"  Market: {signal.market_title}")
    print(f"  Edge: {signal.edge:+.1%}")
    print(f"  Side: {signal.recommended_side}")
    print()
    
    # Test with API key from env
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  ANTHROPIC_API_KEY not set - skipping live test")
        print("\nMock prompt would be:")
        analyzer = ClaudeAnalyzer.__new__(ClaudeAnalyzer)
        analyzer.api_key = "mock"
        prompt = analyzer.build_prompt(signal, metar_raw="RJTT 060900Z 00000KT 9999 FEW030 16/12 Q1018")
        print(prompt)
        return
    
    try:
        import asyncio
        analyzer = ClaudeAnalyzer(api_key)
        
        # Run analysis
        result = asyncio.run(analyzer.analyze_signal(
            signal,
            metar_raw="RJTT 060900Z 00000KT 9999 FEW030 16/12 Q1018",
            taf_summary="No significant weather changes expected"
        ))
        
        print("Claude Analysis Result:")
        print(f"  Confidence: {result.confidence}")
        print(f"  Recommendation: {result.recommendation}")
        print(f"\nReasoning:\n{result.reasoning}")
        
        if result.factors_considered:
            print(f"\nFactors Considered:")
            for factor in result.factors_considered:
                print(f"  - {factor}")
        
        if result.risk_warnings:
            print(f"\nRisk Warnings:")
            for warning in result.risk_warnings:
                print(f"  ⚠️  {warning}")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_analyzer()
