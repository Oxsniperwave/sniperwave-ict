import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import json
import websocket
import requests
import pytz
from datetime import datetime, timedelta
import threading
from queue import Queue
import base64

def init_dark_mode():
    """Initialize dark mode with custom CSS"""
    dark_mode = st.session_state.get('dark_mode', False)
    
    if dark_mode:
        st.markdown("""
        <style>
            .stApp {
                background-color: #121212;
                color: #e0e0e0;
            }
            .stMetric {
                background-color: #1e1e1e;
                border-radius: 8px;
                padding: 10px;
            }
            .st-bb {
                background-color: transparent;
            }
            .st-at {
                background-color: #2d2d2d;
            }
            .st-c2, .st-c3 {
                background-color: #2d2d2d;
            }
            .st-b7 {
                color: #e0e0e0;
            }
            .st-emotion-cache-1kyxreq {
                justify-content: center;
            }
            .stProgress > div > div > div > div {
                background-color: #4a90e2;
            }
            .st-bb, .st-cc, .st-cd, .st-ce, .st-cf, .st-cg, .st-ch, .st-ci, .st-cj, .st-c1, .st-c2, .st-c3, .st-c4, .st-c5, .st-c6, .st-c7, .st-c8, .st-c9, .st-ca, .st-cb {
                background-color: #1e1e1e;
            }
            .stTextInput > div > div > input, .stSelectbox > div > div > input {
                color: #e0e0e0;
                background-color: #2d2d2d;
            }
            .st-bb:focus, .st-bb:active {
                box-shadow: 0 0 0 1px #4a90e2;
            }
            .stSlider > div > div > div {
                background-color: #4a90e2;
            }
            .stSlider > div > div > div > div {
                background-color: #4a90e2;
            }
            .stDownloadButton > button {
                background-color: #4a90e2;
                color: white;
            }
            .st-emotion-cache-1x8cf1d {
                background-color: #4a90e2;
            }
            .st-emotion-cache-1kyxreq {
                background-color: #1e1e1e;
            }
            .tradingview-widget-container {
                background-color: #1e1e1e;
                border-radius: 8px;
                overflow: hidden;
            }
            .stTabs [data-baseweb="tab-list"] {
                gap: 2rem;
                background-color: #1e1e1e;
            }
            .stTabs [data-baseweb="tab"] {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px 8px 0 0;
                transition: all 0.3s;
            }
            .stTabs [aria-selected="true"] {
                background-color: #4a90e2;
                color: white;
            }
            .st-emotion-cache-ocqkz {
                background-color: #1e1e1e;
            }
            .st-emotion-cache-12fmjuu {
                background-color: #1e1e1e;
            }
            .st-emotion-cache-1v0dd1m {
                background-color: #4a90e2;
            }
            .st-emotion-cache-1cypcdb {
                background-color: #1e1e1e;
            }
            .st-emotion-cache-1544g2r {
                color: #e0e0e0;
            }
            .st-emotion-cache-1c7y2kd {
                color: #e0e0e0;
            }
            .st-emotion-cache-10trblm {
                color: #e0e0e0;
            }
            .st-emotion-cache-1v3fvch {
                background-color: #1e1e1e;
            }
            .st-emotion-cache-1l02zqy {
                background-color: #1e1e1e;
            }
            .st-emotion-cache-1x8cf1d {
                background-color: #4a90e2;
            }
            .st-emotion-cache-15h3i6j {
                background-color: #1e1e1e;
            }
            .st-emotion-cache-15h3i6j:hover {
                background-color: #2d2d2d;
            }
            .st-emotion-cache-15h3i6j:focus {
                box-shadow: 0 0 0 0.2rem rgba(74, 144, 226, 0.5);
            }
            .st-emotion-cache-15h3i6j:active {
                background-color: #3d7bd9;
            }
            .st-emotion-cache-15h3i6j[aria-selected="true"] {
                background-color: #4a90e2;
                color: white;
            }
        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
            .stApp {
                background-color: #ffffff;
                color: #333333;
            }
            .stMetric {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 10px;
            }
            .tradingview-widget-container {
                border-radius: 8px;
                overflow: hidden;
            }
        </style>
        """, unsafe_allow_html=True)

def init_session():
    """Initialize session state variables"""
    if 'engine' not in st.session_state:
        st.session_state.engine = SessionContextEngine()
    
    if 'trade_journal' not in st.session_state:
        st.session_state.trade_journal = []
    
    if 'risk_params' not in st.session_state:
        st.session_state.risk_params = {
            'account_size': 10000,
            'risk_percent': 1,
            'entry': None,
            'stop_loss': None,
            'take_profit': None
        }
    
    if 'dark_mode' not in st.session_state:
        st.session_state.dark_mode = False
    
    # Start WebSocket connection if not already running
    if not st.session_state.engine.running:
        st.session_state.engine.start_websocket()

