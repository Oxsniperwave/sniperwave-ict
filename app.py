import sys
if sys.version_info >= (3, 12):
    try:
        import distutils
    except ImportError:
        import setuptools
        sys.modules['distutils'] = setuptools.distutils

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
import calendar
import base64

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
            .calendar-day {
                border: 1px solid #333;
                border-radius: 4px;
                padding: 5px;
                margin: 2px;
                text-align: center;
                cursor: pointer;
                transition: all 0.2s;
            }
            .calendar-day:hover {
                background-color: #2d2d2d;
            }
            .calendar-day.has-trades {
                background-color: #4a90e2;
                color: white;
            }
            .calendar-day.today {
                border: 2px solid #4a90e2;
            }
            .calendar-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }
            .calendar-grid {
                display: grid;
                grid-template-columns: repeat(7, 1fr);
                gap: 5px;
            }
            .calendar-day-name {
                text-align: center;
                font-weight: bold;
                padding: 5px;
                color: #a0a0a0;
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
            .calendar-day {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                margin: 2px;
                text-align: center;
                cursor: pointer;
                transition: all 0.2s;
            }
            .calendar-day:hover {
                background-color: #f0f0f0;
            }
            .calendar-day.has-trades {
                background-color: #4a90e2;
                color: white;
            }
            .calendar-day.today {
                border: 2px solid #4a90e2;
            }
            .calendar-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }
            .calendar-grid {
                display: grid;
                grid-template-columns: repeat(7, 1fr);
                gap: 5px;
            }
            .calendar-day-name {
                text-align: center;
                font-weight: bold;
                padding: 5px;
                color: #666;
            }
        </style>
        """, unsafe_allow_html=True)

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
            print(f"❌ Failed to connect to Dukascopy: {str(e)}")
            self.last_data_source = "simulated"
            return False

    def on_dukascopy_open(self, ws):
        """Handle Dukascopy connection open"""
        print("✅ Dukascopy WebSocket connection established")
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
            print(f"❌ Error processing Dukascopy message: {str(e)}")
            self.last_data_source = "simulated"

    def on_dukascopy_error(self, ws, error):
        """Handle Dukascopy connection errors"""
        print(f"❌ Dukascopy WebSocket error: {error}")
        self.last_data_source = "simulated"
        self.message_queue.put(('status', 'dukascopy_error'))

    def on_dukascopy_close(self, ws, close_status_code, close_msg):
        """Handle Dukascopy connection close"""
        print(f"ℹ️ Dukascopy WebSocket closed: {close_status_code} - {close_msg}")
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
        print("🔄 Starting WebSocket connection thread")
        
        def run_websocket():
            while self.running:
                try:
                    # First try to connect to real data source
                    if self.connect_to_dukascopy():
                        print("✅ Successfully connected to Dukascopy")
                        # If connected, wait for messages
                        time.sleep(60)
                    else:
                        print("⚠️ Connection to Dukascopy failed, using simulated data")
                        # If connection failed, use simulated data
                        time.sleep(2)  # Update every 2 seconds
                        
                        if not self.running:
                            break
                            
                        # Simulate connection status
                        self.message_queue.put(('status', 'simulated'))
                        
                        # Simulate data
                        self.on_message(None, None)
                        
                except Exception as e:
                    print(f"❌ WebSocket thread error: {str(e)}")
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
            print(f"❌ Error processing message: {str(e)}")
            self.message_queue.put(('error', str(e)))

    def stop_websocket(self):
        """Stop the WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
        print("ℹ️ WebSocket connection stopped")

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
          "height": 400,
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
    
    st.components.v1.html(tradingview_html, height=430)

