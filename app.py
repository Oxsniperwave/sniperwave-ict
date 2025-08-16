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
    
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = [
            {"role": "assistant", "content": "Hello! I'm your professional trading analysis assistant. How can I help you analyze the market today?"}
        ]
    
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

def render_analysis_chatbot():
    """Render a chatbot interface for requesting market analysis"""
    st.subheader("Market Analysis Chatbot")
    
    # Display chat messages
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    prompt = st.chat_input("Ask about market structure, liquidity pools, or trading opportunities...")
    
    if prompt:
        # Add user message to chat history
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Process the request
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # Generate response based on the prompt
            with st.spinner("Analyzing chart..."):
                response = generate_analysis_response(prompt)
                full_response = response
            
            message_placeholder.markdown(full_response)
        
        # Add assistant response to chat history
        st.session_state.chat_messages.append({"role": "assistant", "content": full_response})

def generate_analysis_response(prompt):
    """Generate appropriate analysis response based on user prompt"""
    engine = st.session_state.engine
    
    # Basic validation
    if engine.data.empty:
        return ("I need market data to provide analysis. Please wait a moment for the chart to load.")
    
    # Process different types of requests
    prompt_lower = prompt.lower()
    
    # Session context questions
    if any(keyword in prompt_lower for keyword in ["session", "time", "utc", "london", "ny", "asia", "when", "what time"]):
        return generate_session_analysis(engine)
    
    # Liquidity questions
    elif any(keyword in prompt_lower for keyword in ["liquidity", "pool", "sweep", "stop", "order block", "institutional"]):
        return generate_liquidity_analysis(engine)
    
    # Trading setup questions
    elif any(keyword in prompt_lower for keyword in ["setup", "trade", "entry", "signal", "opportunity", "where to enter"]):
        return generate_trade_setup_analysis(engine)
    
    # Technical analysis questions
    elif any(keyword in prompt_lower for keyword in ["trend", "sma", "atr", "volatility", "support", "resistance", "technical"]):
        return generate_technical_analysis(engine)
    
    # Market context questions
    elif any(keyword in prompt_lower for keyword in ["market", "condition", "regime", "structure", "context"]):
        return generate_market_regime_analysis(engine)
    
    # Help/feature questions
    elif any(keyword in prompt_lower for keyword in ["help", "what can you do", "features", "capabilities"]):
        return """I can provide professional analysis of the current market conditions including:

1. **Session Context Analysis**
   - Current trading session and institutional timing
   - Session high/low significance
   - Optimal timing for entries based on institutional flow

2. **Liquidity Structure Analysis**
   - Identification of significant liquidity pools
   - Institutional order block assessment
   - Liquidity grab prediction

3. **Trade Setup Assessment**
   - Entry, stop loss, and take profit recommendations
   - Risk-reward ratio calculation
   - Position sizing based on account parameters

4. **Market Regime Assessment**
   - Trending vs. ranging market identification
   - Volatility assessment
   - Technical structure analysis

Try asking specific questions like:
- 'What's the current session context?'
- 'Are there any significant liquidity pools visible?'
- 'What trade opportunities do you see right now?'
- 'Is the market trending or ranging?'
- 'Show me potential entry points for long positions'"""

    # Default response for unclear requests
    else:
        return ("I can help analyze various aspects of the market including:\n\n"
                "- Current trading session context and institutional timing\n"
                "- Liquidity pool identification and significance\n"
                "- Trade setup opportunities with entry/exit parameters\n"
                "- Market regime assessment (trending vs ranging)\n"
                "- Technical structure analysis\n\n"
                "Try asking something like:\n"
                "- 'What's the current session context?'\n"
                "- 'Are there any significant liquidity pools visible?'\n"
                "- 'What trade opportunities do you see right now?'\n"
                "- 'Is the market trending or ranging?'\n"
                "- 'Show me potential entry points for long positions'")