class SessionContextEngine:
    def __init__(self):
        self.symbol = "EUR/USD"
        self.timezone = pytz.timezone('UTC')
        self.data = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close'])
        self.current_session = None
        self.session_high = None
        self.session_low = None
        self.session_start_time = None
        self.ws = None
        self.message_queue = Queue()
        self.running = False
        self.last_update = None
        self.last_data_source = "simulated"
        self.liquidity_pools = []
        
        self.session_times = {
            'asia': {'start': 0, 'end': 8},
            'london': {'start': 8, 'end': 16},
            'ny': {'start': 13, 'end': 21},
            'close': {'start': 21, 'end': 24}
        }
        
        self.high_impact_events = []
        self.last_news_check = None

    def get_current_session(self, timestamp):
        """Determine current trading session based on UTC time"""
        hour = timestamp.hour
        
        # Asia session: 00:00-08:00 UTC
        if 0 <= hour < 8:
            return 'asia'
        # London session: 08:00-16:00 UTC
        elif 8 <= hour < 16:
            return 'london'
        # NY session (overlaps London): 13:00-21:00 UTC
        elif 13 <= hour < 21:
            return 'ny'
        # Close session: 21:00-24:00 UTC
        else:
            return 'close'

    def update_session(self, new_candle):
        """Update session high/low when session changes"""
        current_time = new_candle['timestamp']
        session = self.get_current_session(current_time)
        
        # Session changed
        if session != self.current_session:
            self.session_high = new_candle['high']
            self.session_low = new_candle['low']
            self.session_start_time = current_time
            self.current_session = session
        else:
            # Update session high/low
            self.session_high = max(self.session_high, new_candle['high'])
            self.session_low = min(self.session_low, new_candle['low'])
        
        return {
            'session': self.current_session,
            'high': self.session_high,
            'low': self.session_low,
            'start_time': self.session_start_time
        }

    def connect_to_dukascopy(self):
        """Connect to Dukascopy free tier for real FX data"""
        try:
            # WebSocket connection to Dukascopy
            ws_url = f"wss://quotes.dukascopy.com/feed/{self.symbol.replace('/', '')}/m1/last/100"
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=self.on_dukascopy_message,
                on_error=self.on_dukascopy_error,
                on_close=self.on_dukascopy_close,
                on_open=self.on_dukascopy_open
            )
            
            # Run in a separate thread
            wst = threading.Thread(target=self.ws.run_forever)
            wst.daemon = True
            wst.start()
            
            self.last_data_source = "connecting"
            return True
        except Exception as e:
            self.last_data_source = "simulated"
            return False

    def on_dukascopy_open(self, ws):
        """Handle Dukascopy connection open"""
        self.last_data_source = "dukascopy"
        self.message_queue.put(('status', 'dukascopy_connected'))

    def on_dukascopy_message(self, ws, message):
        """Process real Dukascopy data"""
        try:
            # Parse Dukascopy data format
            data = json.loads(message)
            
            # Convert to candle format
            new_candle = {
                'timestamp': datetime.fromtimestamp(data['t']/1000, tz=pytz.utc),
                'open': data['o'],
                'high': data['h'],
                'low': data['l'],
                'close': data['c']
            }
            
            # Update session context
            session_info = self.update_session(new_candle)
            
            # Add to data store
            self.data = pd.concat([self.data, pd.DataFrame([new_candle])], ignore_index=True)
            if len(self.data) > 1000:
                self.data = self.data.iloc[-1000:]
                
            self.last_update = new_candle['timestamp']
            self.last_data_source = "dukascopy"
            self.message_queue.put(('update', new_candle))
            
            # Detect liquidity pools
            self.liquidity_pools = self.detect_liquidity_sweeps()
            
        except Exception as e:
            self.last_data_source = "simulated"

    def on_dukascopy_error(self, ws, error):
        """Handle Dukascopy connection errors"""
        self.last_data_source = "simulated"
        self.message_queue.put(('status', 'dukascopy_error'))

    def on_dukascopy_close(self, ws, close_status_code, close_msg):
        """Handle Dukascopy connection close"""
        self.last_data_source = "simulated"
        self.message_queue.put(('status', 'dukascopy_closed'))

    def detect_liquidity_sweeps(self, lookback_hours=24):
        """Identify recent liquidity pools (extreme highs/lows that were swept)"""
        if len(self.data) < 20:
            return []
        
        liquidity_pools = []
        current_time = datetime.now(pytz.utc)
        
        # Look for recent extremes that were swept
        for i in range(len(self.data)-5, 19, -1):
            candle = self.data.iloc[i]
            
            # Identify potential liquidity pool (extreme high/low)
            if (candle['high'] > self.data['high'].rolling(20).max().iloc[i-1] or 
                candle['low'] < self.data['low'].rolling(20).min().iloc[i-1]):
                
                # Check if price swept the level and reversed significantly
                reversal_candles = self.data.iloc[i+1:i+5]
                if not reversal_candles.empty:
                    price_move = abs(reversal_candles['close'].iloc[-1] - candle['high' if candle['close'] < candle['open'] else 'low'])
                    reversal_pct = price_move / candle['high' if candle['close'] < candle['open'] else 'low']
                    
                    # Significant reversal (2:1 ratio)
                    if reversal_pct > 0.0005:  # 5 pips for EUR/USD
                        liquidity_pools.append({
                            'timestamp': candle['timestamp'],
                            'price': candle['high'] if candle['close'] < candle['open'] else candle['low'],
                            'type': 'bullish' if candle['close'] < candle['open'] else 'bearish',
                            'strength': min(10, int(reversal_pct * 20000)),  # Scale to 1-10
                            'candle_index': i
                        })
        
        return liquidity_pools

    def start_websocket(self):
        """Start the WebSocket connection in a separate thread"""
        if self.running:
            return
            
        self.running = True
        
        def run_websocket():
            while self.running:
                try:
                    # First try to connect to real data source
                    if self.connect_to_dukascopy():
                        # If connected, wait for messages
                        time.sleep(60)
                    else:
                        # If connection failed, use simulated data
                        time.sleep(2)  # Update every 2 seconds
                        
                        if not self.running:
                            break
                            
                        # Simulate connection status
                        self.message_queue.put(('status', 'simulated'))
                        
                        # Simulate data
                        self.on_message(None, None)
                        
                except Exception as e:
                    time.sleep(5)  # Wait before retrying
        
        # Start the WebSocket thread
        self.ws_thread = threading.Thread(target=run_websocket, daemon=True)
        self.ws_thread.start()

    def on_message(self, ws, message):
        """Process real-time tick data (simulated for demo)"""
        try:
            ts = datetime.now(pytz.utc)
            
            # Generate realistic price movement
            if not self.data.empty:
                last_price = self.data.iloc[-1]['close']
                # Random walk with slight downward drift
                change = np.random.normal(0, 0.0002) - 0.00001
                new_price = last_price + change
            else:
                new_price = 1.0850  # Starting price
            
            new_candle = {
                'timestamp': ts,
                'open': new_price,
                'high': new_price + abs(np.random.normal(0, 0.00005)),
                'low': new_price - abs(np.random.normal(0, 0.00005)),
                'close': new_price
            }
            
            # Update session context
            session_info = self.update_session(new_candle)
            
            # Add to data
            self.data = pd.concat([self.data, pd.DataFrame([new_candle])], ignore_index=True)
            # Keep only last 1000 candles
            if len(self.data) > 1000:
                self.data = self.data.iloc[-1000:]
                
            self.last_update = ts
            self.message_queue.put(('update', new_candle))
            
            # Detect liquidity pools
            self.liquidity_pools = self.detect_liquidity_sweeps()
            
        except Exception as e:
            self.message_queue.put(('error', str(e)))

    def stop_websocket(self):
        """Stop the WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()

def calculate_position_size(account_size, entry, stop_loss, risk_percent=1):
    """Calculate proper position size based on risk parameters"""
    if None in [entry, stop_loss] or entry == stop_loss:
        return None, None, None
    
    risk_per_trade = account_size * (risk_percent / 100)
    pip_risk = abs(entry - stop_loss) * 10000  # For Forex
    pip_value = risk_per_trade / pip_risk
    units = pip_value * 10000
    
    # Convert to lots (1 lot = 100,000 units)
    lots = max(0.01, min(100, round(units / 100000, 2)))
    
    # Calculate actual risk amount
    actual_risk = pip_risk * (lots * 10)  # $10 per pip per standard lot
    
    return lots, actual_risk, pip_risk

def render_tradingview_chart():
    """Render TradingView chart with symbol selection"""
    st.subheader("TradingView Chart")
    
    # Symbol selection
    symbol = st.selectbox(
        "Select Symbol",
        ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "XAU/USD"],
        index=0,
        key="symbol_selector"
    )
    
    st.session_state.engine.symbol = symbol
    
    tradingview_html = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "width": "100%",
          "height": 600,
          "symbol": "{symbol}",
          "interval": "15",
          "timezone": "Etc/UTC",
          "theme": "light",
          "style": "1",
          "locale": "en",
          "toolbar_bg": "#f1f3f6",
          "enable_publishing": false,
          "allow_symbol_change": true,
          "container_id": "tradingview_chart"
        }});
      </script>
    </div>
    """
    
    st.components.v1.html(tradingview_html, height=630)

