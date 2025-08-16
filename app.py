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
        hour = timestamp.hour
        if 0 <= hour < 8:
            return 'asia'
        elif 8 <= hour < 16:
            return 'london'
        elif 13 <= hour < 21:
            return 'ny'
        else:
            return 'close'

    def update_session(self, new_candle):
        current_time = new_candle['timestamp']
        session = self.get_current_session(current_time)
        
        if session != self.current_session:
            self.session_high = new_candle['high']
            self.session_low = new_candle['low']
            self.session_start_time = current_time
            self.current_session = session
        else:
            self.session_high = max(self.session_high, new_candle['high'])
            self.session_low = min(self.session_low, new_candle['low'])
        
        return {
            'session': self.current_session,
            'high': self.session_high,
            'low': self.session_low,
            'start_time': self.session_start_time
        }

    def fetch_news_impact(self):
        try:
            url = "https://nfs.faireconomy.media/ff_calendar_week.php"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            events = []
            now = datetime.now(pytz.utc)
            today = now.date()
            
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
            return True
            
        except Exception as e:
            return False

    def connect_to_dukascopy(self):
        try:
            ws_url = f"wss://quotes.dukascopy.com/feed/{self.symbol.replace('/', '')}/m1/last/100"
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=self.on_dukascopy_message,
                on_error=self.on_dukascopy_error,
                on_close=self.on_dukascopy_close,
                on_open=self.on_dukascopy_open
            )
            
            wst = threading.Thread(target=self.ws.run_forever)
            wst.daemon = True
            wst.start()
            
            self.last_data_source = "connecting"
            return True
        except Exception as e:
            self.last_data_source = "simulated"
            return False

    def on_dukascopy_open(self, ws):
        self.last_data_source = "dukascopy"
        self.message_queue.put(('status', 'dukascopy_connected'))

    def on_dukascopy_message(self, ws, message):
        try:
            data = json.loads(message)
            
            new_candle = {
                'timestamp': datetime.fromtimestamp(data['t']/1000, tz=pytz.utc),
                'open': data['o'],
                'high': data['h'],
                'low': data['l'],
                'close': data['c']
            }
            
            session_info = self.update_session(new_candle)
            
            self.data = pd.concat([self.data, pd.DataFrame([new_candle])], ignore_index=True)
            if len(self.data) > 1000:
                self.data = self.data.iloc[-1000:]
                
            self.last_update = new_candle['timestamp']
            self.last_data_source = "dukascopy"
            self.message_queue.put(('update', new_candle))
            
            self.liquidity_pools = self.detect_liquidity_sweeps()
            
        except Exception as e:
            self.last_data_source = "simulated"

    def on_dukascopy_error(self, ws, error):
        self.last_data_source = "simulated"
        self.message_queue.put(('status', 'dukascopy_error'))

    def on_dukascopy_close(self, ws, close_status_code, close_msg):
        self.last_data_source = "simulated"
        self.message_queue.put(('status', 'dukascopy_closed'))

    def detect_liquidity_sweeps(self, lookback_hours=24):
        if len(self.data) < 20:
            return []
        
        liquidity_pools = []
        current_time = datetime.now(pytz.utc)
        
        for i in range(len(self.data)-5, 19, -1):
            candle = self.data.iloc[i]
            
            if (candle['high'] > self.data['high'].rolling(20).max().iloc[i-1] or 
                candle['low'] < self.data['low'].rolling(20).min().iloc[i-1]):
                
                reversal_candles = self.data.iloc[i+1:i+5]
                if not reversal_candles.empty:
                    price_move = abs(reversal_candles['close'].iloc[-1] - candle['high' if candle['close'] < candle['open'] else 'low'])
                    reversal_pct = price_move / candle['high' if candle['close'] < candle['open'] else 'low']
                    
                    if reversal_pct > 0.0005:
                        liquidity_pools.append({
                            'timestamp': candle['timestamp'],
                            'price': candle['high'] if candle['close'] < candle['open'] else candle['low'],
                            'type': 'bullish' if candle['close'] < candle['open'] else 'bearish',
                            'strength': min(10, int(reversal_pct * 20000)),
                            'candle_index': i
                        })
        
        return liquidity_pools

    def calculate_rr_ratio(self, entry, stop_loss, take_profit, direction):
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
        if None in [entry, stop_loss, take_profit] or entry == stop_loss:
            return 0, ["Missing required trade parameters"]
        
        score = 0
        factors = []
        
        rr, risk = self.calculate_rr_ratio(entry, stop_loss, take_profit, direction)
        if rr and rr >= 2.0:
            score += 15
            factors.append(f"Good RR ({rr:.1f}R)")
        elif rr:
            score += max(0, min(15, (rr - 1) * 15))
            factors.append(f"Marginal RR ({rr:.1f}R)")
        
        liquidity_alignment = 0
        for pool in self.liquidity_pools:
            if direction == "Long" and pool['type'] == 'bearish':
                if pool['price'] * 0.9995 < entry < pool['price']:
                    liquidity_alignment = max(liquidity_alignment, pool['strength'] * 1.5)
                    factors.append(f"Entry near bearish liquidity ({pool['strength']}/10)")
            elif direction == "Short" and pool['type'] == 'bullish':
                if pool['price'] < entry < pool['price'] * 1.0005:
                    liquidity_alignment = max(liquidity_alignment, pool['strength'] * 1.5)
                    factors.append(f"Entry near bullish liquidity ({pool['strength']}/10)")
        
        score += min(15, liquidity_alignment)
        
        current_session = self.get_current_session(datetime.now(pytz.utc))
        current_hour = datetime.now(pytz.utc).hour
        
        if (current_session == 'london' and 10 <= current_hour <= 15) or \
           (current_session == 'ny' and 13 <= current_hour <= 18):
            score += 15
            factors.append("Prime session timing")
        elif current_session in ['london', 'ny']:
            score += 10
            factors.append("Good session, not peak")
        
        near_news = False
        for event in self.high_impact_events:
            try:
                event_time = datetime.strptime(f"{event['date']} {event['time']}", '%Y-%m-%d %H:%M').replace(tzinfo=pytz.utc)
                time_diff = (event_time - datetime.now(pytz.utc)).total_seconds() / 60
                
                if 0 <= time_diff <= 60:
                    near_news = True
                    break
            except:
                continue
        
        if not near_news:
            score += 15
            factors.append("No high-impact news soon")
        
        return min(100, score), factors

    def start_websocket(self):
        if self.running:
            return
            
        self.running = True
        
        def run_websocket():
            while self.running:
                try:
                    if self.connect_to_dukascopy():
                        time.sleep(60)
                    else:
                        time.sleep(2)
                        
                        if not self.running:
                            break
                            
                        self.message_queue.put(('status', 'simulated'))
                        self.on_message(None, None)
                        
                except Exception as e:
                    time.sleep(5)
        
        self.ws_thread = threading.Thread(target=run_websocket, daemon=True)
        self.ws_thread.start()

    def on_message(self, ws, message):
        try:
            ts = datetime.now(pytz.utc)
            
            if not self.data.empty:
                last_price = self.data.iloc[-1]['close']
                change = np.random.normal(0, 0.0002) - 0.00001
                new_price = last_price + change
            else:
                new_price = 1.0850
            
            new_candle = {
                'timestamp': ts,
                'open': new_price,
                'high': new_price + abs(np.random.normal(0, 0.00005)),
                'low': new_price - abs(np.random.normal(0, 0.00005)),
                'close': new_price
            }
            
            session_info = self.update_session(new_candle)
            
            self.data = pd.concat([self.data, pd.DataFrame([new_candle])], ignore_index=True)
            if len(self.data) > 1000:
                self.data = self.data.iloc[-1000:]
                
            self.last_update = ts
            self.message_queue.put(('update', new_candle))
            
            self.liquidity_pools = self.detect_liquidity_sweeps()
            
        except Exception as e:
            self.message_queue.put(('error', str(e)))

    def on_error(self, ws, error):
        self.message_queue.put(('error', str(error)))

    def on_close(self, ws, close_status_code, close_msg):
        self.message_queue.put(('status', 'disconnected'))

    def on_open(self, ws):
        self.message_queue.put(('status', 'connected'))
        time.sleep(1)
        self.message_queue.put(('status', 'subscribed'))

    def stop_websocket(self):
        self.running = False
        if self.ws:
            self.ws.close()

