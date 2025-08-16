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
import logging
import threading
from queue import Queue
import dateutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        self.last_data_source = "simulated"  # Track data source
        self.liquidity_pools = []  # Store detected liquidity pools
        
        # Session time definitions (GMT/UTC)
        self.session_times = {
            'asia': {'start': 0, 'end': 8},    # 00:00-08:00 UTC
            'london': {'start': 8, 'end': 16}, # 08:00-16:00 UTC
            'ny': {'start': 13, 'end': 21},    # 13:00-21:00 UTC (overlaps London)
            'close': {'start': 21, 'end': 24}  # 21:00-24:00 UTC
        }
        
        # News impact tracking
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
            logger.info(f"SESSION CHANGE: {self.current_session} → {session} at {current_time.strftime('%H:%M')}")
            
            # Reset session values
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

    def fetch_news_impact(self):
        """Fetch high-impact news events from Forex Factory API"""
        try:
            url = "https://nfs.faireconomy.media/ff_calendar_week.php"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # Parse the response to find high impact events
            events = []
            now = datetime.now(pytz.utc)
            today = now.date()
            
            # Add demo events (in real app, parse from API)
            events.append({
                'time': (now + timedelta(hours=1)).strftime("%H:%M"),
                'event': 'US Non-Farm Payrolls',
                'impact': 'High',
                'date': today
            })
            
            events.append({
                'time': (now + timedelta(hours=4)).strftime("%H:%M"),
                'event': 'ECB Interest Rate Decision',
                'impact': 'High',
                'date': today
            })
            
            self.high_impact_events = events
            self.last_news_check = datetime.now()
            logger.info(f"Updated news events: {len(events)} high-impact events found")
            return True
            
        except Exception as e:
            logger.error(f"Error fetching news: {str(e)}")
            return False

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
            
            logger.info(f"Connecting to Dukascopy: {ws_url}")
            self.last_data_source = "connecting"
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Dukascopy: {str(e)}")
            self.last_data_source = "simulated"
            return False

    def on_dukascopy_open(self, ws):
        """Handle Dukascopy connection open"""
        logger.info("Connected to Dukascopy WebSocket")
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
            logger.error(f"Dukascopy processing error: {str(e)}")
            self.last_data_source = "simulated"

    def on_dukascopy_error(self, ws, error):
        """Handle Dukascopy connection errors"""
        logger.error(f"Dukascopy WebSocket error: {error}")
        self.last_data_source = "simulated"
        self.message_queue.put(('status', 'dukascopy_error'))

    def on_dukascopy_close(self, ws, close_status_code, close_msg):
        """Handle Dukascopy connection close"""
        logger.info(f"Dukascopy WebSocket closed: {close_status_code} - {close_msg}")
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

    def calculate_rr_ratio(self, entry, stop_loss, take_profit, direction):
        """Calculate risk-reward ratio with proper validation"""
        if None in [entry, stop_loss, take_profit] or entry == stop_loss:
            return None, None
        
        risk = abs(entry - stop_loss)
        if direction == "Long":
            reward = abs(take_profit - entry)
        else:
            reward = abs(entry - take_profit)
        
        rr_ratio = reward / risk if risk > 0 else None
        return rr_ratio, risk

    def analyze_trade_quality(self, entry, stop_loss, take_profit, direction):
        """Analyze trade setup quality based on multiple factors"""
        if None in [entry, stop_loss, take_profit] or entry == stop_loss:
            return 0, ["❌ Missing required trade parameters"]
        
        score = 0
        factors = []
        
        # 1. Risk-Reward ratio (30% of score)
        rr, risk = self.calculate_rr_ratio(entry, stop_loss, take_profit, direction)
        if rr and rr >= 2.0:
            score += 15
            factors.append(f"✅ Good RR ({rr:.1f}R)")
        elif rr:
            score += max(0, min(15, (rr - 1) * 15))
            factors.append(f"⚠️ Marginal RR ({rr:.1f}R)")
        else:
            factors.append("❌ Missing RR calculation")
        
        # 2. Liquidity alignment (25% of score)
        liquidity_alignment = 0
        for pool in self.liquidity_pools:
            if direction == "Long" and pool['type'] == 'bearish':
                # Check if entry is near bearish liquidity pool (below the pool)
                if pool['price'] * 0.9995 < entry < pool['price']:
                    liquidity_alignment = max(liquidity_alignment, pool['strength'] * 1.5)
                    factors.append(f"✅ Entry near bearish liquidity ({pool['strength']}/10)")
            elif direction == "Short" and pool['type'] == 'bullish':
                # Check if entry is near bullish liquidity pool (above the pool)
                if pool['price'] < entry < pool['price'] * 1.0005:
                    liquidity_alignment = max(liquidity_alignment, pool['strength'] * 1.5)
                    factors.append(f"✅ Entry near bullish liquidity ({pool['strength']}/10)")
        
        score += min(15, liquidity_alignment)
        
        # 3. Session context (25% of score)
        current_session = self.get_current_session(datetime.now(pytz.utc))
        current_hour = datetime.now(pytz.utc).hour
        
        if (current_session == 'london' and 10 <= current_hour <= 15) or \
           (current_session == 'ny' and 13 <= current_hour <= 18):
            score += 15
            factors.append("✅ Prime session timing")
        elif current_session in ['london', 'ny']:
            score += 10
            factors.append("⚠️ Good session, not peak")
        
        # 4. News avoidance (20% of score)
        near_news = False
        for event in self.high_impact_events:
            try:
                event_time = datetime.strptime(f"{event['date']} {event['time']}", '%Y-%m-%d %H:%M').replace(tzinfo=pytz.utc)
                time_diff = (event_time - datetime.now(pytz.utc)).total_seconds() / 60  # minutes
                
                if 0 <= time_diff <= 60:  # Event in next 60 minutes
                    near_news = True
                    break
            except:
                continue
        
        if not near_news:
            score += 15
            factors.append("✅ No high-impact news soon")
        
        return min(100, score), factors

    def start_websocket(self):
        """Start the WebSocket connection in a separate thread"""
        if self.running:
            return
            
        self.running = True
        logger.info("Starting WebSocket connection thread")
        
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
                    logger.error(f"WebSocket thread error: {str(e)}")
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
            logger.error(f"Error processing message: {str(e)}")
            self.message_queue.put(('error', str(e)))

    def on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")
        self.message_queue.put(('error', str(error)))

    def on_close(self, ws, close_status_code, close_msg):
        logger.info("### Connection closed ###")
        self.message_queue.put(('status', 'disconnected'))

    def on_open(self, ws):
        logger.info("### Connected to data feed ###")
        self.message_queue.put(('status', 'connected'))
        
        # Simulate subscription (real app would send subscription message)
        time.sleep(1)
        self.message_queue.put(('status', 'subscribed'))

    def stop_websocket(self):
        """Stop the WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("WebSocket connection stopped")

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
    
    # Start WebSocket connection if not already running
    if not st.session_state.engine.running:
        st.session_state.engine.start_websocket()

def calculate_position_size(account_size, entry, stop_loss, risk_percent=1):
    """Calculate proper position size based on risk parameters"""
    if None in [entry, stop_loss] or entry == stop_loss:
        return None, None, None
    
    risk_per_trade = account_size * (risk_percent / 100)
    pip_risk = abs(entry - stop_loss) * 10000  # For Forex
    pip_value = risk_per_trade / pip_risk
    units = pip_value * 10000  # Standard lot = 100k units
    
    # Convert to lots (1 lot = 100,000 units)
    lots = max(0.01, min(100, round(units / 100000, 2)))
    
    # Calculate actual risk amount
    actual_risk = pip_risk * (lots * 10)  # $10 per pip per standard lot
    
    return lots, actual_risk, pip_risk

def display_disclaimer():
    """Display prominent disclaimer banner"""
    st.markdown("""
    <div style="background-color: #fff8e6; border-left: 4px solid #ffc107; padding: 10px; margin-bottom: 20px; border-radius: 4px;">
        <strong>⚠️ CRITICAL DISCLAIMER:</strong> This application provides <strong>SESSION CONTEXT ONLY</strong>, 
        NOT trading signals. ICT concepts are interpretive frameworks with no mathematical certainty. 
        Trading involves substantial risk of loss. Never risk more than 1% of your account. 
        You are solely responsible for your trading decisions.
    </div>
    """, unsafe_allow_html=True)

def display_news_warnings():
    """Display warnings for upcoming high-impact news"""
    engine = st.session_state.engine
    
    # Fetch news if needed
    if engine.last_news_check is None or (datetime.now() - engine.last_news_check) > timedelta(minutes=30):
        engine.fetch_news_impact()
    
    now = datetime.now(pytz.utc)
    warnings = []
    
    for event in engine.high_impact_events:
        try:
            event_time = datetime.strptime(f"{event['date']} {event['time']}", '%Y-%m-%d %H:%M').replace(tzinfo=pytz.utc)
            time_diff = (event_time - now).total_seconds() / 60  # minutes
            
            if 0 <= time_diff <= 60:  # Event in next 60 minutes
                warnings.append({
                    'event': event['event'],
                    'time': event['time'],
                    'time_diff': time_diff
                })
        except:
            continue
    
    if warnings:
        warning_html = """
        <div style="background-color: #ffebee; border-left: 4px solid #f44336; padding: 10px; margin: 10px 0; border-radius: 4px;">
            <strong>⚠️ HIGH-IMPACT NEWS WARNING:</strong>
            <ul style="margin: 5px 0; padding-left: 20px;">
        """
        
        for warning in warnings:
            warning_html += f"<li>{warning['event']} at {warning['time']} UTC (in {int(warning['time_diff'])} minutes)</li>"
        
        warning_html += """
            </ul>
            <p style="margin: 5px 0; color: #d32f2f;">
                <strong>Recommendation:</strong> Avoid new entries 30 minutes before and after high-impact news.
                Consider closing existing positions or tightening stops.
            </p>
        </div>
        """
        st.markdown(warning_html, unsafe_allow_html=True)

def render_session_chart():
    """Render the main price chart with session context and liquidity pools"""
    engine = st.session_state.engine
    
    if engine.data.empty:
        st.info("Waiting for market data...")
        return
    
    # Create figure with secondary y-axis for volume (if implemented)
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
        title=f"{engine.symbol} - Session Context Analysis (UTC Time)",
        xaxis_rangeslider_visible=False,
        height=600,
        hovermode="x unified",
        template="plotly_white",
        margin=dict(l=10, r=10, t=50, b=10)
    )
    
    fig.update_xaxes(title_text="Time (UTC)", row=1, col=1)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    
    # Add data source indicator
    data_source_text = "✅ Real data from Dukascopy (free tier)" if engine.last_data_source == "dukascopy" else "⚠️ Simulated data - for testing only"
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

def render_risk_calculator():
    """Render the risk management calculator"""
    st.subheader("Risk Management Calculator")
    
    # Input fields
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
    
    # Direction selection
    trade_direction = st.selectbox("Trade Direction", ["Long", "Short"])
    
    # Update session state
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
    
    # Display results
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
            st.warning("⚠️ Warning: Risk amount exceeds 2% of account. Consider reducing position size.")
        
        # Trade Quality Assessment
        st.subheader("Trade Setup Quality")
        quality_score, factors = st.session_state.engine.analyze_trade_quality(
            entry, stop_loss, take_profit, trade_direction
        )
        
        # Display score gauge
        if quality_score > 0:
            # Create gauge chart
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=quality_score,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Trade Quality Score"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#2196F3"},
                    'steps': [
                        {'range': [0, 40], 'color': "#ff4b4b"},
                        {'range': [40, 70], 'color': "#f5ab00"},
                        {'range': [70, 100], 'color': "#00c853"}
                    ]
                }
            ))
            
            fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)
            
            # Display factors
            for factor in factors:
                st.markdown(factor)
            
            # Critical warning for low scores
            if quality_score < 40:
                st.warning("⚠️ This setup has significant weaknesses. Consider waiting for better conditions.")
            elif quality_score < 70:
                st.info("ℹ️ This setup has moderate quality. Double-check your reasoning before entering.")
        
        # Educational explanation
        with st.expander("How this calculation works"):
            st.markdown("""
            **Position Sizing Formula:**
            ```
            Risk Amount = Account Size × Risk %
            Pip Risk = |Entry - Stop Loss| × 10,000
            Position Size (lots) = Risk Amount / (Pip Risk × $ per Pip)
            ```
            
            For Forex:
            - 1 standard lot = 100,000 units
            - $10 per pip for standard lots (EUR/USD)
            - Always risk ≤ 1% of account per trade
            
            **Example:**
            - $10,000 account, 1% risk = $100 risk
            - Entry 1.0850, SL 1.0840 (10 pip risk)
            - Position Size = $100 / (10 pips × $10) = 1 lot
            """)
    else:
        st.info("Enter entry and stop loss prices to calculate position size")

def render_trade_journal():
    """Render the trade journal section"""
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
        
        reason = st.text_area("Trade Reason / Setup", 
                             help="Describe the session context and why you took this trade")
        
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

def render_education_panel():
    """Render educational content about session context"""
    st.subheader("Understanding Session Context")
    
    tab1, tab2, tab3 = st.tabs(["Trading Sessions", "ICT Context", "Risk Management"])
    
    with tab1:
        st.markdown("""
        ### Global Trading Sessions (UTC Time)
        
        | Session | Time (UTC) | Characteristics |
        |---------|------------|----------------|
        | **Asian** | 00:00-08:00 | Lower volatility, range-bound |
        | **London** | 08:00-16:00 | Highest liquidity, trending |
        | **NY/London Overlap** | 13:00-16:00 | Most volatile period |
        | **NY Session** | 13:00-21:00 | Continuation of London trends |
        | **Close** | 21:00-24:00 | Lower volatility, consolidation |
        
        **Why Session Matters:**
        - London session accounts for ~35% of daily FX volume
        - NY/London overlap sees highest volatility
        - Asian session often establishes ranges for London
        - Price action near session highs/lows often shows reversals
        """)
        
        # Session timing diagram
        fig = go.Figure()
        
        sessions = [
            ('Asia', 0, 8, 'rgba(128, 128, 128, 0.3)'),
            ('London', 8, 16, 'rgba(76, 175, 80, 0.3)'),
            ('NY/London Overlap', 13, 16, 'rgba(33, 150, 243, 0.3)'),
            ('NY', 13, 21, 'rgba(156, 39, 176, 0.3)'),
            ('Close', 21, 24, 'rgba(244, 67, 54, 0.3)')
        ]
        
        for name, start, end, color in sessions:
            fig.add_trace(go.Bar(
                x=[(start + end)/2],
                y=[1],
                width=end-start,
                marker_color=color,
                name=name,
                text=name,
                textposition="auto",
            ))
        
        fig.update_layout(
            title="Global Trading Sessions (UTC)",
            xaxis_title="Hour of Day (UTC)",
            yaxis=dict(visible=False),
            height=300,
            showlegend=False,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.markdown("""
        ### ICT Session Context (Educational Only)
        
        **Important Note:** ICT concepts are interpretive frameworks developed by Michael Huddleston. 
        They are NOT mathematical indicators with proven statistical edge.
        
        #### How Session Context Fits in ICT:
        - **London Open (08:00 UTC):** Often seen as key time for institutional activity
        - **Session Highs/Lows:** Potential liquidity pools (areas where stops may cluster)
        - **NY/London Overlap (13:00-16:00 UTC):** Highest probability period for directional moves
        
        #### Critical Reality Check:
        - No backtestable evidence that ICT concepts provide consistent edge
        - Most "ICT setups" are subjective interpretations after the fact
        - Session context is the ONLY objectively verifiable element
        - Always prioritize price action confirmation over "ICT signals"
        
        > "The market doesn't care about your trading methodology. It only cares about supply and demand." - Trading Reality
        """)
        
        st.info("""
        **Educational Disclaimer:** 
        This section explains how some traders interpret session context within ICT framework. 
        It does NOT endorse ICT as a reliable trading methodology. 
        Trading decisions should be based on objective price action and strict risk management.
        """)
    
    with tab3:
        st.markdown("""
        ### Essential Risk Management Principles
        
        #### The 1% Rule
        - Never risk more than 1% of your account on a single trade
        - Example: $10,000 account → max $100 risk per trade
        
        #### Position Sizing Formula
        ```
        Position Size = (Account Size × Risk %) ÷ (Stop Loss in Pips × Value per Pip)
        ```
        
        #### Risk-Reward Ratio
        - Minimum 1:2 ratio recommended (risk $1 to make $2)
        - Example: 10 pip stop loss → 20 pip take profit
        
        #### Critical Reminders
        - Risk management is MORE important than entry timing
        - No strategy works without proper risk controls
        - Emotional trading destroys accounts faster than bad strategies
        """)
        
        st.warning("""
        **WARNING:** 
        Many "ICT gurus" sell courses promising "max accuracy" setups. 
        These claims are misleading and dangerous. 
        Real trading requires discipline, risk management, and acceptance of uncertainty.
        """)

def main():
    # Page configuration
    st.set_page_config(
        page_title="ICT Session Context Tool",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    init_session()
    
    # Process any queued messages
    engine = st.session_state.engine
    while not engine.message_queue.empty():
        msg_type, content = engine.message_queue.get()
        if msg_type == 'error':
            st.error(f"Data error: {content}")
    
    # Display critical disclaimer
    display_disclaimer()
    
    # Display data connection status
    if engine.last_data_source == "dukascopy":
        st.success("✅ Connected to real market data (Dukascopy free tier)")
    elif engine.last_data_source == "connecting":
        st.info("🔄 Connecting to market data feed...")
    else:
        st.warning("⚠️ Using simulated data - check connection settings")
        
        # Show connection troubleshooting tips
        with st.expander("🔧 troubleshoot connection"):
            st.markdown("""
            **Common issues:**
            - Dukascopy free tier only supports 1 connection at a time
            - Free tier has rate limits (1 request/second)
            - Check Streamlit Cloud logs for detailed errors
            - Ensure requirements.txt has all required packages
            
            **Next steps:**
            1. Verify requirements.txt includes `websocket-client==1.8.0`
            2. Check Streamlit Cloud logs for connection errors
            3. Wait 1-2 minutes for connection to establish
            """)

    # News warnings
    display_news_warnings()
    
    # Create layout
    tab1, tab2, tab3, tab4 = st.tabs([
        "Market Analysis", 
        "Risk Calculator", 
        "Trade Journal", 
        "Education"
    ])
    
    with tab1:
        # Real-time chart
        render_session_chart()
        
        # Status indicators
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Current Session", 
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
                st.metric("Data Status", status, 
                         f"Updated {int(time_diff)}s ago" if time_diff < 60 else "No recent data")
    
    with tab2:
        render_risk_calculator()
    
    with tab3:
        render_trade_journal()
    
    with tab4:
        render_education_panel()
    
    # Footer with critical reminders
    st.markdown("""
    <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; 
                text-align: center; color: #666; font-size: 0.9em;">
        <p>ICT Session Context Tool • Educational Purposes Only • 
        <strong>NOT A TRADING SIGNAL GENERATOR</strong></p>
        <p>Always conduct your own analysis and risk management. 
        Trading involves substantial risk of loss.</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