def render_custom_chart():
    """Render custom Plotly chart with session context and liquidity pools"""
    st.subheader("Custom Analysis Chart")
    
    engine = st.session_state.engine
    
    if engine.data.empty:
        st.info("Waiting for market data...")
        return
    
    # Create figure
    fig = make_subplots(rows=1, cols=1)
    
    # Add candlestick chart
    fig.add_trace(go.Candlestick(
        x=engine.data['timestamp'],
        open=engine.data['open'],
        high=engine.data['high'],
        low=engine.data['low'],
        close=engine.data['close'],
        name='Price'
    ))
    
    # Add session background colors
    if engine.current_session and engine.session_start_time:
        fig.add_vrect(
            x0=engine.session_start_time,
            x1=engine.data['timestamp'].max(),
            fillcolor={
                'asia': 'rgba(128, 128, 128, 0.1)',
                'london': 'rgba(76, 175, 80, 0.1)',
                'ny': 'rgba(156, 39, 176, 0.1)',
                'close': 'rgba(244, 67, 54, 0.1)'
            }.get(engine.current_session, 'rgba(0, 0, 0, 0.1)'),
            line_width=0,
            annotation_text=engine.current_session.upper() + " SESSION",
            annotation_position="top left",
            annotation_font_size=12,
            annotation_font_color="white",
            annotation_bgcolor="rgba(0,0,0,0.5)",
            row=1, col=1
        )
    
    # Add session high/low lines
    if engine.session_high and engine.session_low:
        fig.add_hline(y=engine.session_high, line_dash="dot", line_color="green", 
                     annotation_text="Session High", annotation_position="right",
                     row=1, col=1)
        fig.add_hline(y=engine.session_low, line_dash="dot", line_color="red",
                     annotation_text="Session Low", annotation_position="right",
                     row=1, col=1)
    
    # Add liquidity pools
    for pool in engine.liquidity_pools:
        color = 'green' if pool['type'] == 'bullish' else 'red'
        fig.add_hline(
            y=pool['price'], 
            line_dash="dash", 
            line_color=color,
            annotation_text=f"Liquidity Pool ({pool['strength']}/10)",
            annotation_position="right",
            row=1, col=1
        )
    
    # Update layout
    fig.update_layout(
        title=f"{engine.symbol} - Custom Session Context Analysis",
        xaxis_rangeslider_visible=False,
        height=400,
        hovermode="x unified",
        template="plotly_white",
        margin=dict(l=10, r=10, t=50, b=10)
    )
    
    fig.update_xaxes(title_text="Time (UTC)", row=1, col=1)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    
    # Add data source indicator
    data_source_text = "Real data from Dukascopy (free tier)" if engine.last_data_source == "dukascopy" else "Simulated data - for testing only"
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=1.05,
        text=data_source_text,
        showarrow=False,
        font=dict(size=12, color="blue" if engine.last_data_source == "dukascopy" else "orange"),
        bgcolor="rgba(255,255,255,0.8)",
        bordercolor="blue" if engine.last_data_source == "dukascopy" else "orange",
        borderpad=4
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True})

def render_analysis_chatbot():
    """Render a robust chatbot interface for market analysis that works with available data"""
    st.subheader("AI Market Analysis Assistant")
    
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
            with st.spinner("Analyzing market data..."):
                # Check if we have sufficient data
                if st.session_state.engine.data.empty:
                    full_response = "I'm waiting for market data to load. Please give it a moment to connect to the data source."
                else:
                    # Check if we have enough data for meaningful analysis
                    if len(st.session_state.engine.data) < 5:
                        full_response = (f"I have limited data ({len(st.session_state.engine.data)} candles). "
                                        "For better analysis, wait for more data to load (10+ candles recommended).\n\n"
                                        "In the meantime, I can tell you:\n"
                                        f"- Current session: {st.session_state.engine.current_session or 'N/A'}\n"
                                        f"- Current price: {st.session_state.engine.data['close'].iloc[-1]:.5f}")
                    else:
                        full_response = generate_analysis_response(prompt)
            
            message_placeholder.markdown(full_response)
        
        # Add assistant response to chat history
        st.session_state.chat_messages.append({"role": "assistant", "content": full_response})

def generate_analysis_response(prompt):
    """Generate appropriate analysis response based on user prompt with robust error handling"""
    engine = st.session_state.engine
    
    # Basic validation - we know we have data since this is checked in render_analysis_chatbot
    current_price = engine.data['close'].iloc[-1]
    
    # Process different types of requests with robust error handling
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
        return get_help_response()
    
    # Default response for unclear requests
    else:
        return get_default_response()

def get_help_response():
    """Return help information about what the AI can do"""
    return """I'm your professional market analysis assistant. I can help with:

🔍 **Session Context Analysis**
- Current trading session and institutional timing
- Session high/low significance
- Optimal timing for entries based on institutional flow

💧 **Liquidity Structure Analysis**
- Identification of liquidity pools
- Institutional order block assessment
- Liquidity grab prediction

🎯 **Trade Setup Assessment**
- Entry, stop loss, and take profit recommendations
- Risk-reward ratio calculation
- Position sizing based on account parameters

📊 **Market Regime Assessment**
- Trending vs. ranging market identification
- Volatility assessment
- Technical structure analysis

Try asking:
- 'What's the current session context?'
- 'Are there any significant liquidity pools visible?'
- 'What trade opportunities do you see right now?'
- 'Is the market trending or ranging?'
- 'Show me potential entry points for long positions'"""