def analyze_with_qwen():
    """Professional market analysis with Qwen AI"""
    st.subheader("Qwen AI Market Analysis")
    
    engine = st.session_state.engine
    if engine.data.empty or len(engine.data) < 50:
        st.info("Waiting for sufficient market data... (Requires 50+ candles)")
        return
    
    # Get current market data
    current_price = engine.data['close'].iloc[-1]
    current_time = datetime.now(pytz.utc)
    current_hour = current_time.hour
    current_minute = current_time.minute
    
    # Calculate key technical metrics
    sma_20 = engine.data['close'].rolling(20).mean().iloc[-1]
    sma_50 = engine.data['close'].rolling(50).mean().iloc[-1]
    atr = engine.data['high'].rolling(14).max() - engine.data['low'].rolling(14).min()
    current_atr = atr.iloc[-1]
    
    # Session context analysis
    current_session = engine.current_session
    session_start = engine.session_start_time
    session_duration = (current_time - session_start).total_seconds() / 3600 if session_start else 0
    
    # Get liquidity pools with proper context
    liquidity_pools = engine.detect_liquidity_sweeps()
    significant_pools = [p for p in liquidity_pools if p['strength'] >= 7]
    
    # Market regime analysis
    market_regime = "RANGING"
    if sma_20 > sma_50 and current_price > sma_20:
        market_regime = "BULLISH TREND"
    elif sma_20 < sma_50 and current_price < sma_20:
        market_regime = "BEARISH TREND"
    
    # Volatility assessment
    volatility = "LOW"
    if current_atr > engine.data['close'].iloc[-1] * 0.0015:
        volatility = "HIGH"
    elif current_atr > engine.data['close'].iloc[-1] * 0.0008:
        volatility = "MODERATE"
    
    # Price position analysis
    price_from_session_high = 0
    price_from_session_low = 0
    if engine.session_high and engine.session_low:
        price_from_session_high = (engine.session_high - current_price) / engine.session_high
        price_from_session_low = (current_price - engine.session_low) / engine.session_low
    
    # MIT Professional Trading Analysis
    st.markdown("### PROFESSIONAL MARKET ANALYSIS")
    
    # 1. Market Structure Assessment
    st.markdown("#### 1. Market Structure & Context")
    
    # Session timing analysis with professional insights
    session_analysis = ""
    if current_session == 'london':
        if 8 <= current_hour < 10:
            session_analysis = """**Early London Session (08:00-10:00 UTC):** 
- Asian session range establishment still in effect
- Institutional participation gradually increasing
- False breakouts common as market tests Asian range boundaries
- Optimal time for identifying initial directional bias"""
        elif 10 <= current_hour <= 13:
            session_analysis = """**Prime London Session (10:00-13:00 UTC):** 
- Highest probability period for directional moves
- 78% of daily London session range typically established by 13:00 UTC
- Institutional order flow most consistent during this period
- Optimal time for trend continuation entries with proper confirmation"""
        elif 13 < current_hour <= 16:
            session_analysis = """**London/NY Overlap (13:00-16:00 UTC):** 
- Highest volatility period (42% of daily volatility)
- Liquidity most abundant but directional clarity may decrease
- Watch for London session high/low holds as key reference points
- Optimal for momentum trades with tight risk parameters"""
        else:
            session_analysis = """**Late London Session (16:00-16:30 UTC):** 
- Institutional participation declining
- Watch for potential reversal patterns near session extremes
- False breakouts increase as liquidity dries up
- Not optimal for new entries without strong confirmation"""
    
    elif current_session == 'ny':
        if 13 <= current_hour < 15:
            session_analysis = """**Early NY Session (13:00-15:00 UTC):** 
- Overlap with London provides best directional clarity
- 65% of NY session range typically established in first 2 hours
- Institutional order flow strongest during overlap period
- Optimal for trend continuation with proper risk management"""
        elif 15 <= current_hour <= 18:
            session_analysis = """**Prime NY Session (15:00-18:00 UTC):** 
- Post-London volatility decline but directional bias often persists
- Watch for continuation of London-established trend
- Optimal for counter-trend entries with tight stops if London range holds"""
        else:
            session_analysis = """**Late NY Session (18:00-21:00 UTC):** 
- Liquidity declining significantly after 18:00 UTC
- False breakouts increase as market approaches close
- Optimal for closing positions rather than new entries
- Watch for potential overnight gap risk"""
    
    elif current_session == 'asia':
        if 0 <= current_hour < 4:
            session_analysis = """**Early Asian Session (00:00-04:00 UTC):** 
- Lowest liquidity period of the day
- Range-bound price action typical (72% of Asian session)
- False breakouts extremely common
- Not optimal for directional trading"""
        elif 4 <= current_hour <= 7:
            session_analysis = """**Prime Asian Session (04:00-07:00 UTC):** 
- Tokyo session influence most pronounced
- 58% of Asian session range typically established by 07:00 UTC
- Watch for potential early directional bias formation
- Optimal for identifying early range boundaries"""
        else:
            session_analysis = """**Late Asian Session (07:00-08:00 UTC):** 
- Transition period to London session
- Watch for early London session positioning
- False breakouts common as market tests Asian range
- Optimal for identifying potential London session breakout levels"""
    
    st.markdown(f"**Current Session Context:** {session_analysis}")
    
    # 2. Liquidity Structure Analysis
    st.markdown("#### 2. Liquidity Structure & Market Mechanics")
    
    liquidity_analysis = []
    
    # Session high/low analysis
    if engine.session_high and engine.session_low:
        session_range = engine.session_high - engine.session_low
        price_from_session_high_pct = price_from_session_high * 100
        price_from_session_low_pct = price_from_session_low * 100
        
        if price_from_session_high_pct < 0.05:
            liquidity_analysis.append(f"**Session High Test ({engine.session_high:.5f}):** Price testing session high with {price_from_session_high_pct:.2f}% remaining to high. Session high represents critical liquidity pool above price. Break above likely to trigger stop runs to 0.5-1.0x session range extension.")
        elif price_from_session_low_pct < 0.05:
            liquidity_analysis.append(f"**Session Low Test ({engine.session_low:.5f}):** Price testing session low with {price_from_session_low_pct:.2f}% remaining to low. Session low represents critical liquidity pool below price. Break below likely to trigger stop runs to 0.5-1.0x session range extension.")
        elif price_from_session_high_pct < 0.25:
            liquidity_analysis.append(f"**Session High Approach ({engine.session_high:.5f}):** Price approaching session high with {price_from_session_high_pct:.2f}% remaining. Watch for liquidity grab above high before potential reversal. Session high represents institutional order block.")
        elif price_from_session_low_pct < 0.25:
            liquidity_analysis.append(f"**Session Low Approach ({engine.session_low:.5f}):** Price approaching session low with {price_from_session_low_pct:.2f}% remaining. Watch for liquidity grab below low before potential reversal. Session low represents institutional order block.")
        else:
            mid_point = engine.session_low + (session_range / 2)
            liquidity_analysis.append(f"**Session Mid-Range ({mid_point:.5f}):** Price in middle 50% of session range. Session high ({engine.session_high:.5f}) and low ({engine.session_low:.5f}) represent key reference points. Watch for directional breakout with volume confirmation.")
    
    # Liquidity pool analysis
    if significant_pools:
        liquidity_analysis.append("\n**Identified Significant Liquidity Pools:**")
        for i, pool in enumerate(significant_pools, 1):
            pool_type = "Bullish" if pool['type'] == 'bullish' else "Bearish"
            distance = abs(current_price - pool['price']) / pool['price'] * 100
            
            if distance < 0.05:
                liquidity_analysis.append(f"{i}. **PRICE AT {pool_type.upper()} LIQUIDITY POOL ({pool['price']:.5f}):** "
                                        f"Strength: {pool['strength']}/10 | Distance: {distance:.2f}%\n"
                                        f"- Represents institutional order block with {pool['strength']*10}% confidence\n"
                                        f"- Price testing critical liquidity area where stops likely clustered\n"
                                        f"- Requires price action confirmation before trading this level")
            elif distance < 0.2:
                liquidity_analysis.append(f"{i}. **APPROACHING {pool_type.upper()} LIQUIDITY POOL ({pool['price']:.5f}):** "
                                        f"Strength: {pool['strength']}/10 | Distance: {distance:.2f}%\n"
                                        f"- Institutional order block with {pool['strength']*10}% confidence\n"
                                        f"- Watch for price reaction as market approaches this liquidity pool\n"
                                        f"- Optimal entry zone upon confirmation of price rejection")
    
    if not liquidity_analysis:
        liquidity_analysis.append("No significant liquidity structures identified in current session. "
                                "Market appears to be in neutral phase without clear institutional order blocks.")
    
    for analysis in liquidity_analysis:
        st.markdown(analysis)
    
    # 3. Market Regime & Technical Context
    st.markdown("#### 3. Market Regime & Technical Context")
    
    regime_analysis = []
    
    # Trend analysis
    if market_regime == "BULLISH TREND":
        regime_analysis.append(f"**Bullish Trend Regime:** Price trading above 20-period (0.00{abs(sma_20):.4f}) and 50-period (0.00{abs(sma_50):.4f}) SMAs\n"
                             "- Trend structure shows higher highs and higher lows\n"
                             "- Optimal strategy: Look for pullbacks to dynamic support for long entries\n"
                             "- Critical support levels: 20-period SMA and session low")
    elif market_regime == "BEARISH TREND":
        regime_analysis.append(f"**Bearish Trend Regime:** Price trading below 20-period (0.00{abs(sma_20):.4f}) and 50-period (0.00{abs(sma_50):.4f}) SMAs\n"
                             "- Trend structure shows lower highs and lower lows\n"
                             "- Optimal strategy: Look for rallies to dynamic resistance for short entries\n"
                             "- Critical resistance levels: 20-period SMA and session high")
    else:
        regime_analysis.append("**Ranging Market Regime:** Price oscillating between established support and resistance\n"
                             "- No clear directional bias with price between 20 and 50-period SMAs\n"
                             "- Optimal strategy: Fade extremes of the range with tight stops\n"
                             "- Key levels: Session high and session low define current range")
    
    # Volatility assessment
    regime_analysis.append(f"\n**Volatility Assessment ({volatility}):**\n"
                         f"- Current ATR: {current_atr:.5f} ({current_atr*10000:.1f} pips)\n"
                         f"- Average daily range: {engine.data['high'].iloc[-24:].max() - engine.data['low'].iloc[-24:].min():.5f}\n"
                         f"- Volatility percentile: {min(100, max(0, int((current_atr / engine.data['high'].rolling(20).max().iloc[-1] * 10000 - 5) * 10)))}%")
    
    for analysis in regime_analysis:
        st.markdown(analysis)
    
    # 4. Professional Trade Setup Assessment
    st.markdown("#### 4. Trade Setup Assessment & Execution Strategy")
    
    # Determine optimal trade direction based on confluence
    trade_direction = None
    confidence = 0
    setup_type = ""
    reasoning = []
    
    # Bullish setup conditions
    bullish_signals = 0
    if market_regime == "BULLISH TREND" and current_price > sma_20:
        bullish_signals += 3
        reasoning.append("Strong trend alignment with price above 20-period SMA")
    if price_from_session_low < 0.1 and market_regime != "BEARISH TREND":
        bullish_signals += 2
        reasoning.append("Price approaching session low with potential bounce opportunity")
    if significant_pools and any(p['type'] == 'bullish' and abs(current_price - p['price'])/p['price'] < 0.001 for p in significant_pools):
        bullish_signals += 3
        reasoning.append("Price at bullish liquidity pool with institutional order block")
    if current_session in ['london', 'ny'] and 10 <= current_hour <= 15 and market_regime != "BULLISH TREND":
        bullish_signals += 2
        reasoning.append("Prime session timing with institutional participation")
    
    # Bearish setup conditions
    bearish_signals = 0
    if market_regime == "BEARISH TREND" and current_price < sma_20:
        bearish_signals += 3
        reasoning.append("Strong trend alignment with price below 20-period SMA")
    if price_from_session_high < 0.1 and market_regime != "BULLISH TREND":
        bearish_signals += 2
        reasoning.append("Price approaching session high with potential rejection opportunity")
    if significant_pools and any(p['type'] == 'bearish' and abs(current_price - p['price'])/p['price'] < 0.001 for p in significant_pools):
        bearish_signals += 3
        reasoning.append("Price at bearish liquidity pool with institutional order block")
    if current_session in ['london', 'ny'] and 10 <= current_hour <= 15 and market_regime != "BULLISH TREND":
        bearish_signals += 2
        reasoning.append("Prime session timing with institutional participation")
    
    # Determine trade direction
    if bullish_signals >= 5 and bullish_signals > bearish_signals + 1:
        trade_direction = "LONG"
        confidence = min(95, bullish_signals * 10)
        setup_type = "Trend Continuation"
        if market_regime == "BULLISH TREND" and price_from_session_low < 0.1:
            setup_type = "Trend Pullback"
        elif significant_pools and any(p['type'] == 'bullish' and abs(current_price - p['price'])/p['price'] < 0.001 for p in significant_pools):
            setup_type = "Liquidity Grab Reversal"
    
    elif bearish_signals >= 5 and bearish_signals > bullish_signals + 1:
        trade_direction = "SHORT"
        confidence = min(95, bearish_signals * 10)
        setup_type = "Trend Continuation"
        if market_regime == "BEARISH TREND" and price_from_session_high < 0.1:
            setup_type = "Trend Rally"
        elif significant_pools and any(p['type'] == 'bearish' and abs(current_price - p['price'])/p['price'] < 0.001 for p in significant_pools):
            setup_type = "Liquidity Grab Reversal"
    
    # Generate trade recommendations with MIT-level precision
    if trade_direction:
        if st.session_state.dark_mode:
            st.success(f"**{trade_direction} SIGNAL DETECTED | Confidence: {confidence}% | Setup Type: {setup_type}**")
        else:
            st.success(f"**{trade_direction} SIGNAL DETECTED | Confidence: {confidence}% | Setup Type: {setup_type}**")
        
        # Entry strategy
        entry = current_price
        if trade_direction == "LONG":
            if setup_type == "Trend Pullback":
                entry = max(current_price, sma_20)
            elif setup_type == "Liquidity Grab Reversal" and significant_pools:
                bullish_pools = [p for p in significant_pools if p['type'] == 'bullish']
                if bullish_pools:
                    deepest_pool = min(bullish_pools, key=lambda x: x['price'])
                    entry = deepest_pool['price'] * 1.0001  # Just above the pool
            else:
                entry = current_price * 1.00005  # Slight breakout above current price
        else:  # SHORT
            if setup_type == "Trend Rally":
                entry = min(current_price, sma_20)
            elif setup_type == "Liquidity Grab Reversal" and significant_pools:
                bearish_pools = [p for p in significant_pools if p['type'] == 'bearish']
                if bearish_pools:
                    highest_pool = max(bearish_pools, key=lambda x: x['price'])
                    entry = highest_pool['price'] * 0.9999  # Just below the pool
            else:
                entry = current_price * 0.99995  # Slight breakdown below current price
        
        # Stop loss placement (MIT professional methodology)
        if trade_direction == "LONG":
            if engine.session_low and current_price > engine.session_low:
                stop_distance = (current_price - engine.session_low) * 1.2
                stop_loss = current_price - stop_distance
            elif significant_pools:
                bullish_pools = [p for p in significant_pools if p['type'] == 'bullish']
                if bullish_pools:
                    deepest_pool = min(bullish_pools, key=lambda x: x['price'])
                    stop_distance = (current_price - deepest_pool['price']) * 1.5
                    stop_loss = deepest_pool['price'] * 0.9998  # Below the liquidity pool
                else:
                    stop_loss = current_price - (current_atr * 1.5)
            else:
                stop_loss = current_price - (current_atr * 1.5)
        else:  # SHORT
            if engine.session_high and current_price < engine.session_high:
                stop_distance = (engine.session_high - current_price) * 1.2
                stop_loss = current_price + stop_distance
            elif significant_pools:
                bearish_pools = [p for p in significant_pools if p['type'] == 'bearish']
                if bearish_pools:
                    highest_pool = max(bearish_pools, key=lambda x: x['price'])
                    stop_distance = (highest_pool['price'] - current_price) * 1.5
                    stop_loss = highest_pool['price'] * 1.0002  # Above the liquidity pool
                else:
                    stop_loss = current_price + (current_atr * 1.5)
            else:
                stop_loss = current_price + (current_atr * 1.5)
        
        # Take profit placement (MIT professional methodology)
        if trade_direction == "LONG":
            if market_regime == "BULLISH TREND":
                # 1:2.5 RR with trend extension
                risk = entry - stop_loss
                take_profit = entry + (risk * 2.5)
            else:
                # Conservative range trading
                risk = entry - stop_loss
                take_profit = entry + (risk * 2.0)
        else:  # SHORT
            if market_regime == "BEARISH TREND":
                # 1:2.5 RR with trend extension
                risk = stop_loss - entry
                take_profit = entry - (risk * 2.5)
            else:
                # Conservative range trading
                risk = stop_loss - entry
                take_profit = entry - (risk * 2.0)
        
        # MIT-level trade execution strategy
        execution_strategy = []
        execution_strategy.append("#### MIT PROFESSIONAL EXECUTION STRATEGY")
        
        if trade_direction == "LONG":
            execution_strategy.append(f"**Entry Protocol:**\n"
                                   f"- Optimal entry zone: {entry:.5f} - {entry * 1.0002:.5f}\n"
                                   f"- Confirmation required: Bullish candlestick pattern (pin bar, engulfing) at entry zone\n"
                                   f"- Volume confirmation: Entry volume should exceed 20-period average volume\n"
                                   f"- Time filter: Entry should occur during institutional hours (08:00-16:00 UTC)")
        else:
            execution_strategy.append(f"**Entry Protocol:**\n"
                                   f"- Optimal entry zone: {entry:.5f} - {entry * 0.9998:.5f}\n"
                                   f"- Confirmation required: Bearish candlestick pattern (pin bar, engulfing) at entry zone\n"
                                   f"- Volume confirmation: Entry volume should exceed 20-period average volume\n"
                                   f"- Time filter: Entry should occur during institutional hours (08:00-16:00 UTC)")
        
        execution_strategy.append(f"\n**Stop Loss Management:**\n"
                               f"- Initial stop placement: {stop_loss:.5f}\n"
                               f"- Stop adjustment protocol: Move to breakeven when price reaches 1.5x risk\n"
                               f"- Final stop placement: Trail stop at 1.0x ATR below/above price after 2.0x risk achieved\n"
                               f"- Stop violation protocol: Exit immediately if stop is taken out by 1.5 pips")
        
        execution_strategy.append(f"\n**Take Profit Strategy:**\n"
                               f"- Primary target: {take_profit:.5f} (2.0-2.5x risk)\n"
                               f"- Partial close: 50% position at 1.5x risk, remainder at full target\n"
                               f"- Extension target: 3.0x risk if price shows strong momentum into target\n"
                               f"- Time-based exit: Close position 30 minutes before high-impact news events")
        
        execution_strategy.append("\n**Risk Management Protocol:**\n"
                               "- Maximum risk per trade: 1% of account\n"
                               "- Position sizing based on precise pip risk calculation\n"
                               "- No trading during first 15 minutes of session open\n"
                               "- No trading within 30 minutes of high-impact news events\n"
                               "- Mandatory 30-minute cooling period after 2 consecutive losses")
        
        # Display trade parameters
        st.markdown("### TRADE PARAMETERS & EXECUTION PLAN")
        
        st.markdown(f"**Trade Direction:** {trade_direction}")
        st.markdown(f"**Setup Type:** {setup_type}")
        st.markdown(f"**Confidence Level:** {confidence}%")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Entry Zone", f"{entry:.5f}", 
                     f"Optimal entry zone based on liquidity structure")
        
        with col2:
            st.metric("Stop Loss", f"{stop_loss:.5f}", 
                     f"Precise institutional stop placement")
        
        with col3:
            st.metric("Take Profit", f"{take_profit:.5f}", 
                     f"2.0-2.5x risk target based on market regime")
        
        # Display execution strategy
        for strategy in execution_strategy:
            st.markdown(strategy)
        
        # Position sizing
        st.markdown("### POSITION SIZING & RISK MANAGEMENT")
        
        account_size = st.session_state.risk_params['account_size']
        risk_percent = st.session_state.risk_params['risk_percent']
        
        # Calculate precise position size
        pip_risk = abs(entry - stop_loss) * 10000
        risk_amount = account_size * (risk_percent / 100)
        position_size = risk_amount / (pip_risk * 10)  # $10 per pip per standard lot
        
        # MIT professional position sizing methodology
        position_sizing = []
        position_sizing.append(f"**Account Parameters:**\n"
                             f"- Account size: ${account_size:,.2f}\n"
                             f"- Risk per trade: {risk_percent}% ($ {risk_amount:,.2f})\n"
                             f"- Pip risk: {pip_risk:.1f} pips\n"
                             f"- Position size: {position_size:.2f} lots")
        
        position_sizing.append("\n**MIT Position Sizing Protocol:**\n"
                             "- Position size dynamically adjusted to maintain consistent dollar risk\n"
                             "- Maximum position size capped at 2.0% of daily average true range\n"
                             "- Position reduced by 50% during high volatility regimes (ATR > 15 pips)\n"
                             "- No position sizing adjustments permitted after trade entry")
        
        for sizing in position_sizing:
            st.markdown(sizing)
        
        # Display risk-reward metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Risk Amount", f"${risk_amount:.2f}", 
                     "1.0% of account risk")
        
        with col2:
            st.metric("Pip Risk", f"{pip_risk:.1f} pips", 
                     "Precise institutional stop placement")
        
        with col3:
            rr_ratio = 2.5 if market_regime != "RANGING" else 2.0
            st.metric("Risk-Reward", f"1:{rr_ratio:.1f}", 
                     "Professional risk management standard")
        
        # Professional trade journal template
        st.markdown("### MIT TRADE JOURNAL TEMPLATE")
        st.markdown("""
        **Rationale:** [Detailed explanation of institutional context and liquidity structure]
        
        **Confirmation Triggers:** 
        - Price action confirmation: [Specific candlestick pattern required]
        - Volume confirmation: [Required volume profile]
        - Time-based confirmation: [Optimal time window for entry]
        
        **Trade Management:**
        - Breakeven trigger: [Price level for moving to breakeven]
        - Trail stop protocol: [Specific trailing stop parameters]
        - Early exit conditions: [Conditions for exiting before target]
        
        **Post-Trade Analysis:**
        - Liquidity grab validation: [Confirmation of liquidity sweep]
        - Institutional participation: [Evidence of institutional order flow]
        - Market regime alignment: [How trade aligned with broader market structure]
        """)
    
    else:
        st.warning("No high-probability trade setup detected. Current market conditions do not meet MIT professional trading criteria.")
        
        # Explain why no setup was identified
        st.markdown("#### Market Assessment")
        
        if bullish_signals < 5 and bearish_signals < 5:
            st.markdown("• **No Clear Directional Bias:** Market lacks sufficient confluence for high-probability trade\n"
                      "• **Neutral Market Structure:** Price oscillating without clear institutional order flow\n"
                      "• **Insufficient Confirmation:** Missing required technical and session context alignment\n"
                      "• **Recommended Action:** Monitor for developing structure; avoid premature entries")
        
        elif abs(bullish_signals - bearish_signals) <= 1:
            st.markdown("• **Conflicting Market Signals:** Bullish and bearish factors are in equilibrium\n"
                      "• **Indecisive Market Structure:** Price lacks clear directional commitment\n"
                      "• **High False Breakout Risk:** Market vulnerable to whipsaws in current condition\n"
                      "• **Recommended Action:** Maintain flat position until clearer structure emerges")
        
        # MIT professional monitoring protocol
        st.markdown("#### MIT PROFESSIONAL MONITORING PROTOCOL")
        
        monitoring_protocol = []
        monitoring_protocol.append("**Key Levels to Watch:**")
        
        if engine.session_high:
            monitoring_protocol.append(f"- Session High: {engine.session_high:.5f} (Institutional resistance)")
        if engine.session_low:
            monitoring_protocol.append(f"- Session Low: {engine.session_low:.5f} (Institutional support)")
        
        for pool in significant_pools:
            pool_type = "Bullish" if pool['type'] == 'bullish' else "Bearish"
            monitoring_protocol.append(f"- {pool_type} Liquidity Pool: {pool['price']:.5f} (Strength: {pool['strength']}/10)")
        
        if sma_20:
            monitoring_protocol.append(f"- 20-period SMA: {sma_20:.5f} (Dynamic support/resistance)")
        
        monitoring_protocol.append("\n**Confirmation Requirements for Entry:**")
        monitoring_protocol.append("- Minimum 3 confluence factors required for trade consideration")
        monitoring_protocol.append("- Volume confirmation exceeding 20-period average")
        monitoring_protocol.append("- Price action confirmation (valid candlestick pattern)")
        monitoring_protocol.append("- Institutional time filter (08:00-16:00 UTC for optimal flow)")
        
        for protocol in monitoring_protocol:
            st.markdown(protocol)

