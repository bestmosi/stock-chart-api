"""
📊 Stock Chart API for ChatGPT Integration
Flask API service for generating stock charts on-demand
"""

import os
import io
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import mplfinance as mpf
import requests

# ================== Configuration ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for ChatGPT access

# Chart storage directory
CHARTS_DIR = "generated_charts"
os.makedirs(CHARTS_DIR, exist_ok=True)


# ================== Chart Style ==================
CHART_STYLE = mpf.make_mpf_style(
    base_mpf_style="classic",
    facecolor="white",
    edgecolor="black",
    gridcolor="#e6e6e6",
    gridstyle="--",
    figcolor="white",
    rc={
        "axes.labelsize": 10,
        "axes.titlesize": 12,
        "font.size": 9,
    },
    marketcolors=mpf.make_marketcolors(
        up="#26a69a",
        down="#ef5350",
        wick="black",
        edge="inherit",
        volume="inherit"
    )
)


# ================== Helper Functions ==================
def fetch_stock_data(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV data from Yahoo Finance
    
    Args:
        ticker: Stock symbol
        period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 5y, max)
        interval: Data interval (1m, 5m, 15m, 1h, 1d, 1wk, 1mo)
    
    Returns:
        DataFrame with OHLCV data
    """
    ticker = ticker.strip().upper()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    
    params = {
        "range": period,
        "interval": interval,
        "includePrePost": "false",
        "useYfid": "true",
        "includeAdjustedClose": "true"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        
        df = pd.DataFrame({
            "Open": quote["open"],
            "High": quote["high"],
            "Low": quote["low"],
            "Close": quote["close"],
            "Volume": quote["volume"],
        })
        
        df.index = pd.to_datetime([datetime.fromtimestamp(ts) for ts in timestamps])
        df = df.dropna()
        
        if df.empty:
            raise ValueError(f"No data available for {ticker}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        raise


def generate_chart_image(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    moving_averages: tuple = (20, 50),
    show_volume: bool = True
) -> io.BytesIO:
    """
    Generate candlestick chart and return as BytesIO
    """
    df = fetch_stock_data(ticker, period, interval)
    
    # Chart title
    title = f"{ticker} | {period} | {interval}"
    if moving_averages:
        ma_str = ", ".join([f"MA{ma}" for ma in moving_averages])
        title += f" | {ma_str}"
    
    # Create chart
    fig, axes = mpf.plot(
        df,
        type="candle",
        volume=show_volume,
        mav=moving_averages,
        style=CHART_STYLE,
        title=title,
        figsize=(12, 6),
        returnfig=True,
        ylabel="Price (USD)",
        ylabel_lower="Volume",
    )
    
    # Save to BytesIO
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    buf.seek(0)
    plt.close(fig)
    
    return buf


def get_stock_info(ticker: str) -> Dict[str, Any]:
    """
    Get latest stock price and information
    """
    df = fetch_stock_data(ticker, period="5d", interval="1d")
    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) > 1 else latest
    
    change = latest["Close"] - previous["Close"]
    change_percent = (change / previous["Close"]) * 100
    
    return {
        "ticker": ticker,
        "price": round(float(latest["Close"]), 2),
        "change": round(float(change), 2),
        "change_percent": round(float(change_percent), 2),
        "volume": int(latest["Volume"]),
        "high": round(float(latest["High"]), 2),
        "low": round(float(latest["Low"]), 2),
        "open": round(float(latest["Open"]), 2),
        "date": latest.name.strftime("%Y-%m-%d %H:%M:%S")
    }


# ================== API Endpoints ==================

@app.route('/', methods=['GET'])
def home():
    """API information endpoint"""
    return jsonify({
        "service": "Stock Chart API",
        "version": "1.0",
        "endpoints": {
            "/chart": "Generate stock chart (GET)",
            "/info": "Get stock information (GET)",
            "/health": "Health check (GET)"
        },
        "parameters": {
            "ticker": "Stock symbol (required)",
            "period": "Time period (optional, default: 6mo)",
            "interval": "Data interval (optional, default: 1d)",
            "ma": "Moving averages (optional, e.g., 20,50,200)"
        },
        "example": "/chart?ticker=TSLA&period=3mo&ma=20,50"
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/chart', methods=['GET'])
def get_chart():
    """
    Generate and return stock chart
    
    Query Parameters:
        - ticker (required): Stock symbol (e.g., TSLA, AAPL)
        - period (optional): Time period (default: 6mo)
        - interval (optional): Data interval (default: 1d)
        - ma (optional): Moving averages, comma-separated (e.g., 20,50,200)
        - volume (optional): Show volume (true/false, default: true)
    
    Returns:
        PNG image of the chart
    """
    try:
        # Get parameters
        ticker = request.args.get('ticker', '').strip().upper()
        if not ticker:
            return jsonify({
                "error": "Missing required parameter 'ticker'",
                "example": "/chart?ticker=TSLA"
            }), 400
        
        period = request.args.get('period', '6mo')
        interval = request.args.get('interval', '1d')
        ma_param = request.args.get('ma', '20,50')
        show_volume = request.args.get('volume', 'true').lower() == 'true'
        
        # Parse moving averages
        moving_averages = None
        if ma_param:
            try:
                moving_averages = tuple(int(x.strip()) for x in ma_param.split(','))
            except ValueError:
                return jsonify({
                    "error": "Invalid moving averages format",
                    "example": "ma=20,50,200"
                }), 400
        
        logger.info(f"Generating chart for {ticker} ({period}, {interval})")
        
        # Generate chart
        chart_buffer = generate_chart_image(
            ticker=ticker,
            period=period,
            interval=interval,
            moving_averages=moving_averages,
            show_volume=show_volume
        )
        
        # Return image
        return send_file(
            chart_buffer,
            mimetype='image/png',
            as_attachment=False,
            download_name=f'{ticker}_chart.png'
        )
        
    except ValueError as e:
        logger.error(f"Data error: {e}")
        return jsonify({
            "error": str(e),
            "ticker": ticker
        }), 404
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@app.route('/info', methods=['GET'])
def get_info():
    """
    Get stock information (price, change, volume, etc.)
    
    Query Parameters:
        - ticker (required): Stock symbol
    
    Returns:
        JSON with stock information
    """
    try:
        ticker = request.args.get('ticker', '').strip().upper()
        if not ticker:
            return jsonify({
                "error": "Missing required parameter 'ticker'",
                "example": "/info?ticker=TSLA"
            }), 400
        
        logger.info(f"Getting info for {ticker}")
        
        info = get_stock_info(ticker)
        return jsonify(info)
        
    except ValueError as e:
        logger.error(f"Data error: {e}")
        return jsonify({
            "error": str(e),
            "ticker": ticker
        }), 404
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": ["/", "/chart", "/info", "/health"]
    }), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({
        "error": "Internal server error"
    }), 500


# ================== Main ==================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Stock Chart API on port {port}")
    logger.info(f"Debug mode: {debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