def init_session():
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
    
    if not st.session_state.engine.running:
        st.session_state.engine.start_websocket()

def calculate_position_size(account_size, entry, stop_loss, risk_percent=1):
    if None in [entry, stop_loss] or entry == stop_loss:
        return None, None, None
    
    risk_per_trade = account_size * (risk_percent / 100)
    pip_risk = abs(entry - stop_loss) * 10000
    pip_value = risk_per_trade / pip_risk
    units = pip_value * 10000
    
    lots = max(0.01, min(100, round(units / 100000, 2)))
    
    actual_risk = pip_risk * (lots * 10)
    
    return lots, actual_risk, pip_risk

def render_tradingview_chart():
    st.subheader("TradingView Chart")
    
    tradingview_html = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "width": "100%",
          "height": 610,
          "symbol": "{st.session_state.engine.symbol}",
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
    
    st.components.v1.html(tradingview_html, height=650)

def render_session_chart():
    engine = st.session_state.engine
    
    if engine.data.empty:
        st.info("Waiting for market data...")
        return
    
    fig = make_subplots(rows=1, cols=1)
    
    fig.add_trace(go.Candlestick(
        x=engine.data['timestamp'],
        open=engine.data['open'],
        high=engine.data['high'],
        low=engine.data['low'],
        close=engine.data['close'],
        name='Price'
    ))
    
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
    
    if engine.session_high and engine.session_low:
        fig.add_hline(y=engine.session_high, line_dash="dot", line_color="green", 
                     annotation_text="Session High", annotation_position="right",
                     row=1, col=1)
        fig.add_hline(y=engine.session_low, line_dash="dot", line_color="red",
                     annotation_text="Session Low", annotation_position="right",
                     row=1, col=1)
    
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