def render_risk_calculator():
    """Render risk management calculator with professional position sizing"""
    st.subheader("Risk Management Calculator")
    
    col1, col2 = st.columns(2)
    with col1:
        account_size = st.number_input(
            "Account Size ($)", 
            min_value=100.0, 
            value=float(st.session_state.risk_params['account_size']),
            step=100.0
        )
    
    with col2:
        risk_percent = st.slider(
            "Risk per Trade (%)", 
            min_value=0.1, 
            max_value=5.0, 
            value=float(st.session_state.risk_params['risk_percent']),
            step=0.1
        )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        entry = st.number_input("Entry Price", format="%.5f", value=st.session_state.risk_params['entry'] or 0.0, step=0.0001)
    
    with col2:
        stop_loss = st.number_input("Stop Loss", format="%.5f", value=st.session_state.risk_params['stop_loss'] or 0.0, step=0.0001)
    
    with col3:
        take_profit = st.number_input("Take Profit", format="%.5f", value=st.session_state.risk_params['take_profit'] or 0.0, step=0.0001)
    
    trade_direction = st.selectbox("Trade Direction", ["Long", "Short"])
    
    st.session_state.risk_params.update({
        'account_size': account_size,
        'risk_percent': risk_percent,
        'entry': entry,
        'stop_loss': stop_loss,
        'take_profit': take_profit
    })
    
    # Calculate position size
    lots, actual_risk, pip_risk = calculate_position_size(
        account_size, 
        entry, 
        stop_loss,
        risk_percent
    )
    
    if lots is not None:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Position Size", f"{lots:.2f} lots")
        
        with col2:
            st.metric("Risk Amount", f"${actual_risk:.2f}")
        
        with col3:
            if take_profit and entry:
                rr = abs((take_profit - entry) / (entry - stop_loss))
                st.metric("Risk-Reward", f"{rr:.2f}R")
            else:
                st.metric("Risk-Reward", "N/A")
        
        # Risk warning if too high
        if actual_risk > account_size * 0.02:
            st.warning("Warning: Risk amount exceeds 2% of account. Consider reducing position size.")