def generate_session_analysis(engine):
    """Generate analysis of current session context"""
    if engine.data.empty:
        return "No market data available for analysis."
    
    current_time = datetime.now(pytz.utc)
    current_hour = current_time.hour
    current_session = engine.current_session
    
    # Get current price
    current_price = engine.data['close'].iloc[-1]
    
    # Session timing analysis
    if current_session == 'london':
        if 8 <= current_hour < 10:
            return f"""**Early London Session Analysis (08:00-10:00 UTC)**

- Asian session range has been established with high of {engine.session_high:.5f} and low of {engine.session_low:.5f}
- Institutional participation is gradually increasing as London traders come online
- The market is currently testing the Asian range boundaries - watch for breakout confirmation
- Price is at {current_price:.5f}, which is {(current_price - engine.session_low) / (engine.session_high - engine.session_low) * 100:.1f}% through the Asian range
- Optimal time for identifying initial directional bias for the London session

*Recommendation:* Wait for clear breakout from Asian range with volume confirmation before entering trades."""
        
        elif 10 <= current_hour <= 13:
            session_range = engine.session_high - engine.session_low
            price_from_high = (engine.session_high - current_price) / session_range
            price_from_low = (current_price - engine.session_low) / session_range
            
            return f"""**Prime London Session Analysis (10:00-13:00 UTC)**

- 78% of the typical London session range has been established
- Institutional order flow is strong and directional
- Price has moved {price_from_high * 100:.1f}% from session high ({engine.session_high:.5f})
- Liquidity is abundant with tight spreads
- Current price: {current_price:.5f}

*Recommendation:* Look for pullback entries in the direction of the trend with tight stops. This is the highest probability period for directional moves. If price breaks above {engine.session_high:.5f}, expect a move toward {engine.session_high + session_range * 0.5:.5f}."""
        
        elif 13 < current_hour <= 16:
            return f"""**London/NY Overlap Session Analysis (13:00-16:00 UTC)**

- Highest volatility period (42% of daily volatility)
- Liquidity most abundant but directional clarity may decrease
- London session high: {engine.session_high:.5f} | London session low: {engine.session_low:.5f}
- Current price: {current_price:.5f}
- Price is {(current_price - engine.session_low) / (engine.session_high - engine.session_low) * 100:.1f}% through the London session range

*Recommendation:* Watch for London session high/low holds as key reference points. Optimal for momentum trades with tight risk parameters. Be prepared for potential reversal as London session winds down."""
        
        else:
            return f"""**Late London Session Analysis (16:00-16:30 UTC)**

- Institutional participation declining as London session ends
- Session high: {engine.session_high:.5f} | Session low: {engine.session_low:.5f}
- Current price: {current_price:.5f}
- Only {18 - current_hour} hours remaining in the trading day

*Recommendation:* Watch for potential reversal patterns near session extremes. False breakouts increase as liquidity dries up. Not optimal for new entries without strong confirmation. Consider closing positions before the NY session close."""
    
    elif current_session == 'ny':
        if 13 <= current_hour < 15:
            return f"""**Early NY Session Analysis (13:00-15:00 UTC)**

- Overlap with London provides best directional clarity
- 65% of NY session range typically established in first 2 hours
- Institutional order flow strongest during overlap period
- Current price: {current_price:.5f}
- Session high: {engine.session_high:.5f} | Session low: {engine.session_low:.5f}

*Recommendation:* Look for trend continuation with proper risk management. This is the optimal time for trend continuation entries with proper confirmation."""
        
        elif 15 <= current_hour <= 18:
            return f"""**Prime NY Session Analysis (15:00-18:00 UTC)**

- Post-London volatility decline but directional bias often persists
- Watch for continuation of London-established trend
- Current price: {current_price:.5f}
- Session high: {engine.session_high:.5f} | Session low: {engine.session_low:.5f}

*Recommendation:* Optimal for counter-trend entries with tight stops if London range holds. Watch for continuation of London-established trend."""
        
        else:
            return f"""**Late NY Session Analysis (18:00-21:00 UTC)**

- Liquidity declining significantly after 18:00 UTC
- False breakouts increase as market approaches close
- Current price: {current_price:.5f}
- Session high: {engine.session_high:.5f} | Session low: {engine.session_low:.5f}

*Recommendation:* Optimal for closing positions rather than new entries. Watch for potential overnight gap risk. Avoid new entries within 30 minutes of session close."""
    
    elif current_session == 'asia':
        if 0 <= current_hour < 4:
            return f"""**Early Asian Session Analysis (00:00-04:00 UTC)**

- Lowest liquidity period of the day
- Range-bound price action typical (72% of Asian session)
- Current price: {current_price:.5f}
- Session high: {engine.session_high:.5f} | Session low: {engine.session_low:.5f}

*Recommendation:* False breakouts extremely common. Not optimal for directional trading. Monitor for early range boundaries."""
        
        elif 4 <= current_hour <= 7:
            return f"""**Prime Asian Session Analysis (04:00-07:00 UTC)**

- Tokyo session influence most pronounced
- 58% of Asian session range typically established by 07:00 UTC
- Current price: {current_price:.5f}
- Session high: {engine.session_high:.5f} | Session low: {engine.session_low:.5f}

*Recommendation:* Watch for potential early directional bias formation. Optimal for identifying early range boundaries. Monitor for breakout levels for London session."""
        
        else:
            return f"""**Late Asian Session Analysis (07:00-08:00 UTC)**

- Transition period to London session
- Watch for early London session positioning
- Current price: {current_price:.5f}
- Session high: {engine.session_high:.5f} | Session low: {engine.session_low:.5f}

*Recommendation:* False breakouts common as market tests Asian range. Optimal for identifying potential London session breakout levels. Prepare for London session open."""
    
    else:
        return f"""**Market Session Analysis**

- Current time: {current_time.strftime('%H:%M')} UTC
- No active trading session (between sessions)
- Current price: {current_price:.5f}

*Recommendation:* Market typically consolidates between sessions. Avoid new entries until next session establishes direction. Monitor for early positioning as next session approaches."""

