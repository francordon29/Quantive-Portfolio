import os
import json
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta, date
from flask_compress import Compress

from helpers import apology, login_required, lookup, usd, search_symbols, get_historical_data, get_stock_news

app = Flask(__name__)

Compress(app)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(days=365)
STATIC_VERSION = "v4"
@app.context_processor
def inject_static_version():
    return dict(STATIC_VERSION=STATIC_VERSION)

api_cache = {}

app.jinja_env.filters["usd"] = usd

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL("sqlite:///finance.db")

if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def add_header(response):
    """
    Cachea estáticos 1 año y evita recachear HTML dinámico
    """
    if response.headers.get("Content-Type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
    else:
        response.headers["Cache-Control"] = "public, max-age=31536000"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks with advanced metrics and a real growth chart"""
    user_id = session["user_id"]

    holdings_db = db.execute(
        "SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0", user_id)

    grand_total_value = 0
    total_pl = 0
    total_daily_pl = 0
    total_invested = 0
    holdings = []
    all_historical_prices = {}

    for row in holdings_db:
        quote = lookup(row["symbol"], api_cache)

        if not quote:
            print(f"WARNING: Could not retrieve quote for {row['symbol']}. Skipping this holding.")
            continue

        cost_basis_rows = db.execute(
            "SELECT SUM(price * shares) as total_cost, SUM(shares) as total_shares_bought FROM transactions WHERE user_id = ? AND symbol = ? AND shares > 0", user_id, row["symbol"])

        total_cost_for_holding = cost_basis_rows[0]["total_cost"] or 0
        total_shares_bought = cost_basis_rows[0]["total_shares_bought"] or 0
        avg_price = total_cost_for_holding / total_shares_bought if total_shares_bought > 0 else 0

        current_value = row["total_shares"] * quote["price"]
        unrealized_pl = current_value - (row["total_shares"] * avg_price)

        previous_close_safe = quote.get("previous_close", quote["price"])
        daily_pl = (quote["price"] - previous_close_safe) * row["total_shares"]

        position_cost_basis = row["total_shares"] * avg_price
        total_pl_pct_for_holding = (unrealized_pl / position_cost_basis) * 100 if position_cost_basis > 0 else 0

        price_change_abs = quote["price"] - previous_close_safe
        price_change_pct = (price_change_abs / previous_close_safe) * 100 if previous_close_safe > 0 else 0

        holdings.append({
            "symbol": row["symbol"], "shares": row["total_shares"], "price": quote["price"],
            "avg_price": avg_price, "total_value": current_value, "total_pl": unrealized_pl,
            "daily_pl": daily_pl, "price_change_abs": price_change_abs, "price_change_pct": price_change_pct,
            "total_pl_pct": total_pl_pct_for_holding
        })

        grand_total_value += current_value
        total_pl += unrealized_pl
        total_daily_pl += daily_pl
        total_invested += position_cost_basis

        all_historical_prices[row["symbol"]] = get_historical_data(row["symbol"], api_cache)

    total_pl_pct = (total_pl / total_invested) * 100 if total_invested > 0 else 0
    yesterday_value = grand_total_value - total_daily_pl
    total_daily_pl_pct = (total_daily_pl / yesterday_value) * 100 if yesterday_value > 0 else 0

    dist_chart_labels = [h['symbol'] for h in holdings]
    dist_chart_values = [h['total_value'] for h in holdings]

    transactions = db.execute("SELECT symbol, shares, price, DATE(timestamp) as date FROM transactions WHERE user_id = ? ORDER BY timestamp ASC", user_id)

    growth_chart_labels = []
    growth_chart_values_abs = []
    growth_chart_values_pct = []

    if transactions and holdings:
        start_date = datetime.strptime(transactions[0]['date'], '%Y-%m-%d').date()
        end_date = date.today()

        time_span_days = (end_date - start_date).days
        if time_span_days > 365 * 2:
            delta = timedelta(days=30)
            time_unit = 'month'
        elif time_span_days > 90:
            delta = timedelta(days=7)
            time_unit = 'week'
        else:
            delta = timedelta(days=1)
            time_unit = 'day'

        current_date = start_date
        last_added_date = None

        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')

            if time_unit == 'week' and last_added_date and current_date.isocalendar()[:2] == last_added_date.isocalendar()[:2]:
                current_date += timedelta(days=1)
                continue
            if time_unit == 'month' and last_added_date and current_date.month == last_added_date.month and current_date.year == last_added_date.year:
                current_date += timedelta(days=1)
                continue

            holdings_on_date = {}
            cost_basis_on_date = 0

            for t in transactions:
                if t['symbol'] in all_historical_prices:
                    if t['date'] <= date_str:
                        holdings_on_date[t['symbol']] = holdings_on_date.get(t['symbol'], 0) + t['shares']
                        if t['shares'] > 0:
                            cost_basis_on_date += t['shares'] * t['price']

            value_on_date = 0
            for symbol, shares in holdings_on_date.items():
                if shares > 0:
                    price_history = all_historical_prices.get(symbol, {})
                    price_on_date = price_history.get(date_str)

                    if not price_on_date:
                        temp_date = current_date - timedelta(days=1)
                        while temp_date >= start_date:
                            price_on_date = price_history.get(temp_date.strftime('%Y-%m-%d'))
                            if price_on_date:
                                break
                            temp_date -= timedelta(days=1)

                    if price_on_date:
                        value_on_date += shares * price_on_date

            if value_on_date > 0:
                growth_chart_labels.append(date_str)
                growth_chart_values_abs.append(round(value_on_date, 2))
                pct_growth = ((value_on_date - cost_basis_on_date) / cost_basis_on_date) * 100 if cost_basis_on_date > 0 else 0
                growth_chart_values_pct.append(round(pct_growth, 2))

            last_added_date = current_date
            current_date += delta

    all_chart_data = {
        "distribution": {"labels": dist_chart_labels, "values": dist_chart_values},
        "growth": {
            "labels": growth_chart_labels,
            "values_abs": growth_chart_values_abs,
            "values_pct": growth_chart_values_pct
        }
    }

    return render_template("index.html",
                           holdings=holdings, grand_total=grand_total_value, total_pl=total_pl,
                           total_daily_pl=total_daily_pl, total_pl_pct=total_pl_pct,
                           total_daily_pl_pct=total_daily_pl_pct, chart_data_json=all_chart_data)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Log a stock or crypto purchase"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        asset_type = request.form.get("asset_type")

        try:
            shares = float(request.form.get("shares"))
            price = float(request.form.get("price"))
        except (ValueError, TypeError):
            return apology("shares and price must be numbers", 400)

        date_str = request.form.get("date")

        if not date_str:
            return apology("must provide a transaction date", 400)

        transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if transaction_date > date.today():
            return apology("date cannot be in the future", 400)

        if not symbol or shares <= 0 or price <= 0 or not asset_type:
            return apology("all fields are required", 400)

        quote = lookup(symbol, api_cache)
        if quote is None:
            return apology("invalid symbol", 400)

        user_id = session["user_id"]

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, timestamp, asset_type) VALUES (?, ?, ?, ?, ?, ?)",
                   user_id, symbol, shares, price, date_str, asset_type)

        flash("Purchase logged successfully!", "success")
        return redirect("/")
    else:
        today = date.today().strftime('%Y-%m-%d')
        return render_template("buy.html", today=today)

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions = db.execute(
        "SELECT id, symbol, shares, price, timestamp FROM transactions WHERE user_id = ? ORDER BY timestamp DESC", user_id)
    return render_template("history.html", transactions=transactions)


@app.route("/calculator")
@login_required
def calculator():
    """Show P/L calculator page"""
    return render_template("calculator.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 400)
        elif not password:
            return apology("must provide password", 400)
        elif password != confirmation:
            return apology("passwords do not match", 400)

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) > 0:
            return apology("username already exists", 400)

        hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        session["user_id"] = rows[0]["id"]

        flash("Registered successfully!", "success")
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Log a stock sale and calculate realized profit/loss"""
    user_id = session["user_id"]

    if request.method == "POST":
        symbol = request.form.get("symbol")

        try:
            shares_to_sell = int(request.form.get("shares"))
            price = float(request.form.get("price"))
        except (ValueError, TypeError):
            return apology("shares and price must be numbers", 400)

        date_str = request.form.get("date")

        if not date_str:
            return apology("must provide a transaction date", 400)

        transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if transaction_date > date.today():
            return apology("date cannot be in the future", 400)

        if not symbol or shares_to_sell <= 0 or price <= 0:
            return apology("all fields are required", 400)

        owned_shares_rows = db.execute(
            "SELECT SUM(shares) as total_shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)

        if not owned_shares_rows or owned_shares_rows[0]["total_shares"] < shares_to_sell:
            return apology("not enough shares to sell", 400)

        cost_basis_rows = db.execute(
            "SELECT SUM(price * shares) as total_cost, SUM(shares) as total_shares_bought FROM transactions WHERE user_id = ? AND symbol = ? AND shares > 0", user_id, symbol)

        total_cost = cost_basis_rows[0]["total_cost"]
        total_shares_bought = cost_basis_rows[0]["total_shares_bought"]
        average_cost_per_share = total_cost / total_shares_bought

        cost_of_shares_sold = shares_to_sell * average_cost_per_share

        total_sale_value = shares_to_sell * price
        realized_pl = total_sale_value - cost_of_shares_sold

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, timestamp) VALUES (?, ?, ?, ?, ?)",
                   user_id, symbol, -shares_to_sell, price, date_str)

        if realized_pl >= 0:
            flash(f"Sold successfully! Realized Profit: ${realized_pl:,.2f}", "success")
        else:
            flash(f"Sold successfully! Realized Loss: ${-realized_pl:,.2f}", "danger")

        return redirect("/")
    else:
        today = date.today().strftime('%Y-%m-%d')
        symbols = db.execute(
            "SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", user_id)
        user_symbols = [row['symbol'] for row in symbols]
        return render_template("sell.html", symbols=user_symbols, today=today)


