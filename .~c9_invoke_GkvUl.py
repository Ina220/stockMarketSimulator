import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, graphic, analize

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Current user that is logged-in saved in variable
    userId = session['user_id']

    # Query the "trades" table
    stocksData = db.execute("SELECT symbol, name, TOTAL(shares) AS sharesOwned FROM trades WHERE userId = :userId GROUP BY symbol",
                            userId=userId)

    # Query the users table to save users cash into a variable
    usersCash = db.execute("SELECT cash FROM users WHERE id = :userId", userId=userId)
    usersBudget = usersCash[0]["cash"]

    # Creating an empty dictionary
    stocksDict = []
    totalSum = 0

    # For every stock in the user's portfolio, assign dict key/values for use in html/jinja
    for stock in stocksData:

        stockQuote = lookup(stock["symbol"])
        symbol = stockQuote["symbol"]
        name = stockQuote["name"]
        shares = int(stock["sharesOwned"])
        price = stockQuote["price"]
        total = price * shares
        totalSum += total
        stocksDict.append({"symbol": symbol, "name": name, "shares": shares, "price": price, "total": total})

    grandTotal = usersBudget + totalSum

    # Send to html
    return render_template("index.html", stocksData=stocksData, usersBudget=usersBudget, stocksDict=stocksDict, grandTotal="{0:,.2f}".format(grandTotal))


@app.route("/home")
@login_required
def home():
    """Show of portfolio with graph"""

 # Current user that is logged-in saved in variable
    userId = session['user_id']

    # Query the "trades" table
    stocksData = db.execute("SELECT symbol, name, TOTAL(shares) AS sharesOwned FROM trades WHERE userId = :userId GROUP BY symbol",
                            userId=userId)

    # Query the users table to save users cash into a variable
    usersCash = db.execute("SELECT cash FROM users WHERE id = :userId", userId=userId)
    usersBudget = usersCash[0]["cash"]

    # Creating an empty dictionary
    stocksDict = []
    totalSum = 0
    labels = []
    data = []

    for i in stocksData:
        stockQuote = lookup(i["symbol"])
        symbol = stockQuote["symbol"]

        shares = int(i["sharesOwned"])
        data.append({"shares": shares})


    # For every stock in the user's portfolio, assign dict key/values for use in html/jinja
    for stock in stocksData:

        stockQuote = lookup(stock["symbol"])
        symbol = stockQuote["symbol"]
        name = stockQuote["name"]
        shares = int(stock["sharesOwned"])
        price = stockQuote["price"]
        total = price * shares
        totalSum += total
        stocksDict.append({"symbol": symbol, "name": name, "shares": shares, "price": price, "total": total})

    grandTotal = usersBudget + totalSum


    # Send to html
    return render_template("home.html", stocksData=stocksData, usersBudget=usersBudget, stocksDict=stocksDict, grandTotal="{0:,.2f}".format(grandTotal), labels=labels, data=data)





@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        # The user's input of stock symbol and number of shares to buy
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Run the lookup function to get the stock data
        stock = lookup(symbol)

        # If the user didn't typed a stock symbol
        if stock is None:
            return apology("Please enter a valid stock symbol")

        name = stock["name"]
        price = stock["price"]
        # Current user that is logged-in
        user_id = session["user_id"]

        # Query the user's cach then save into a variable
        cashData = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)
        cash = cashData[0]["cash"]
        transBought = "buy"

        # The user's input of number of shares
        # Return error message apology in case of blank field, not number, not positive number,insufficient funds
        if not shares.isdigit() or int(shares) == 0:
            return apology("Please enter a positive number")

        # Calculate the total amount of the stocks to buy
        total = price * int(shares)

        # Ensure that the users budget is enough to purchase stock/s
        if cash >= total:

            # Update the users cash
            cash = cash - total
            db.execute("UPDATE users SET cash = :cash WHERE id = :user_id",
                       cash=cash, user_id=user_id)

            # Insert the values into a table
            db.execute("INSERT INTO trades (userId, symbol, name, shares, price, total, tradeType, transacted)\
            VALUES (:userId, :symbol, :name, :shares, :price, :total, :transBought, datetime('now'))",
                       userId=user_id, symbol=symbol, name=name, shares=shares, price=price, total=total, transBought=transBought)

        else:
            # If the users budget isnt't sufficient to buy the desired number of shares, returns apology
            return apology("Sorry, your cash is lower than the stock price.")

        # Flash message to confirm that the user bought stock/s
        flash("Bought!")

        # Redirect user to homepage
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Current user that is logged-in saved in variable
    userId = session['user_id']

    # Create a display table with quering the "trades" table
    history = db.execute("SELECT symbol, shares, price, transacted FROM trades WHERE userId = :userId",
                         userId=userId)

    return render_template("history.html", history=history)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
    """Get stock quote."""

    if request.method == "POST":

        # Require that a user input a stock’s symbol
        symbol = request.form.get("symbol")

        # Run lookup function to get the stock data
        stock = lookup(symbol)

        # Ensure the user typed valid stock symbol, otherwise return apology
        if stock is None:
            return apology("Please enter valid stock symbol")

        # Save stock name into variable
        stockname = stock["name"]

        # Save stock current price into variable
        price = stock["price"]

        # Save stock symbol into variable
        stocksymbol = stock["symbol"]

        change = stock["change"]

        usMarket = stock["usMarket"]
        stockOpen = stock["openPrice"]
        stockClose = stock["closePrice"]
        ratio = stock["ratio"]

        # Sending the stock data to html/jinja
        return render_template("quoted.html", name=stockname, symbol=stocksymbol, price=usd(price), change=change, usMarket=usMarket, stockOpen=stockOpen, stockClose=stockClose, ratio=ratio)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/chart", methods=["GET", "POST"])