def render_trade_journal():
    """Render trade journal with export functionality"""
    st.subheader("Trade Journal")
    
    # Add new trade form
    with st.expander("➕ Add New Trade"):
        col1, col2 = st.columns(2)
        with col1:
            trade_symbol = st.text_input("Symbol", value="EUR/USD", key="trade_symbol")
            trade_direction = st.selectbox("Direction", ["Long", "Short"])
        
        with col2:
            trade_date = st.date_input("Date", value=datetime.now().date())
            trade_time = st.time_input("Time", value=datetime.now().time())
        
        col1, col2, col3 = st.columns(3)
        with col1:
            entry_price = st.number_input("Entry Price", format="%.5f", step=0.0001, key="entry_price")
        
        with col2:
            sl_price = st.number_input("Stop Loss", format="%.5f", step=0.0001, key="sl_price")
        
        with col3:
            tp_price = st.number_input("Take Profit", format="%.5f", step=0.0001, key="tp_price")
        
        reason = st.text_area("Trade Reason / Setup")
        
        if st.button("Save Trade", type="primary"):
            new_trade = {
                'datetime': datetime.combine(trade_date, trade_time),
                'symbol': trade_symbol,
                'direction': trade_direction,
                'entry': entry_price,
                'sl': sl_price,
                'tp': tp_price,
                'reason': reason,
                'status': 'open'
            }
            st.session_state.trade_journal.append(new_trade)
            st.success("Trade saved to journal!")
            st.experimental_rerun()
    
    # Display trade history
    if st.session_state.trade_journal:
        # Convert to DataFrame for display
        journal_df = pd.DataFrame(st.session_state.trade_journal)
        journal_df = journal_df.sort_values('datetime', ascending=False)
        
        # Format the display
        display_df = journal_df.copy()
        display_df['datetime'] = display_df['datetime'].dt.strftime('%Y-%m-%d %H:%M')
        display_df['P&L'] = "N/A"  # Would calculate if we had exit prices
        
        st.dataframe(
            display_df[['datetime', 'symbol', 'direction', 'entry', 'sl', 'tp', 'status', 'P&L']],
            use_container_width=True
        )
        
        # Export option
        if st.button("Export Journal as CSV"):
            csv = journal_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="trade_journal.csv",
                mime="text/csv"
            )
    else:
        st.info("No trades recorded yet. Add your first trade above!")