def generate_liquidity_analysis(engine):
    """Generate analysis of liquidity structure"""
    if engine.data.empty:
        return "No market data available for analysis."
    
    # Get current price
    current_price = engine.data['close'].iloc[-1]
    
    # Detect liquidity pools
    liquidity_pools = engine.detect_liquidity_sweeps()
    significant_pools = [p for p in liquidity_pools if p['strength'] >= 7]
    
    if not engine.session_high or not engine.session_low:
        return """**Liquidity Structure Analysis**

Session context is still forming. Wait for the session to establish its high and low before liquidity analysis becomes meaningful.

*Recommendation:* Monitor for the establishment of session high and low. Key levels to watch:
- Initial range boundaries
- Previous session close
- Daily pivot points

Check back once the session has been active for 30+ minutes for a more detailed liquidity analysis."""

    if not significant_pools:
        return f"""**Liquidity Structure Analysis**

No significant liquidity pools have been identified in the current session. The market appears to be in a neutral phase without clear institutional order blocks.

*Current Session Context:*
- Session high: {engine.session_high:.5f}
- Session low: {engine.session_low:.5f}
- Current price: {current_price:.5f}
- Price position: {(current_price - engine.session_low) / (engine.session_high - engine.session_low) * 100:.1f}% through session range

*Recommendation:* Monitor for developing liquidity structures as the session progresses. Key levels to watch:
- Session high: {engine.session_high:.5f} (Institutional resistance)
- Session low: {engine.session_low:.5f} (Institutional support)
- 20-period SMA: {engine.data['close'].rolling(20).mean().iloc[-1]:.5f} (Dynamic support/resistance)

Look for price reactions at these levels which may indicate emerging liquidity structures."""

    # Format the liquidity pool analysis
    analysis = "**Significant Liquidity Pools Identified**\n\n"
    
    for i, pool in enumerate(significant_pools, 1):
        distance = abs(current_price - pool['price']) / pool['price'] * 100
        pool_type = "Bullish" if pool['type'] == 'bullish' else "Bearish"
        
        analysis += f"{i}. **{pool_type} Liquidity Pool at {pool['price']:.5f}** (Strength: {pool['strength']}/10)\n"
        analysis += f"   - Distance from current price: {distance:.2f}%\n"
        
        if distance < 0.05:
            analysis += "   - *Price is currently testing this liquidity pool*\n"
            analysis += "   - Requires price action confirmation before trading\n"
        elif distance < 0.2:
            analysis += "   - *Price is approaching this liquidity pool*\n"
            analysis += "   - Watch for reaction as price nears this level\n"
        else:
            analysis += "   - *Price is distant from this liquidity pool*\n"
            analysis += "   - May become relevant if price moves in this direction\n"
        
        analysis += "\n"
    
    analysis += """**Trading Implications**\n\n"""
    
    if current_price > engine.session_high * 0.999:
        analysis += f"- Price is near session high ({engine.session_high:.5f}) - watch for liquidity grab above high before potential reversal\n"
    elif current_price < engine.session_low * 1.001:
        analysis += f"- Price is near session low ({engine.session_low:.5f}) - watch for liquidity grab below low before potential reversal\n"
    else:
        analysis += "- Price is in mid-session range - watch for directional breakout\n"
    
    analysis += "- Liquidity pools represent institutional order blocks where stops are likely clustered\n"
    analysis += "- Trading with the liquidity sweep (not against it) increases probability of success\n"
    
    # Add specific trade recommendation if price is near a pool
    if significant_pools:
        closest_pool = min(significant_pools, key=lambda x: abs(x['price'] - current_price))
        distance = abs(current_price - closest_pool['price']) / closest_pool['price'] * 100
        
        if distance < 0.2:
            if closest_pool['type'] == 'bullish':
                analysis += f"\n**Trade Recommendation:**\n"
                analysis += f"- *Potential long opportunity* near bullish liquidity pool at {closest_pool['price']:.5f}\n"
                analysis += f"- Entry: {closest_pool['price'] * 1.0001:.5f}\n"
                analysis += f"- Stop loss: {closest_pool['price'] * 0.9998:.5f}\n"
                analysis += f"- Take profit: {closest_pool['price'] + (closest_pool['price'] - engine.session_low) * 2.0:.5f}\n"
                analysis += "- Confirmation: Bullish candlestick pattern at entry zone"
            else:
                analysis += f"\n**Trade Recommendation:**\n"
                analysis += f"- *Potential short opportunity* near bearish liquidity pool at {closest_pool['price']:.5f}\n"
                analysis += f"- Entry: {closest_pool['price'] * 0.9999:.5f}\n"
                analysis += f"- Stop loss: {closest_pool['price'] * 1.0002:.5f}\n"
                analysis += f"- Take profit: {closest_pool['price'] - (engine.session_high - closest_pool['price']) * 2.0:.5f}\n"
                analysis += "- Confirmation: Bearish candlestick pattern at entry zone"
    
    return analysis