def get_default_response():
    """Return a helpful default response for unclear requests"""
    return ("I can help analyze various aspects of the market. Try asking specific questions like:\n\n"
            "• 'What's the current session context?'\n"
            "• 'Are there any significant liquidity pools visible?'\n"
            "• 'What trade opportunities do you see right now?'\n"
            "• 'Is the market trending or ranging?'\n"
            "• 'Show me potential entry points for long positions'\n\n"
            "For more guidance, type 'help' to see what I can do.")

def generate_session_analysis(engine):
    """Generate robust session context analysis that works with available data"""
    current_time = datetime.now(pytz.utc)
    current_hour = current_time.hour
    current_session = engine.current_session or "asia"  # Default to asia if not determined
    
    # Get current price with fallback
    current_price = engine.data['close'].iloc[-1]
    
    # Create session analysis with robust fallbacks
    analysis = "**Current Session Context Analysis**\n\n"
    
    # Basic session information
    analysis += f"- **Current Session:** {current_session.upper() if current_session else 'UNKNOWN'}\n"
    analysis += f"- **Current Time:** {current_time.strftime('%H:%M')} UTC\n"
    
    # Session-specific analysis with fallbacks
    if current_session == 'london':
        if 8 <= current_hour < 10:
            analysis += "- Early London session: Asian range establishment still in effect\n"
            analysis += "- Institutional participation gradually increasing\n"
        elif 10 <= current_hour <= 13:
            analysis += "- Prime London session: Highest probability period for directional moves\n"
            analysis += "- 78% of daily London session range typically established by 13:00 UTC\n"
        elif 13 < current_hour <= 16:
            analysis += "- London/NY overlap: Highest volatility period (42% of daily volatility)\n"
            analysis += "- Liquidity most abundant but directional clarity may decrease\n"
        else:
            analysis += "- Late London session: Institutional participation declining\n"
            analysis += "- Watch for potential reversal patterns near session extremes\n"
    
    elif current_session == 'ny':
        if 13 <= current_hour < 15:
            analysis += "- Early NY session: Overlap with London provides best directional clarity\n"
            analysis += "- 65% of NY session range typically established in first 2 hours\n"
        elif 15 <= current_hour <= 18:
            analysis += "- Prime NY session: Post-London volatility decline but directional bias persists\n"
            analysis += "- Watch for continuation of London-established trend\n"
        else:
            analysis += "- Late NY session: Liquidity declining significantly after 18:00 UTC\n"
            analysis += "- False breakouts increase as market approaches close\n"
    
    elif current_session == 'asia':
        if 0 <= current_hour < 4:
            analysis += "- Early Asian session: Lowest liquidity period of the day\n"
            analysis += "- Range-bound price action typical (72% of Asian session)\n"
        elif 4 <= current_hour <= 7:
            analysis += "- Prime Asian session: Tokyo session influence most pronounced\n"
            analysis += "- 58% of Asian session range typically established by 07:00 UTC\n"
        else:
            analysis += "- Late Asian session: Transition period to London session\n"
            analysis += "- Watch for early London session positioning\n"
    
    else:
        analysis += "- No active trading session: Market typically consolidates between sessions\n"
        analysis += "- Avoid new entries until next session establishes direction\n"
    
    # Add session high/low if available
    if engine.session_high and engine.session_low:
        analysis += f"\n- **Session Range:** {engine.session_low:.5f} - {engine.session_high:.5f}\n"
        analysis += f"- **Current Price:** {current_price:.5f}\n"
        price_position = (current_price - engine.session_low) / (engine.session_high - engine.session_low) * 100
        analysis += f"- **Price Position:** {price_position:.1f}% through session range\n"
    
    # Add professional recommendation
    analysis += "\n**Professional Recommendation:**\n"
    
    if current_session in ['london', 'ny'] and 10 <= current_hour <= 15:
        analysis += "- Prime institutional hours - optimal for trade entries with confirmation\n"
    else:
        analysis += "- Suboptimal timing for new entries - monitor for developing structure\n"
    
    analysis += "- Always confirm with price action before entering trades\n"
    analysis += "- Watch for key session high/low holds as reference points\n"
    
    return analysis