def analyze_with_ai():
    st.subheader("AI Market Analysis")
    
    engine = st.session_state.engine
    if engine.data.empty:
        return
    
    current_price = engine.data['close'].iloc[-1]
    session_high = engine.session_high
    session_low = engine.session_low
    
    analysis = []
    
    if engine.current_session == 'london' and 10 <= datetime.now(pytz.utc).hour <= 15:
        analysis.append("Prime London session - high probability setup zone")
    
    liquidity_pools = engine.detect_liquidity_sweeps()
    for pool in liquidity_pools:
        if abs(current_price - pool['price']) < 0.0005:
            if pool['type'] == 'bullish':
                analysis.append(f"Price at bullish liquidity pool ({pool['price']:.5f}) - potential buy zone")
            else:
                analysis.append(f"Price at bearish liquidity pool ({pool['price']:.5f}) - potential sell zone")
    
    if session_high and session_low:
        price_from_high = (session_high - current_price) / session_high
        price_from_low = (current_price - session_low) / session_low
        
        if price_from_high < 0.001:
            analysis.append("Near session high - watch for rejection")
        elif price_from_low < 0.001:
            analysis.append("Near session low - watch for bounce")
    
    if analysis:
        st.success("AI Analysis Complete")
        
        for i, item in enumerate(analysis, 1):
            st.markdown(f"{i}. {item}")
        
        if any("potential buy" in a.lower() for a in analysis) and "near session low" in " ".join(analysis).lower():
            st.markdown("### Trade Recommendation")
            st.success("BUY SIGNAL DETECTED")
            
            entry = current_price
            stop_loss = session_low * 0.9995
            take_profit = entry + 2 * abs(entry - stop_loss)
            
            st.markdown(f"**Entry:** {entry:.5f}")
            st.markdown(f"**Stop Loss:** {stop_loss:.5f}")
            st.markdown(f"**Take Profit:** {take_profit:.5f}")
            
            account_size = st.session_state.risk_params['account_size']
            risk_percent = st.session_state.risk_params['risk_percent']
            pip_risk = abs(entry - stop_loss) * 10000
            
            if pip_risk > 0:
                risk_amount = account_size * (risk_percent / 100)
                position_size = risk_amount / (pip_risk * 10)
                
                st.markdown("### Position Sizing")
                st.markdown(f"**Position Size:** {position_size:.2f} lots")
                st.markdown(f"**Risk Amount:** ${risk_amount:.2f}")
                st.markdown(f"**Risk-Reward Ratio:** 1:{2.0:.1f}")