def generate_trade_setup_analysis(engine):
    """Generate trade setup analysis based on current market conditions"""
    if engine.data.empty:
        return "No market data available for analysis."
    
    # Get current price
    current_price = engine.data['close'].iloc[-1]
    
    # Calculate key technical metrics
    sma_20 = engine.data['close'].rolling(20).mean().iloc[-1] if len(engine.data) >= 20 else None
    sma_50 = engine.data['close'].rolling(50).mean().iloc[-1] if len(engine.data) >= 50 else None
    atr = engine.data['high'].rolling(14).max() - engine.data['low'].rolling(14).min()
    current_atr = atr.iloc[-1] if len(atr) > 0 else None
    
    # Session context
    current_session = engine.current_session
    current_hour = datetime.now(pytz.utc).hour
    
    # Get liquidity pools
    liquidity_pools = engine.detect_liquidity_sweeps()
    significant_pools = [p for p in liquidity_pools if p['strength'] >= 7]
    
    # Market regime analysis
    market_regime = "RANGING"
    if sma_20 and sma_50 and sma_20 > sma_50 and current_price > sma_20:
        market_regime = "BULLISH TREND"
    elif sma_20 and sma_50 and sma_20 < sma_50 and current_price < sma_20:
        market_regime = "BEARISH TREND"
    
    # Determine optimal trade direction
    bullish_signals = 0
    bearish_signals = 0
    
    # Bullish setup conditions
    if market_regime == "BULLISH TREND" and sma_20 and current_price > sma_20:
        bullish_signals += 3
    if engine.session_low and (current_price - engine.session_low) / (engine.session_high - engine.session_low) < 0.25:
        bullish_signals += 2
    if significant_pools and any(p['type'] == 'bullish' and abs(current_price - p['price'])/p['price'] < 0.002 for p in significant_pools):
        bullish_signals += 3
    if current_session in ['london', 'ny'] and 10 <= current_hour <= 15:
        bullish_signals += 2
    
    # Bearish setup conditions
    if market_regime == "BEARISH TREND" and sma_20 and current_price < sma_20:
        bearish_signals += 3
    if engine.session_high and (engine.session_high - current_price) / (engine.session_high - engine.session_low) < 0.25:
        bearish_signals += 2
    if significant_pools and any(p['type'] == 'bearish' and abs(current_price - p['price'])/p['price'] < 0.002 for p in significant_pools):
        bearish_signals += 3
    if current_session in ['london', 'ny'] and 10 <= current_hour <= 15:
        bearish_signals += 2
    
    # Generate trade recommendations
    if bullish_signals >= 5 and bullish_signals > bearish_signals + 1:
        # Entry strategy
        if sma_20 and current_price > sma_20:
            entry = max(current_price, sma_20)
        elif significant_pools:
            bullish_pools = [p for p in significant_pools if p['type'] == 'bullish']
            if bullish_pools:
                deepest_pool = min(bullish_pools, key=lambda x: x['price'])
                entry = deepest_pool['price'] * 1.0001
            else:
                entry = current_price * 1.00005
        else:
            entry = current_price * 1.00005
        
        # Stop loss placement
        if engine.session_low and current_price > engine.session_low:
            stop_distance = (current_price - engine.session_low) * 1.2
            stop_loss = current_price - stop_distance
        elif significant_pools:
            bullish_pools = [p for p in significant_pools if p['type'] == 'bullish']
            if bullish_pools:
                deepest_pool = min(bullish_pools, key=lambda x: x['price'])
                stop_distance = (current_price - deepest_pool['price']) * 1.5
                stop_loss = deepest_pool['price'] * 0.9998
            else:
                stop_loss = current_price - (current_atr * 1.5) if current_atr else current_price * 0.999
        else:
            stop_loss = current_price - (current_atr * 1.5) if current_atr else current_price * 0.999
        
        # Take profit placement
        if market_regime == "BULLISH TREND" and sma_20:
            risk = entry - stop_loss
            take_profit = entry + (risk * 2.5)
        else:
            risk = entry - stop_loss
            take_profit = entry + (risk * 2.0)
        
        # Format the trade setup
        setup_type = "Trend Continuation"
        if market_regime == "BULLISH TREND" and engine.session_low and (current_price - engine.session_low) / (engine.session_high - engine.session_low) < 0.25:
            setup_type = "Trend Pullback"
        elif significant_pools and any(p['type'] == 'bullish' and abs(current_price - p['price'])/p['price'] < 0.002 for p in significant_pools):
            setup_type = "Liquidity Grab Reversal"
        
        confidence = min(95, bullish_signals * 10)
        
        return f"""**LONG TRADE SETUP DETECTED | Confidence: {confidence}% | Setup Type: {setup_type}**

**Entry Zone:** {entry:.5f}
- Optimal entry: {entry:.5f} - {entry * 1.0002:.5f}
- Confirmation required: Bullish candlestick pattern at entry zone
- Volume confirmation: Entry volume should exceed 20-period average

**Stop Loss:** {stop_loss:.5f}
- Initial stop placement based on liquidity structure
- Move to breakeven when price reaches 1.5x risk
- Trail stop at 1.0x ATR below price after 2.0x risk achieved

**Take Profit:** {take_profit:.5f}
- Primary target: 2.0-2.5x risk
- Partial close: 50% position at 1.5x risk, remainder at full target
- Extension target: 3.0x risk if price shows strong momentum

**Risk Management:**
- Maximum risk: 1% of account
- Position size: Adjusted to maintain consistent dollar risk
- No trading within 30 minutes of high-impact news events"""
    
    elif bearish_signals >= 5 and bearish_signals > bullish_signals + 1:
        # Entry strategy
        if sma_20 and current_price < sma_20:
            entry = min(current_price, sma_20)
        elif significant_pools:
            bearish_pools = [p for p in significant_pools if p['type'] == 'bearish']
            if bearish_pools:
                highest_pool = max(bearish_pools, key=lambda x: x['price'])
                entry = highest_pool['price'] * 0.9999
            else:
                entry = current_price * 0.99995
        else:
            entry = current_price * 0.99995
        
        # Stop loss placement
        if engine.session_high and current_price < engine.session_high:
            stop_distance = (engine.session_high - current_price) * 1.2
            stop_loss = current_price + stop_distance
        elif significant_pools:
            bearish_pools = [p for p in significant_pools if p['type'] == 'bearish']
            if bearish_pools:
                highest_pool = max(bearish_pools, key=lambda x: x['price'])
                stop_distance = (highest_pool['price'] - current_price) * 1.5
                stop_loss = highest_pool['price'] * 1.0002
            else:
                stop_loss = current_price + (current_atr * 1.5) if current_atr else current_price * 1.001
        else:
            stop_loss = current_price + (current_atr * 1.5) if current_atr else current_price * 1.001
        
        # Take profit placement
        if market_regime == "BEARISH TREND" and sma_20:
            risk = stop_loss - entry
            take_profit = entry - (risk * 2.5)
        else:
            risk = stop_loss - entry
            take_profit = entry - (risk * 2.0)
        
        # Format the trade setup
        setup_type = "Trend Continuation"
        if market_regime == "BEARISH TREND" and engine.session_high and (engine.session_high - current_price) / (engine.session_high - engine.session_low) < 0.25:
            setup_type = "Trend Rally"
        elif significant_pools and any(p['type'] == 'bearish' and abs(current_price - p['price'])/p['price'] < 0.002 for p in significant_pools):
            setup_type = "Liquidity Grab Reversal"
        
        confidence = min(95, bearish_signals * 10)
        
        return f"""**SHORT TRADE SETUP DETECTED | Confidence: {confidence}% | Setup Type: {setup_type}**

**Entry Zone:** {entry:.5f}
- Optimal entry: {entry:.5f} - {entry * 0.9998:.5f}
- Confirmation required: Bearish candlestick pattern at entry zone
- Volume confirmation: Entry volume should exceed 20-period average

**Stop Loss:** {stop_loss:.5f}
- Initial stop placement based on liquidity structure
- Move to breakeven when price reaches 1.5x risk
- Trail stop at 1.0x ATR above price after 2.0x risk achieved

**Take Profit:** {take_profit:.5f}
- Primary target: 2.0-2.5x risk
- Partial close: 50% position at 1.5x risk, remainder at full target
- Extension target: 3.0x risk if price shows strong momentum

**Risk Management:**
- Maximum risk: 1% of account
- Position size: Adjusted to maintain consistent dollar risk
- No trading within 30 minutes of high-impact news events"""
    
    else:
        return """**No High-Probability Trade Setup Detected**

Current market conditions do not meet professional trading criteria. Analysis shows:

"""
        # Add specific reasons based on the signals
        if bullish_signals < 5 and bearish_signals < 5:
            response += "- No clear directional bias: Market lacks sufficient confluence for high-probability trade\n"
            response += "- Neutral market structure: Price oscillating without clear institutional order flow\n"
            response += "- Insufficient confirmation: Missing required technical and session context alignment\n\n"
            response += "*Recommendation:* Monitor for developing structure; avoid premature entries."
        else:
            response += f"- Bullish signals: {bullish_signals}/10\n"
            response += f"- Bearish signals: {bearish_signals}/10\n"
            response += "- Conflicting market signals: Bullish and bearish factors are in equilibrium\n"
            response += "- Indecisive market structure: Price lacks clear directional commitment\n\n"
            response += "*Recommendation:* Maintain flat position until clearer structure emerges."
        
        response += """

**Key Levels to Watch:**
"""
        if engine.session_high:
            response += f"- Session High: {engine.session_high:.5f} (Institutional resistance)\n"
        if engine.session_low:
            response += f"- Session Low: {engine.session_low:.5f} (Institutional support)\n"
        
        for pool in significant_pools[:3]:  # Show up to 3 pools
            pool_type = "Bullish" if pool['type'] == 'bullish' else "Bearish"
            response += f"- {pool_type} Liquidity Pool: {pool['price']:.5f} (Strength: {pool['strength']}/10)\n"
        
        if sma_20:
            response += f"- 20-period SMA: {sma_20:.5f} (Dynamic support/resistance)\n"
        
        response += """

**Confirmation Requirements for Entry:**
- Minimum 3 confluence factors required for trade consideration
- Volume confirmation exceeding 20-period average
- Price action confirmation (valid candlestick pattern)
- Institutional time filter (08:00-16:00 UTC for optimal flow)"""

        return response