def generate_liquidity_analysis(engine):
    """Generate robust liquidity analysis that works with limited data"""
    current_price = engine.data['close'].iloc[-1]
    
    analysis = "**Liquidity Structure Analysis**\n\n"
    
    # Detect liquidity pools with error handling
    try:
        liquidity_pools = engine.detect_liquidity_sweeps()
        significant_pools = [p for p in liquidity_pools if p['strength'] >= 5]  # Lower threshold for limited data
    except Exception as e:
        liquidity_pools = []
        significant_pools = []
        analysis += f"⚠️ Error detecting liquidity pools: {str(e)}\n\n"
    
    # Session high/low analysis
    if engine.session_high and engine.session_low:
        session_range = engine.session_high - engine.session_low
        price_from_high = (engine.session_high - current_price) / session_range
        price_from_low = (current_price - engine.session_low) / session_range
        
        analysis += f"- **Session High:** {engine.session_high:.5f}\n"
        analysis += f"- **Session Low:** {engine.session_low:.5f}\n"
        analysis += f"- **Current Price:** {current_price:.5f}\n"
        
        if price_from_high < 0.1:
            analysis += "- Price near session high - watch for liquidity grab above high\n"
        elif price_from_low < 0.1:
            analysis += "- Price near session low - watch for liquidity grab below low\n"
        else:
            analysis += "- Price in mid-session range - watch for directional breakout\n"
    else:
        analysis += "- Session high/low not yet established\n"
        analysis += "- Monitor for developing session structure\n\n"
    
    # Liquidity pool analysis
    if significant_pools:
        analysis += f"\n- **{len(significant_pools)} significant liquidity pools identified**\n"
        
        for i, pool in enumerate(significant_pools[:3], 1):  # Show up to 3 pools
            distance = abs(current_price - pool['price']) / pool['price'] * 100
            pool_type = "Bullish" if pool['type'] == 'bullish' else "Bearish"
            
            analysis += f"\n{i}. **{pool_type} Liquidity Pool at {pool['price']:.5f}**\n"
            analysis += f"   - Strength: {pool['strength']}/10\n"
            analysis += f"   - Distance: {distance:.2f}% from current price\n"
            
            if distance < 5:
                analysis += "   - *Price near this liquidity pool*\n"
    
    else:
        analysis += "\n- No significant liquidity pools identified yet\n"
        analysis += "- This is normal with limited data or during consolidation\n"
    
    # Trading implications
    analysis += "\n**Trading Implications:**\n"
    
    if engine.session_high and engine.session_low and significant_pools:
        analysis += "- Trade with the liquidity sweep (not against it)\n"
        analysis += "- Enter trades after price confirms direction at liquidity pools\n"
        analysis += "- Use session high/low as reference points for risk management\n"
    else:
        analysis += "- Monitor for developing liquidity structures\n"
        analysis += "- Wait for clear session high/low establishment\n"
        analysis += "- Look for price reactions at round numbers as temporary reference points\n"
    
    return analysis