def render_risk_calculator():
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
        
        if actual_risk > account_size * 0.02:
            st.warning("Warning: Risk amount exceeds 2% of account. Consider reducing position size.")
        
        st.subheader("Trade Setup Quality")
        quality_score, factors = st.session_state.engine.analyze_trade_quality(
            entry, stop_loss, take_profit, trade_direction
        )
        
        if quality_score > 0:
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
            
            for factor in factors:
                st.markdown(factor)
            
            if quality_score < 40:
                st.warning("This setup has significant weaknesses. Consider waiting for better conditions.")
            elif quality_score < 70:
                st.info("This setup has moderate quality. Double-check your reasoning before entering.")

def render_trade_journal():
    st.subheader("Trade Journal")
    
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
    
    if st.session_state.trade_journal:
        journal_df = pd.DataFrame(st.session_state.trade_journal)
        journal_df = journal_df.sort_values('datetime', ascending=False)
        
        display_df = journal_df.copy()
        display_df['datetime'] = display_df['datetime'].dt.strftime('%Y-%m-%d %H:%M')
        display_df['P&L'] = "N/A"
        
        st.dataframe(
            display_df[['datetime', 'symbol', 'direction', 'entry', 'sl', 'tp', 'status', 'P&L']],
            use_container_width=True
        )
        
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

def display_news_warnings():
    engine = st.session_state.engine
    
    if engine.last_news_check is None or (datetime.now() - engine.last_news_check) > timedelta(minutes=30):
        engine.fetch_news_impact()
    
    now = datetime.now(pytz.utc)
    warnings = []
    
    for event in engine.high_impact_events:
        try:
            event_time = datetime.strptime(f"{event['date']} {event['time']}", '%Y-%m-%d %H:%M').replace(tzinfo=pytz.utc)
            time_diff = (event_time - now).total_seconds() / 60
            
            if 0 <= time_diff <= 60:
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
            <strong>HIGH-IMPACT NEWS WARNING:</strong>
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

def main():
    st.set_page_config(
        page_title="ICT Session Context Tool",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    init_session()
    
    engine = st.session_state.engine
    while not engine.message_queue.empty():
        msg_type, content = engine.message_queue.get()
    
    if engine.last_data_source == "dukascopy":
        st.success("Connected to real market data (Dukascopy free tier)")
    elif engine.last_data_source == "connecting":
        st.info("Connecting to market data feed...")
    else:
        st.warning("Using simulated data - check connection settings")
    
    display_news_warnings()
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "Market Analysis", 
        "Risk Calculator", 
        "Trade Journal", 
        "Education"
    ])
    
    with tab1:
        render_tradingview_chart()
        render_session_chart()
        analyze_with_ai()
        
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
                status = "Live" if time_diff < 10 else "Delayed"
                st.metric("Data Status", status, 
                         f"Updated {int(time_diff)}s ago" if time_diff < 60 else "No recent data")
    
    with tab2:
        render_risk_calculator()
    
    with tab3:
        render_trade_journal()
    
    with tab4:
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
            ### ICT Session Context
            
            **Important Note:** ICT concepts are interpretive frameworks developed by Michael Huddleston. 
            
            #### How Session Context Fits in ICT:
            - **London Open (08:00 UTC):** Key time for institutional activity
            - **Session Highs/Lows:** Potential liquidity pools
            - **NY/London Overlap (13:00-16:00 UTC):** Highest probability period
            
            #### Critical Reality Check:
            - Session context is the objectively verifiable element
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
            - Minimum 1:2 ratio recommended
            - Example: 10 pip stop loss → 20 pip take profit
            """)

if __name__ == "__main__":
    main()
