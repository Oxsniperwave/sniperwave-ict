import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from openai import OpenAI
import requests
import json
import websocket
import threading
from queue import Queue
import pytz
from datetime import datetime

# Initialize session state
if 'engine' not in st.session_state:
    st.session_state.engine = TradingEngine()
if 'analysis' not in st.session_state:
    st.session_state.analysis = None
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

# Dark mode CSS
def init_dark_mode():
    dark_mode = st.session_state.dark_mode
    st.markdown(f"""
        <style>
            .stApp {{ background-color: {'#121212' if dark_mode else '#ffffff'}; color: {'#e0e0e0' if dark_mode else '#333333'}; }}
            .stButton > button {{ background-color: {'#4a90e2' if dark_mode else '#007bff'}; color: white; }}
            .stMetric {{ background-color: {'#1e1e1e' if dark_mode else '#f8f9fa'}; border-radius: 8px; padding: 10px; }}
        </style>
    """, unsafe_allow_html=True)

class TradingEngine:
    def __init__(self):
        self.symbol = "EUR/USD"
        self.timezone = pytz.timezone('UTC')
        self.data = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close'])
        self.ws = None
        self.message_queue = Queue()
        self.running = False
        self.last_update = None
        self.client = OpenAI(api_key="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")

    def connect_to_dukascopy(self):
        ws_url = f"wss://quotes.dukascopy.com/feed/{self.symbol.replace('/', '')}/m1/last/100"
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()
        return True

    def on_open(self, ws):
        self.message_queue.put(('status', 'connected'))

    def on_message(self, ws, message):
        data = json.loads(message)
        new_candle = {
            'timestamp': datetime.fromtimestamp(data['t']/1000, tz=self.timezone),
            'open': data['o'], 'high': data['h'], 'low': data['l'], 'close': data['c']
        }
        self.data = pd.concat([self.data, pd.DataFrame([new_candle])], ignore_index=True).iloc[-1000:]
        self.last_update = new_candle['timestamp']
        self.message_queue.put(('update', new_candle))
        if (datetime.now(self.timezone) - self.last_update).total_seconds() > 600:
            analysis = self.generate_analysis(self.data)
            self.message_queue.put(('analysis', analysis))

    def on_error(self, ws, error):
        self.message_queue.put(('status', 'error'))
        self.fallback_to_coingecko()

    def on_close(self, ws, close_status_code, close_msg):
        self.message_queue.put(('status', 'disconnected'))

    def fallback_to_coingecko(self):
        url = f"https://api.coingecko.com/api/v3/coins/{self.symbol.replace('/', '-').lower()}/market_chart?vs_currency=usd&days=1"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            cg_data = pd.DataFrame(response.json()['prices'], columns=['timestamp', 'close'])
            cg_data['timestamp'] = pd.to_datetime(cg_data['timestamp'], unit='ms', utc=True)
            cg_data['open'] = cg_data['close']
            cg_data['high'] = cg_data['close']
            cg_data['low'] = cg_data['close']
            self.data = cg_data
            self.last_update = datetime.now(self.timezone)
            self.message_queue.put(('update', self.data.iloc[-1]))

    def generate_analysis(self, data_to_analyze):
        """Generate ICT analysis using OpenAI API"""
        prompt = f"Analyze this {self.symbol} trading data for ICT patterns: {json.dumps(data_to_analyze.to_dict(orient='records')[-20:])}. Return a JSON object with market_structure, order_blocks, liquidity_sweeps, trading_signals, and risk_management_advice."
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Use gpt-4o for best results
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7
            )
            result = response.choices[0].message.content
            return json.loads(result) if result.startswith('{') else {"analysis": result}
        except Exception as e:
            print(f"❌ Error calling OpenAI API: {str(e)}")
            return {"error": str(e), "analysis": "Failed to generate report."}

    def start(self):
        if not self.running:
            self.running = True
            self.connect_to_dukascopy()

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()

# Main app
def main():
    init_dark_mode()
    st.title("ICT Trading Analyzer")
    engine = st.session_state.engine

    # Controls
    col1, col2 = st.columns(2)
    with col1:
        symbol = st.selectbox("Symbol", ["EUR/USD", "BTC/USD"], key="symbol")
        if symbol != engine.symbol:
            engine.symbol = symbol
            engine.data = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close'])
            engine.start()
    with col2:
        st.session_state.dark_mode = st.toggle("Dark Mode", value=st.session_state.dark_mode)

    # Start engine
    if not engine.running:
        engine.start()

    # Display data
    st.subheader("Market Data")
    if engine.last_update:
        st.metric("Last Update", engine.last_update.astimezone(pytz.timezone('Europe/Berlin')).strftime("%H:%M:%S"))
    else:
        st.info("Connecting...")

    # Chart
    st.subheader("Price Chart")
    fig = go.Figure(data=[go.Candlestick(x=engine.data['timestamp'],
                                         open=engine.data['open'],
                                         high=engine.data['high'],
                                         low=engine.data['low'],
                                         close=engine.data['close'])])
    st.plotly_chart(fig, use_container_width=True)

    # Analysis
    st.subheader("OpenAI Analysis")
    if st.session_state.analysis and 'analysis' in st.session_state.analysis:
        st.json(st.session_state.analysis)
    elif 'error' in st.session_state.analysis:
        st.error(st.session_state.analysis['error'])

    # Process queue
    while not engine.message_queue.empty():
        msg_type, msg = engine.message_queue.get()
        if msg_type == 'update':
            st.experimental_rerun()
        elif msg_type == 'analysis':
            st.session_state.analysis = msg

if __name__ == "__main__":
    main()