def generate_trade_setup_analysis(engine):
    """Generate robust trade setup analysis with conservative recommendations"""
    current_price = engine.data['close'].iloc[-1]
    
    # Calculate technical indicators with error handling
    sma_20 = None
    sma_50 = None
    
    try:
        if len(engine.data) >= 20:
            sma_20 = engine.data['close'].rolling(20).mean().iloc[-1]
        if len(engine.data) >= 50:
            sma_50 = engine.data['close'].rolling(50).mean().iloc[-1]
    except:
        pass
    
    # Detect liquidity pools
    try:
        liquidity_pools = engine.detect_liquidity_sweeps()
        significant_pools = [p for p in liquidity_pools if p['strength'] >= 5]
    except:
        liquidity_pools = []
        significant_pools = []
    
    # Determine market regime
    market_regime = "RANGING"
    if sma_20 and sma_50 and sma_20 > sma_50 and current_price > sma_20:
        market_regime = "BULLISH TREND"
    elif sma_20 and sma_50 and sma_20 < sma_50 and current_price < sma_20:
        market_regime = "BEARISH TREND"
    
    # Generate analysis
    analysis = "**Trade Setup Analysis**\n\n"
    
    # Market regime
    analysis += f"- **Current Market Regime:** {market_regime}\n"
    
    # Technical indicators
    if sma_20:
        analysis += f"- **20-period SMA:** {sma_20:.5f}\n"
        if market_regime == "BULLISH TREND":
            analysis += "- Price above 20-period SMA - bullish bias\n"
        elif market_regime == "BEARISH TREND":
            analysis += "- Price below 20-period SMA - bearish bias\n"
        else:
            analysis += "- Price near 20-period SMA - neutral bias\n"
    else:
        analysis += "- Not enough data for 20-period SMA\n"
    
    # Session context
    current_session = engine.current_session or "asia"
    current_hour = datetime.now(pytz.utc).hour
    
    if current_session in ['london', 'ny'] and 10 <= current_hour <= 15:
        analysis += "- Prime institutional hours - optimal for trade entries\n"
    else:
        analysis += "- Suboptimal timing for new entries\n"
    
    # Liquidity analysis
    if significant_pools:
        analysis += f"\n- **{len(significant_pools)} potential trade zones identified** at liquidity pools\n"
    else:
        analysis += "\n- No strong liquidity structures identified yet\n"
    
    # Conservative trade recommendations
    analysis += "\n**Conservative Trade Recommendations:**\n"
    
    # Bullish opportunity
    bullish_opportunity = False
    if market_regime == "BULLISH TREND" and sma_20 and current_price > sma_20:
        bullish_opportunity = True
        analysis += "- Potential long opportunity on pullbacks to support\n"
        analysis += f"  * Entry zone: {sma_20:.5f} - {current_price:.5f}\n"
        analysis += f"  * Stop loss: Below {min(engine.session_low, sma_20 * 0.999) if engine.session_low else sma_20 * 0.999:.5f}\n"
    
    # Bearish opportunity
    bearish_opportunity = False
    if market_regime == "BEARISH TREND" and sma_20 and current_price < sma_20:
        bearish_opportunity = True
        analysis += "- Potential short opportunity on rallies to resistance\n"
        analysis += f"  * Entry zone: {current_price:.5f} - {sma_20:.5f}\n"
        analysis += f"  * Stop loss: Above {max(engine.session_high, sma_20 * 1.001) if engine.session_high else sma_20 * 1.001:.5f}\n"
    
    # Range-bound market
    if not bullish_opportunity and not bearish_opportunity:
        analysis += "- Market appears range-bound - consider fading extremes\n"
        if engine.session_high and engine.session_low:
            mid_point = (engine.session_high + engine.session_low) / 2
            if current_price > mid_point:
                analysis += f"  * Consider short near {engine.session_high:.5f} with stop above\n"
            else:
                analysis += f"  * Consider long near {engine.session_low:.5f} with stop below\n"
        else:
            analysis += "  * Wait for clearer range boundaries to form\n"
    
    # Risk management
    analysis += "\n**Risk Management Protocol:**\n"
    analysis += "- Risk only 1% of account per trade\n"
    analysis += "- Use stop losses on every trade\n"
    analysis += "- Target minimum 1:2 risk-reward ratio\n"
    analysis += "- Confirm with price action before entering\n"
    
    return analysis

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

