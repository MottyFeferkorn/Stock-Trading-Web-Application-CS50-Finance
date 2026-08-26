from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, make_response
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    user = session["user_id"]
    stocks_owned = db.execute(
        "SELECT stock_symbol, SUM(amount) AS total_amount FROM portfolio WHERE users_id = ? GROUP BY stock_symbol", user)
    cash_query = db.execute("SELECT cash FROM users WHERE id = ?", user)
    cash = cash_query[0]['cash']
    grand_total = cash
    for row in stocks_owned:
        price = lookup(row['stock_symbol'])['price']
        amount = float(row['total_amount'])
        total = price * amount
        grand_total += total
        row['price'] = price
        row['total'] = total

    return render_template("index.html", stocks=stocks_owned, cash=cash, total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        amount = request.form.get("shares")
        stock_info = lookup(symbol)

        # if it is valid update table otherwise throw error
        if stock_info:
            if amount:
                try:
                    amount_int = float(amount)
                except ValueError:
                    return apology("Pleses enter valid amount")
                else:
                    if amount_int > 0 and amount_int.is_integer():
                        price = amount_int * stock_info['price']
                        try:
                            db.execute("BEGIN TRANSACTION")
                            update = db.execute(
                                "UPDATE users SET cash = (cash - ?) WHERE id = ? AND (cash - ?) >= 0", price, session["user_id"], price)

                            auto_increment_id = db.execute(
                                "INSERT INTO transactions (users_id, type, stock_symbol, amount, stock_price) VALUES (?, 'buy', ?, ?, ?)", session["user_id"], stock_info['symbol'], amount, stock_info['price'])

                            if update != 1:
                                raise ValueError("Update Failed")

                            db.execute("COMMIT")

                        except ValueError:
                            db.execute("ROLLBACK")
                            return apology("Insufficient funds")
                        else:
                            flash("Purchase Succesfull")
                            return redirect("/")
                    else:
                        return apology("Pleses enter valid amount")
            else:
                return apology("Pleses enter valid amount")
        else:
            return apology("Pleses enter valid stock symbol")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    transactions = db.execute(
        "SELECT * FROM transactions WHERE users_id = ? ORDER BY time_stamp DESC", session['user_id'])

    for row in transactions:
        row['price'] = float(row['stock_price'])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    # difrentiate if user should see the quote form or results if posted
    if request.method == "POST":
        user_input = request.form.get("symbol")
        stock_info = lookup(user_input)

        # if was invalid input render apology
        if not stock_info:
            return apology("Invalid Entry")

        return render_template("quote.html", stock_info=stock_info, previous_input=user_input, title="Quoted")

    else:
        return render_template("quote.html", title="quote")


@app.route("/register", methods=["GET", "POST"])
def register():
    # if user visits by post handle registration
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")

        # validates that user filled out all 3 fields
        if username and password and confirm_password:

            # validate that password and confirmation matches
            if password == confirm_password:

                # hash password
                hashed_password = generate_password_hash(password)

                # try adding user if value error username exists
                try:
                    # update data base
                    db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                               username, hashed_password)

                except ValueError:
                    return apology("User name exists.")
                else:
                    return redirect("/login")
            else:
                return apology("Password and confirmation doesn't match")
        else:
            return apology("Please fill out all fields")
    # if user visits by get show the registration page
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        amount = request.form.get("shares")
        stock_info = lookup(symbol)

        # if it is valid update table otherwise throw error
        if stock_info:
            if amount:
                try:
                    amount_int = float(amount)
                except ValueError:
                    return apology("Pleses enter valid amount")
                else:
                    if amount_int > 0 and amount_int.is_integer():
                        price = amount_int * stock_info['price']
                        # add sell if has enough of those shares
                        try:
                            db.execute("BEGIN TRANSACTION")

                            # sell update
                            sold = db.execute("INSERT INTO transactions (users_id, type, stock_symbol, amount, stock_price) VALUES (?, 'sell', ?, ?, ?)",
                                              session["user_id"], stock_info['symbol'], amount, stock_info['price'])

                            # calculate current amount of stocks
                            current_stock_quantaty = db.execute(
                                "SELECT stock_symbol, SUM(amount) AS total_amount FROM portfolio WHERE users_id = ? AND stock_symbol = ? GROUP BY stock_symbol", session["user_id"], stock_info['symbol'])

                            if current_stock_quantaty:
                                # check if he has gone minus
                                if current_stock_quantaty[0]['total_amount'] < 0:
                                    raise ValueError("Update Failed")
                            else:
                                raise ValueError("Update Failed")

                            update_cash_value = db.execute(
                                "UPDATE users SET cash = (cash + ?) WHERE id = ?", price, session["user_id"])

                            db.execute("COMMIT")

                        except ValueError:
                            db.execute("ROLLBACK")
                            return apology("You don't have enough " + symbol + " stocks")
                        else:
                            flash("Sold succesful")
                            return redirect("/")
            else:
                return apology("Enter amount")
        else:
            return apology("Enter valid stock name")

    else:
        stocks = db.execute(
            "SELECT stock_symbol, SUM(amount) AS total_amount FROM portfolio WHERE users_id = ? GROUP BY stock_symbol HAVING total_amount > 0", session["user_id"])
        for row in stocks:
            print(row["stock_symbol"])
        return render_template("sell.html", stocks=stocks)


@app.route("/buy_quote", methods=["POST"])
@login_required
def buy_quote():
    symbol = request.form.get("symbol")
    amount = request.form.get("shares")
    stock_info = lookup(symbol)

    # if it is valid format answer
    if stock_info:
        if amount:
            try:
                amount_int = int(float(amount))
            except ValueError:
                return make_response('', 204)
            else:
                if amount_int > 0:
                    price = usd(stock_info["price"] * amount_int)
                    return render_template("buy.html", price=price, symbol=symbol, amount=amount_int)
    # otherwise return nothing
    return make_response('', 204)


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")

        # validates that user filled out all 3 fields
        if password and confirm_password:

            # validate that password and confirmation matches
            if password == confirm_password:

                # hash password
                hashed_password = generate_password_hash(password)

                # update data base
                db.execute("UPDATE users SET hash = ? WHERE id = ?",
                           hashed_password, session["user_id"])

                flash("Updated Succsefull")

                return redirect("/")
            else:
                return apology("Password and confirmation doesn't match")
        else:
            return apology("Please fill out all fields")
    else:
        return render_template("account.html")