@login_required
def chart():
    """Get stock quote."""

    if request.method == "POST":

        # Require that a user input a stock’s symbol
        symbol = request.form.get("symbol")

        # Run lookup function to get the stock data
        show = graphic(symbol)

        # Ensure the user typed valid stock symbol, otherwise return apology
        if show is None:
            return apology("Please enter valid stock symbol")

        # Save stock name into variable
        stockopen = show["open"]

        # Save stock current price into variable


        # Save stock symbol into variable




        # Sending the stock data to html/jinja
        return render_template("charted.html", stockopen=stockopen, show=show)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("chart.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Submit a form via POST
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Hash the user's password
        hash = generate_password_hash(password)

        # Ensure the user typed username
        if not username:
            return apology("You have to create username to register")

        # Check if the username already exists
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)
        if rows:
            return apology("Sorry, that username already exists.")

        # Ensure that the user typed password and confirmed password
        if not password or not confirmation:
            return apology("You have to create/confirm password to register")

        # Ensure that password and confirmed password match
        if password != confirmation:
            return apology("Password and Confirm password did not match")

        # When form is submitted via POST, insert the new user into users table
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                   username=username, hash=hash)

        # Redirect user to homepage
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        # The user's input of stock symbol
        holdings = request.form.get("symbol")

        # Query table "trades" for symbol which shows that the user owns that stock
        holdingsOwned = db.execute("SELECT symbol FROM trades WHERE userId = :userId and symbol = :symbol",
                                   userId=session["user_id"], symbol=holdings)

        # Check if the user selected a stock symbol and if the user owns that stock
        if not holdings:
            return apology("Please choose symbol.")
        if not holdingsOwned:
            return apology("Sorry, stock not owned.")

        # The users input of number of shares to sell
        numberShares = request.form.get("shares")

        # Check if the user entered valid amount of shares
        sharesTotal = db.execute("SELECT SUM(shares) AS usersShares FROM trades WHERE userId = :userId AND symbol = :symbol",
                                 userId=session["user_id"], symbol=holdings)
        usersShares = sharesTotal[0]["usersShares"]

        # Check if user entered positive number
        if not numberShares.isdigit() or int(numberShares) == 0:
            return apology("Please enter a positive number")

        # Check if the user owns that number of shares as entered to sell
        if int(numberShares) > int(usersShares):
            return apology("Sorry, you don't own that many shares.")
        if usersShares <= 0:
            return apology("Please enter a valid number of shares")

        userId = session["user_id"]
        symbol = holdings
        soldStock = lookup(symbol)
        stockName = soldStock["name"]
        stockPrice = soldStock["price"]
        shares = float(numberShares)
        stockTotal = stockPrice * shares
        traderBudget = db.execute("SELECT cash FROM users WHERE id = :userId", userId=userId)
        usersCash = traderBudget[0]["cash"]
        usersCash = usersCash + stockTotal
        action = "sell"

        # Update users cash into users table
        db.execute("UPDATE users SET cash = :cash WHERE id = :userId", cash=usersCash, userId=userId)

        # Insert data of the sold shares into the table
        db.execute("INSERT INTO trades (userId, symbol, name, shares, price, total, tradeType, transacted)\
            VALUES (:userId, :symbol, :stockName, :shares, :stockPrice, :stockTotal, :action, datetime('now'))",
                   userId=userId, symbol=symbol, stockName=stockName, shares=-shares, stockPrice=stockPrice, stockTotal=stockTotal, action=action)

        # Flash message to confirm that the user sold stock/s
        flash("Sold")

        # Redirect to homepage
        return redirect("/")

    else:
        # Query table "trades" for stocks left to sell
        saleHoldings = db.execute("SELECT DISTINCT symbol FROM trades WHERE userId = :userId GROUP BY symbol HAVING SUM(shares) > 0",
                                  userId=session["user_id"])

        # Send variable that has left stocks to sell, to html
        return render_template("sell.html", saleHoldings=saleHoldings)

@app.route("/watch")
@login_required
def watch():
    """Get market quote."""
    market = []

    for y in market:
        for i in market[y]:
            symbol = i["symbol"]
            name= i["name"]
            date= i["date"]
            type = i["type"]
            iexId = i["iexId"]
            region = i["region"]
            currency = i["currency"]
            isEnabled = i["isEnabled"]
            figi = i["figi"]
            cik = i["cik"]
            market.append({"symbol": symbol, "name": name, "date": date, "type": type, "iexId": iexId, "region": region, "currency": currency, "isEnabled": isEnabled, " figi": figi, "cik": cik})

        marketWatch = analize(market)
        return render_template("watch.html", marketWatch=marketWatch, market=market)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