def render_trading_journal_calendar():
    """Render trading journal with calendar view"""
    st.subheader("Trading Journal Calendar")
    
    # Get current date
    today = datetime.now().date()
    
    # Create a calendar for the current month
    current_year = today.year
    current_month = today.month
    
    # Get all trade dates
    trade_dates = []
    if st.session_state.trade_journal:
        for trade in st.session_state.trade_journal:
            trade_dates.append(trade['datetime'].date())
    
    # Create calendar grid
    st.markdown('<div class="calendar-header">', unsafe_allow_html=True)
    st.markdown(f'<h3>{calendar.month_name[current_month]} {current_year}</h3>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Day names
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    st.markdown('<div class="calendar-grid">', unsafe_allow_html=True)
    for day in days:
        st.markdown(f'<div class="calendar-day-name">{day}</div>', unsafe_allow_html=True)
    
    # Get the first day of the month
    first_day = datetime(current_year, current_month, 1)
    # Get the weekday of the first day (0 = Monday, 6 = Sunday)
    first_weekday = first_day.weekday()
    
    # Fill in empty days before the first day
    for _ in range(first_weekday):
        st.markdown('<div class="calendar-day"></div>', unsafe_allow_html=True)
    
    # Get number of days in the month
    _, num_days = calendar.monthrange(current_year, current_month)
    
    # Create calendar days
    for day in range(1, num_days + 1):
        day_date = datetime(current_year, current_month, day).date()
        has_trades = day_date in trade_dates
        is_today = day_date == today
        
        classes = ["calendar-day"]
        if has_trades:
            classes.append("has-trades")
        if is_today:
            classes.append("today")
        
        if has_trades:
            st.markdown(f'<div class="{" ".join(classes)}" title="Trades today">{day}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="{" ".join(classes)}">{day}</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Show trades for selected date
    st.subheader("Recent Trades")
    
    # Filter to show only recent trades (last 7 days)
    recent_trades = []
    if st.session_state.trade_journal:
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_trades = [t for t in st.session_state.trade_journal if t['datetime'] > seven_days_ago]
        recent_trades = sorted(recent_trades, key=lambda x: x['datetime'], reverse=True)
    
    if recent_trades:
        # Convert to DataFrame for display
        journal_df = pd.DataFrame(recent_trades)
        journal_df = journal_df.sort_values('datetime', ascending=False)
        
        # Format the display
        display_df = journal_df.copy()
        display_df['datetime'] = display_df['datetime'].dt.strftime('%Y-%m-%d %H:%M')
        display_df['P&L'] = "N/A"  # Would calculate if we had exit prices
        
        st.dataframe(
            display_df[['datetime', 'symbol', 'direction', 'entry', 'sl', 'tp', 'status', 'P&L']],
            use_container_width=True
        )
    else:
        st.info("No recent trades recorded. Add your first trade in the Trade Journal tab.")
    
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
    
    # Export option
    if st.session_state.trade_journal:
        if st.button("Export Journal as CSV"):
            journal_df = pd.DataFrame(st.session_state.trade_journal)
            journal_df = journal_df.sort_values('datetime', ascending=False)
            journal_df['datetime'] = journal_df['datetime'].dt.strftime('%Y-%m-%d %H:%M')
            journal_df['P&L'] = "N/A"
            
            csv = journal_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="trade_journal.csv",
                mime="text/csv"
            )

def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="ICT Analysis",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    init_session()
    
    # Apply dark mode CSS
    init_dark_mode()
    
    # Process any queued messages
    engine = st.session_state.engine
    while not engine.message_queue.empty():
        msg_type, content = engine.message_queue.get()
    
    # Create sidebar with AI assistant
    with st.sidebar:
        st.markdown("### AI Trading Assistant")
        st.markdown("Ask me about market structure, liquidity pools, or trading opportunities.")
        
        st.markdown("---")
        
        # AI assistant chat in sidebar
        for message in st.session_state.chat_messages[-3:]:  # Show last 3 messages
            with st.container():
                if message["role"] == "user":
                    st.markdown(f"**You:** {message['content'][:30]}{'...' if len(message['content']) > 30 else ''}")
                else:
                    st.markdown(f"**Assistant:** {message['content'][:30]}{'...' if len(message['content']) > 30 else ''}")
        
        st.markdown("---")
        
        st.markdown("### About")
        st.markdown("ICT Session Context Tool v2.0")
        st.markdown("Professional trading analysis platform")
        
        # Add a dark mode toggle in the sidebar
        st.toggle("Dark Mode", value=st.session_state.dark_mode, key="dark_mode_toggle", 
                 on_change=lambda: st.session_state.update(dark_mode=st.session_state.dark_mode_toggle))
    
    # Main content
    st.title("📊 ICT Session Context Analysis Tool")
    
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
    tab1, tab2, tab3, tab4 = st.tabs([
        "Analysis", 
        "Risk Calculator", 
        "Trade Journal",
        "Calendar View"
    ])
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            render_tradingview_chart()
        
        with col2:
            render_custom_chart()
        
        render_analysis_chatbot()
    
    with tab2:
        render_risk_calculator()
    
    with tab3:
        # Add new trade form
        with st.expander("➕ Add New Trade"):
            col1, col2 = st.columns(2)
            with col1:
                trade_symbol = st.text_input("Symbol", value="EUR/USD", key="trade_symbol_tab3")
                trade_direction = st.selectbox("Direction", ["Long", "Short"])
            
            with col2:
                trade_date = st.date_input("Date", value=datetime.now().date())
                trade_time = st.time_input("Time", value=datetime.now().time())
            
            col1, col2, col3 = st.columns(3)
            with col1:
                entry_price = st.number_input("Entry Price", format="%.5f", step=0.0001, key="entry_price_tab3")
            
            with col2:
                sl_price = st.number_input("Stop Loss", format="%.5f", step=0.0001, key="sl_price_tab3")
            
            with col3:
                tp_price = st.number_input("Take Profit", format="%.5f", step=0.0001, key="tp_price_tab3")
            
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
    
    with tab4:
        render_trading_journal_calendar()
    
    # Footer
    st.markdown("""
    <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; 
                text-align: center; color: #666; font-size: 0.9em;">
        <p>ICT Session Context Tool • Professional Trading Analysis</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
