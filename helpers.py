import os
import requests
import urllib.parse
from datetime import datetime, timedelta

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol, cache):
    """Look up quote for symbol using FMP API."""
    if symbol in cache:
        data, timestamp = cache[symbol]
        if datetime.now() - timestamp < timedelta(minutes=5):
            return data

    try:
        api_key = os.environ.get("API_KEY")
        url = f"https://financialmodelingprep.com/api/v3/quote/{urllib.parse.quote_plus(symbol)}?apikey={api_key}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if not data:
            return None

        quote = data[0]
        price = quote.get("price")

        if price is None:
            return None

        result = {
            "name": quote.get("name"),
            "price": float(price),
            "symbol": quote.get("symbol"),
            "previous_close": float(quote["previousClose"]) if "previousClose" in quote and quote["previousClose"] is not None else None
        }

        cache[symbol] = (result, datetime.now())
        return result
    except (requests.RequestException, ValueError, IndexError, KeyError, TypeError):
        return None

def search_symbols(keywords, asset_type, cache):
    """Search for stock or crypto symbols using FMP API by changing the API endpoint parameters."""
    cache_key = f"search_{asset_type}_{keywords}"

    if cache_key in cache:
        data, timestamp = cache[cache_key]
        if datetime.now() - timestamp < timedelta(hours=1):
            return data

    try:
        api_key = os.environ.get("API_KEY")

        base_url = f"https://financialmodelingprep.com/api/v3/search?query={urllib.parse.quote_plus(keywords)}&limit=10&apikey={api_key}"

        if asset_type == "crypto":
            url = f"{base_url}&exchange=CRYPTO"
        else:
            url = base_url

        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if asset_type == 'stock':
            matches = [match for match in data if match.get("currency") == "USD"]
        else:
            matches = data

        cache[cache_key] = (matches, datetime.now())
        return matches
    except (requests.RequestException, ValueError):
        return []

def get_historical_data(symbol, cache):
    """Get historical daily price data for a symbol and return it as a dict."""
    cache_key = f"historical_{symbol}"

    if cache_key in cache:
        data, timestamp = cache[cache_key]
        if datetime.now() - timestamp < timedelta(days=1):
            print(f"DEBUG: Using CACHED historical data for '{symbol}'")
            return data

    print(f"DEBUG: Making NEW API call to FMP for historical data: '{symbol}'")
    try:
        api_key = os.environ.get("API_KEY")
        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{urllib.parse.quote_plus(symbol)}?apikey={api_key}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        historical_list = []
        if isinstance(data, dict) and 'historical' in data:
            historical_list = data.get("historical", [])
        elif isinstance(data, list):
            historical_list = data

        price_dict = {item['date']: item['close'] for item in historical_list if 'date' in item and 'close' in item}

        cache[cache_key] = (price_dict, datetime.now())
        return price_dict
    except (requests.RequestException, ValueError) as e:
        print(f"ERROR: Exception during historical data fetch for {symbol}: {e}")
        return {}

def get_stock_news(company_name, cache):
    """Get recent news for a company name using NewsAPI.org."""
    cache_key = f"news_{company_name}"

    if cache_key in cache:
        data, timestamp = cache[cache_key]
        if datetime.now() - timestamp < timedelta(minutes=30):
            return data

    try:
        api_key = os.environ.get("NEWS_API_KEY")
        url = f"https://newsapi.org/v2/everything?q={urllib.parse.quote_plus(company_name)}&sortBy=publishedAt&pageSize=10&apiKey={api_key}"

        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        news_data = data.get("articles", [])
        cache[cache_key] = (news_data, datetime.now())
        return news_data
    except (requests.RequestException, ValueError):
        return []


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