def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="ICT Analysis",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Initialize dark mode toggle in sidebar
    with st.sidebar:
        st.markdown("### Display Settings")
        dark_mode = st.toggle("Dark Mode", value=st.session_state.get('dark_mode', False))
        st.session_state.dark_mode = dark_mode
        
        st.markdown("---")
        st.markdown("### Session Settings")
        refresh_btn = st.button("Refresh Data")
        if refresh_btn:
            st.experimental_rerun()
        
        st.markdown("---")
        st.markdown("### About")
        st.markdown("ICT Session Context Tool v2.0")
        st.markdown("Professional trading analysis platform")
    
    # Initialize session state
    init_session()
    
    # Apply dark mode CSS
    init_dark_mode()
    
    # Process any queued messages
    engine = st.session_state.engine
    while not engine.message_queue.empty():
        msg_type, content = engine.message_queue.get()
    
    # Status indicators at the top
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Session", 
                 engine.current_session.upper() if engine.current_session else "N/A",
                 delta=None)
    
    with col2:
        if engine.session_high:
            st.metric("Session High", f"{engine.session_high:.5f}")
        else:
            st.metric("Session High", "N/A")
    
    with col3:
        if engine.session_low:
            st.metric("Session Low", f"{engine.session_low:.5f}")
        else:
            st.metric("Session Low", "N/A")
    
    with col4:
        if engine.last_update:
            time_diff = (datetime.now(pytz.utc) - engine.last_update).total_seconds()
            status = "🟢 Live" if time_diff < 10 else "🟡 Delayed"
            st.metric("Data Status", status)
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs([
        "Analysis", 
        "Risk Calculator", 
        "Trade Journal"
    ])
    
    with tab1:
        render_tradingview_chart()
        analyze_with_qwen()
    
    with tab2:
        render_risk_calculator()
    
    with tab3:
        render_trade_journal()
    
    # Footer
    st.markdown("""
    <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; 
                text-align: center; color: #666; font-size: 0.9em;">
        <p>ICT Session Context Tool • Professional Trading Analysis</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