@app.route("/reset", methods=["POST"])
@login_required
def reset():
    """Reset the user's entire transaction history"""
    user_id = session["user_id"]

    db.execute("DELETE FROM transactions WHERE user_id = ?", user_id)

    flash("Your portfolio has been reset!", "success")
    return redirect("/")


@app.route("/analysis")
@login_required
def analysis():
    """Show stock analysis search page"""
    return render_template("analysis.html")


@app.route("/stock/<symbol>")
@login_required
def stock_detail(symbol):
    """Show detail page for a specific stock."""

    quote = lookup(symbol, api_cache)
    if not quote:
        return apology("Stock symbol not found", 404)

    historical_data = get_historical_data(symbol, api_cache)

    news = get_stock_news(quote["name"], api_cache)

    return render_template("stock_detail.html",
                           quote=quote,
                           historical_data=historical_data,
                           news=news)



@app.route("/search")
@login_required
def search():
    """Search for stock or crypto symbols."""
    q = request.args.get("q")
    asset_type = request.args.get("type", "stock")
    if q:
        matches = search_symbols(q, asset_type, api_cache)
        return jsonify(matches)
    return jsonify([])


@app.route("/delete/<int:transaction_id>", methods=["POST"])
@login_required
def delete(transaction_id):
    """Delete a specific transaction"""
    user_id = session["user_id"]

    db.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", transaction_id, user_id)

    flash("Transaction deleted successfully!", "success")
    return redirect("/history")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