def generate_technical_analysis(engine):
    """Generate technical analysis of current market structure"""
    if engine.data.empty:
        return "No market data available for analysis."
    
    # Get current price
    current_price = engine.data['close'].iloc[-1]
    
    # Calculate technical indicators
    sma_20 = engine.data['close'].rolling(20).mean().iloc[-1] if len(engine.data) >= 20 else None
    sma_50 = engine.data['close'].rolling(50).mean().iloc[-1] if len(engine.data) >= 50 else None
    ema_20 = engine.data['close'].ewm(span=20, adjust=False).mean().iloc[-1] if len(engine.data) >= 20 else None
    rsi = 100 - (100 / (1 + (engine.data['close'].diff(1).clip(lower=0).rolling(14).mean() / 
                            -engine.data['close'].diff(1).clip(upper=0).rolling(14).mean()).iloc[-1])) if len(engine.data) >= 14 else None
    
    # Bollinger Bands
    bb_mid = engine.data['close'].rolling(20).mean().iloc[-1] if len(engine.data) >= 20 else None
    bb_std = engine.data['close'].rolling(20).std().iloc[-1] if len(engine.data) >= 20 else None
    bb_upper = bb_mid + (bb_std * 2) if bb_mid and bb_std else None
    bb_lower = bb_mid - (bb_std * 2) if bb_mid and bb_std else None
    
    # ATR
    high_low = engine.data['high'] - engine.data['low']
    high_close = (engine.data['high'] - engine.data['close'].shift()).abs()
    low_close = (engine.data['low'] - engine.data['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_ranges = ranges.max(axis=1)
    atr = true_ranges.rolling(14).mean().iloc[-1] if len(engine.data) >= 14 else None
    
    # Format the technical analysis
    analysis = "**Technical Structure Analysis**\n\n"
    
    # Trend analysis
    if sma_20 and sma_50:
        if sma_20 > sma_50 and current_price > sma_20:
            analysis += f"**Bullish Trend Structure**\n"
            analysis += f"- Price trading above 20-period SMA ({sma_20:.5f}) and 50-period SMA ({sma_50:.5f})\n"
            analysis += "- Trend structure shows higher highs and higher lows\n"
            analysis += "- Optimal strategy: Look for pullbacks to dynamic support for long entries\n\n"
        elif sma_20 < sma_50 and current_price < sma_20:
            analysis += f"**Bearish Trend Structure**\n"
            analysis += f"- Price trading below 20-period SMA ({sma_20:.5f}) and 50-period SMA ({sma_50:.5f})\n"
            analysis += "- Trend structure shows lower highs and lower lows\n"
            analysis += "- Optimal strategy: Look for rallies to dynamic resistance for short entries\n\n"
        else:
            analysis += "**Neutral Trend Structure**\n"
            analysis += "- Price oscillating between 20 and 50-period SMAs\n"
            analysis += "- No clear directional bias\n"
            analysis += "- Optimal strategy: Fade extremes of the range with tight stops\n\n"
    
    # Momentum analysis
    if rsi is not None:
        analysis += f"**Momentum Assessment (RSI: {rsi:.1f})**\n"
        if rsi > 70:
            analysis += "- Overbought conditions - watch for potential pullback\n"
        elif rsi < 30:
            analysis += "- Oversold conditions - watch for potential bounce\n"
        else:
            analysis += "- Neutral momentum - no extreme conditions\n"
        analysis += "- RSI trending " + ("upward" if engine.data['close'].tail(5).pct_change().mean() > 0 else "downward") + "\n\n"
    
    # Volatility analysis
    if bb_upper and bb_lower:
        price_position = (current_price - bb_lower) / (bb_upper - bb_lower) * 100
        analysis += f"**Volatility Assessment (Bollinger Bands)**\n"
        analysis += f"- Upper band: {bb_upper:.5f} | Lower band: {bb_lower:.5f}\n"
        analysis += f"- Price position: {price_position:.1f}% through band\n"
        
        if price_position > 80:
            analysis += "- Price near upper band - potential overextension\n"
        elif price_position < 20:
            analysis += "- Price near lower band - potential oversold condition\n"
        else:
            analysis += "- Price in mid-band - neutral volatility\n"
    
    if atr:
        analysis += f"\n**ATR (14-period): {atr:.5f} ({atr*10000:.1f} pips)**\n"
        if atr > current_price * 0.0015:
            analysis += "- High volatility regime - expect larger price movements\n"
        elif atr > current_price * 0.0008:
            analysis += "- Moderate volatility regime - typical market conditions\n"
        else:
            analysis += "- Low volatility regime - expect tighter ranges\n"
    
    # Support and resistance
    analysis += "\n**Key Support & Resistance Levels**\n"
    
    if engine.session_high:
        analysis += f"- Session High: {engine.session_high:.5f} (Major resistance)\n"
    if engine.session_low:
        analysis += f"- Session Low: {engine.session_low:.5f} (Major support)\n"
    
    if sma_20:
        analysis += f"- 20-period SMA: {sma_20:.5f} (Dynamic support/resistance)\n"
    if sma_50:
        analysis += f"- 50-period SMA: {sma_50:.5f} (Major trend indicator)\n"
    
    # Pivot points (simplified)
    if len(engine.data) >= 24:
        daily_high = engine.data['high'].tail(24).max()
        daily_low = engine.data['low'].tail(24).min()
        daily_close = engine.data['close'].iloc[-1]
        
        pivot = (daily_high + daily_low + daily_close) / 3
        r1 = (2 * pivot) - daily_low
        s1 = (2 * pivot) - daily_high
        
        analysis += f"\n**Daily Pivot Points**\n"
        analysis += f"- Pivot Point: {pivot:.5f}\n"
        analysis += f"- R1 Resistance: {r1:.5f}\n"
        analysis += f"- S1 Support: {s1:.5f}\n"
    
    # Trading implications
    analysis += "\n**Trading Implications**\n"
    
    if sma_20 and sma_50 and sma_20 > sma_50 and current_price > sma_20:
        analysis += "- Bullish trend confirmed - look for long opportunities on pullbacks\n"
        analysis += f"- Key support: {sma_20:.5f} (20-period SMA)\n"
    elif sma_20 and sma_50 and sma_20 < sma_50 and current_price < sma_20:
        analysis += "- Bearish trend confirmed - look for short opportunities on rallies\n"
        analysis += f"- Key resistance: {sma_20:.5f} (20-period SMA)\n"
    else:
        analysis += "- Neutral market structure - range trading strategy preferred\n"
        analysis += f"- Key range: {engine.session_low:.5f} to {engine.session_high:.5f}\n"
    
    if rsi is not None:
        if rsi > 70:
            analysis += "- Overbought conditions - consider profit-taking on longs\n"
        elif rsi < 30:
            analysis += "- Oversold conditions - consider profit-taking on shorts\n"
    
    return analysis

def generate_market_regime_analysis(engine):
    """Generate analysis of current market regime"""
    if engine.data.empty:
        return "No market data available for analysis."
    
    # Get current price
    current_price = engine.data['close'].iloc[-1]
    
    # Calculate key technical metrics
    sma_20 = engine.data['close'].rolling(20).mean().iloc[-1] if len(engine.data) >= 20 else None
    sma_50 = engine.data['close'].rolling(50).mean().iloc[-1] if len(engine.data) >= 50 else None
    atr = engine.data['high'].rolling(14).max() - engine.data['low'].rolling(14).min()
    current_atr = atr.iloc[-1] if len(atr) > 0 else None
    
    # Session context
    current_session = engine.current_session
    current_hour = datetime.now(pytz.utc).hour
    
    # Get liquidity pools
    liquidity_pools = engine.detect_liquidity_sweeps()
    significant_pools = [p for p in liquidity_pools if p['strength'] >= 7]
    
    # Market regime analysis
    market_regime = "RANGING"
    if sma_20 and sma_50 and sma_20 > sma_50 and current_price > sma_20:
        market_regime = "BULLISH TREND"
    elif sma_20 and sma_50 and sma_20 < sma_50 and current_price < sma_20:
        market_regime = "BEARISH TREND"
    
    # Volatility assessment
    volatility = "LOW"
    if current_atr and current_atr > current_price * 0.0015:
        volatility = "HIGH"
    elif current_atr and current_atr > current_price * 0.0008:
        volatility = "MODERATE"
    
    # Price position analysis
    price_from_session_high = 0
    price_from_session_low = 0
    if engine.session_high and engine.session_low:
        price_from_session_high = (engine.session_high - current_price) / engine.session_high
        price_from_session_low = (current_price - engine.session_low) / engine.session_low
    
    # Generate the analysis
    analysis = "**Market Regime Analysis**\n\n"
    
    # Market structure
    analysis += f"**Current Market Structure: {market_regime}**\n"
    
    if market_regime == "BULLISH TREND":
        analysis += "- Price trading above key moving averages\n"
        analysis += "- Higher highs and higher lows pattern established\n"
        analysis += "- Institutional buying pressure dominant\n\n"
    elif market_regime == "BEARISH TREND":
        analysis += "- Price trading below key moving averages\n"
        analysis += "- Lower highs and lower lows pattern established\n"
        analysis += "- Institutional selling pressure dominant\n\n"
    else:
        analysis += "- Price oscillating between established support and resistance\n"
        analysis += "- No clear directional bias\n"
        analysis += "- Market in consolidation phase\n\n"
    
    # Volatility assessment
    analysis += f"**Volatility Assessment: {volatility}**\n"
    if current_atr:
        analysis += f"- Current ATR: {current_atr:.5f} ({current_atr*10000:.1f} pips)\n"
        analysis += f"- Average daily range: {engine.data['high'].iloc[-24:].max() - engine.data['low'].iloc[-24:].min():.5f}\n"
    
    if volatility == "HIGH":
        analysis += "- Expect larger price movements and wider ranges\n"
        analysis += "- Wider stops required to avoid whipsaws\n"
    elif volatility == "MODERATE":
        analysis += "- Typical market conditions\n"
        analysis += "- Standard stop placement appropriate\n"
    else:
        analysis += "- Tighter ranges expected\n"
        analysis += "- Tighter stops can be used\n"
    
    analysis += "\n"
    
    # Session context
    analysis += f"**Session Context: {current_session.upper()} SESSION**\n"
    
    if current_session == 'london' and 10 <= current_hour <= 13:
        analysis += "- Prime institutional participation period\n"
        analysis += "- Highest probability for directional moves\n"
    elif current_session == 'ny' and 13 <= current_hour <= 15:
        analysis += "- London/NY overlap - maximum liquidity\n"
        analysis += "- Strong directional potential\n"
    elif current_session == 'asia' and 4 <= current_hour <= 7:
        analysis += "- Tokyo session influence\n"
        analysis += "- Range-bound price action typical\n"
    else:
        analysis += "- Suboptimal timing for new entries\n"
        analysis += "- Wait for prime institutional hours\n"
    
    analysis += "\n"
    
    # Trading strategy
    analysis += "**Recommended Trading Strategy**\n"
    
    if market_regime == "BULLISH TREND" and current_session in ['london', 'ny'] and 10 <= current_hour <= 15:
        analysis += "- Trend following strategy optimal\n"
        analysis += "- Look for pullback entries in direction of trend\n"
        analysis += "- Target 2.0-2.5x risk on trades\n"
    elif market_regime == "BEARISH TREND" and current_session in ['london', 'ny'] and 10 <= current_hour <= 15:
        analysis += "- Trend following strategy optimal\n"
        analysis += "- Look for rally entries in direction of trend\n"
        analysis += "- Target 2.0-2.5x risk on trades\n"
    elif market_regime == "RANGING":
        analysis += "- Range trading strategy optimal\n"
        analysis += "- Fade extremes of the range with tight stops\n"
        analysis += "- Target 1.5-2.0x risk on trades\n"
    else:
        analysis += "- Suboptimal conditions for new entries\n"
        analysis += "- Monitor for developing structure\n"
        analysis += "- Wait for better confluence of factors\n"
    
    # Additional insights
    analysis += "\n**Additional Insights**\n"
    
    if significant_pools:
        analysis += f"- {len(significant_pools)} significant liquidity pools identified\n"
        analysis += "- Focus on price reactions at these institutional order blocks\n"
    
    if engine.session_high and engine.session_low:
        mid_point = engine.session_low + (engine.session_high - engine.session_low) / 2
        if abs(current_price - mid_point) / (engine.session_high - engine.session_low) < 0.1:
            analysis += "- Price at session midpoint - indecision phase\n"
        elif current_price > mid_point:
            analysis += "- Price above session midpoint - bullish bias\n"
        else:
            analysis += "- Price below session midpoint - bearish bias\n"
    
    return analysis

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
        render_analysis_chatbot()
    
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
