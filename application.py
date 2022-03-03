import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, usd, lookup, company

from flask import Markup

import requests
import urllib.parse
from functools import wraps

import datetime




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


    userId = session['user_id']


    history = db.execute("SELECT symbol, shares, price, transacted FROM trades WHERE userId = :userId",
                         userId=session['user_id'])

    return render_template("history.html", history=history)

@app.route("/datefilter", methods=["GET", "POST"])
@login_required
def datefilter():
    """Show filtered history of transactions"""

    if request.method == "POST":

        # Current user that is logged-in saved in variable
        userId = session['user_id']

        beg = request.form.get("datestart")

        fin = request.form.get("dateend")

        filterDates = db.execute("SELECT symbol, shares, price, transacted FROM trades WHERE transacted >= :beg AND transacted <= :fin AND userId = :userId", userId=userId, beg=beg, fin=fin)
        print(filterDates)
        return render_template("datefilter.html", filterDates=filterDates)
    else:
        return render_template("history.html")

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
        return redirect("/marketwatch")

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


@app.route("/marketwatch")
@login_required
def marketwatch():
    """Get all stocks on the market."""

    api_key = os.environ.get("API_KEY")
    response = requests.get(f"https://cloud.iexapis.com/stable/ref-data/symbols?token={api_key}")
    response.raise_for_status()

    # Parse response
    allStocks = []
    stocksData = []

    quote = response.json()

    for i in quote:
        dataObject = {
        "symbol": i["symbol"],
        "name": i["name"],
        "stockExchange": i["exchange"],
        "date": i["date"],
        "sort": i["type"]
        }
        allStocks.append(dataObject)
        symbol = dataObject["symbol"]
        name = dataObject["name"]
        sort = dataObject["sort"]
        stockExchange = dataObject["stockExchange"]
        stocksData.append({"symbol": symbol, "name": name, "stockExchange": stockExchange, "sort": sort})

        totalStocks = len(allStocks)

    return render_template("marketwatch.html", allStocks=allStocks, stocksData=stocksData, totalStocks=totalStocks)


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

        # Create company profile
        profile = company(symbol)
        comName = profile["comName"]
        employees = profile ["employees"]
        exchange = profile ["exchange"]
        industry = profile ["industry"]
        description = profile ["description"]
        ceo = profile ["CEO"]
        issueType = profile ["issueType"]
        sector =  profile ["sector"]
        address =  profile ["address"]
        state = profile ["state"]
        city = profile ["city"]
        zipC = profile ["zip"]
        country = profile ["country"]
        phone = profile ["phone"]

        # Creating the chart for the stock symbol
        api_key = os.environ.get("API_KEY")
        response = requests.get(f"https://cloud-sse.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/chart/1m?token={api_key}")
        response.raise_for_status()

        chart = response.json()
        dataList = []

        for i in chart:
            dataObject = {
            "label": i["label"],
            "close": i["close"]
            }
            dataList.append(dataObject)
        labels = [dataObject["label"] for dataObject in dataList]
        values = [dataObject["close"] for dataObject in dataList]
        colors = [ "#F7464A", "#46BFBD", "#FDB45C", "#FEDCBA","#ABCDEF", "#DDDDDD", "#ABCABC", "#CAABB9", "#46F7F3", "#EFCDAB", "#ABEFBE", ]

        date = datetime.datetime.now()
        currentDate = date.strftime("%c")

        # Sending the stock data to html/jinja
        return render_template("quoted.html", name=stockname, symbol=stocksymbol, price=usd(price), currentDate=currentDate, comName=comName, employees=employees, exchange=exchange, industry=industry, description=description, ceo=ceo, issueType=issueType, sector=sector, address=address, state=state, city=city, zipC=zipC, country=country, phone=phone, chart=chart, labels=labels, values=values, colors=colors)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/changepass", methods=["GET", "POST"])
@login_required
def changepass():
    """Change password"""

    if request.method == "POST":

        userId = session["user_id"]

        oldpassword = request.form.get("oldpassword")
        newpass = request.form.get("newpass")
        verifynew = request.form.get("verifynew")
        newhash = generate_password_hash(newpass)

        db.execute("UPDATE users SET hash = :newhash WHERE id = :userId",
                          userId=userId, newhash=newhash)
        flash("Password changed")
        return redirect("/")
    else:
        return render_template("changepass.html")



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



@app.route("/calculator", methods=["GET", "POST"])
@login_required
def calculator():
    """Calculate personal finance"""

    if request.method == "POST":

        income = request.form.get("income")

        if not income:
            return apology("must provide income amount")

        if not income.isdigit() or float(income) == 0:
            return apology("Please enter a positive number")



        labels = ["Housing","Pension,Insurance","Groceries,Food","Medical,Health","Transportation","Debt","Utilities","Clothing","Vacationing","Unexpected Necessities"]

        spendings = {}
        housingMin = float(income) * 0.25
        housingMax = float(income) * 0.35
        foodMin = float(income) * 0.11
        foodMax = float(income) * 0.15
        piMin = float(income) * 0.15
        piMax = float(income) * 0.20
        healthMin = float(income) * 0.10
        healthMax = float(income) * 0.12
        transportMin = float(income) * 0.08
        transportMax =  float(income) * 0.12
        debtsMin = float(income) * 0.15
        debtsMax = float(income) * 0.20
        utilitiesMin = float(income) * 0.05
        utilitiesMax = float(income) * 0.10
        clothingMin = float(income) * 0.03
        clothingMax = float(income) * 0.07
        vacationingMin = float(income) * 0.05
        vacationingMax = float(income) * 0.10
        miscMin = float(income) * 0.05
        miscMax = float(income) * 0.10

        spendings = ({"minimum": housingMin, "maximum": housingMax},{"minimum": foodMin, "maximum": foodMax},{"minimum": piMin, "maximum": piMax},{"minimum": healthMin, "maximum": healthMax},{"minimum": transportMin, "maximum": transportMax},{"minimum": debtsMin, "maximum": debtsMax},{"minimum": utilitiesMin, "maximum": utilitiesMax},{"minimum": clothingMin, "maximum": clothingMax},{"minimum": vacationingMin, "maximum": vacationingMax},{"minimum": miscMin, "maximum": miscMax})

        valuesMinimum = [dataObject["minimum"] for dataObject in spendings]

        valuesMaximum = [dataObject["maximum"] for dataObject in spendings]


        colorsChart = [ "#F7464A", "#46BFBD", "#FDB45C", "#FEDCBA","#ABCDEF", "#DDDDDD", "#ABCABC", "#CAABB9", "#46F7F3", "#EFCDAB", "#ABEFBE", ]


        return render_template("/calculated.html",
        housingMin=housingMin, housingMax=housingMax, foodMin=foodMin, foodMax=foodMax, piMin=piMin, piMax=piMax, healthMin=healthMin, healthMax=healthMax, transportMin=transportMin, transportMax=transportMax, debtsMin=debtsMin, debtsMax=debtsMax, utilitiesMin=utilitiesMin,  utilitiesMax=utilitiesMax, clothingMin=clothingMin, clothingMax=clothingMax, vacationingMin=vacationingMin, vacationingMax=vacationingMax, miscMin=miscMin, miscMax=miscMax, valuesMinimum=valuesMinimum, valuesMaximum=valuesMaximum, labels=labels, colorsChart=colorsChart)
    else:
        return render_template("calculator.html")


@app.route("/addnotes", methods=["GET", "POST"])
@login_required
def addnotes():
    """Make notes on stocks"""

    if request.method == "POST":

        # Current user that is logged-in saved in variable
        memberId = session['user_id']
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("for better organized notes, please enter stock symbol")

        note = request.form.get("note")
        if not note:
            return apology("Note field is empty.")

        db.execute("INSERT INTO records(memberId, symbol, note, datetime)\
        VALUES(:memberId, :symbol, :note, datetime('now'))", memberId=memberId, symbol=symbol, note=note)

        # Flash message to confirm that the user add a note
        flash("Note added")
        return redirect("/notes")
    else:
        return render_template("addnotes.html")


@app.route("/notes", methods=["GET", "POST"])
@login_required
def notes():
    """Show main notes page"""

    memberId = session['user_id']

     # Query the "records" table
    allMemos = db.execute("SELECT memberId, symbol, note, datetime FROM records WHERE memberId = :memberId",
                                memberId=memberId)
    # Creating an empty list to store the values to be send to jinja html
    memosList = []
    for memo in allMemos:
        symbol = memo["symbol"]
        note = memo["note"]
        datetime = memo["datetime"]
        memosList.append({"symbol": symbol, "note": note, "datetime": datetime})

    return render_template("notes.html", memosList=memosList)


@app.route("/addactual", methods=["GET", "POST"])
@login_required
def addactual():
    """Add actual spendings"""

    if request.method == "POST":
        allPayments = []
        # Current user that is logged-in saved in variable
        userId = session["user_id"]
        month = request.form.get("month")
        housing = request.form.get("housing")
        housing = float(housing)
        pensionIns = request.form.get("pensionIns")
        pensionIns = float(pensionIns)
        food = request.form.get("food")
        food= float(food)
        health = request.form.get("health")
        health = float(health)
        transport = request.form.get("transport")
        transport = float(transport)
        debt = request.form.get("debt")
        debt = float(debt)
        utilities = request.form.get("utilities")
        utilities = float(utilities)
        clothing = request.form.get("clothing")
        clothing = float(clothing)
        vacation = request.form.get("vacation")
        vacation = float(vacation)
        unexpected = request.form.get("unexpected")
        unexpected = float(unexpected)
        total = housing + pensionIns + food + health + transport + debt + utilities + clothing + vacation + unexpected

        allPayments.append({"month": month, "housing": housing, "pensionIns": pensionIns, "food": food, "health": health, "transport": transport, "debt": debt, "utilities": utilities, "clothing": clothing, "vacation": vacation, "unexpected": unexpected, "total": total})
        allMonths = db.execute("SELECT month FROM payments WHERE userid = :userId", userId=userId)
        enteredMonths = allMonths[0]["month"]

        db.execute("INSERT INTO payments(userId, month, housing, pensionIns, food, health, transport, debt, utilities, clothing, vacation, unexpected, total)\
        VALUES(:userId, :month, :housing, :pensionIns, :food, :health, :transport, :debt, :utilities, :clothing, :vacation, :unexpected, :total)", userId=userId, month=month, housing=housing, pensionIns=pensionIns, food=food, health=health, transport=transport, debt=debt, utilities=utilities, clothing=clothing, vacation=vacation, unexpected=unexpected, total=total)
         # Flash message to confirm that the user add a note
        flash("Payments added")

        if month in enteredMonths:
            return apology("Monnth already entered!")

        return redirect("/actual")
    else:
        return render_template("addactual.html")

@app.route("/actual", methods=["GET", "POST"])
@login_required
def actual():
    """Show spendings page"""

    userId = session["user_id"]

     # Query the "records" table
    allspendings = db.execute("SELECT userId, month, housing, pensionIns, food, health, transport, debt, utilities, clothing, vacation, unexpected, total FROM payments WHERE userId = :userId",
                                userId=userId)
    # Creating an empty list to store the values to be send to jinja html
    spendingsList = []
    totalSum = 0
    for payment in allspendings:
        month = payment["month"]
        housing = payment["housing"]
        pensionIns = payment["pensionIns"]
        food = payment["food"]
        health = payment["health"]
        transport = payment["transport"]
        debt = payment["debt"]
        utilities = payment["utilities"]
        clothing = payment["clothing"]
        vacation = payment["vacation"]
        unexpected = payment["unexpected"]
        total = housing + pensionIns + food + health + transport + debt + utilities + clothing + vacation + unexpected
        totalSum += total
        spendingsList.append({"userId": userId, "month": month, "housing": housing, "pensionIns": pensionIns, "food": food, "health": health, "transport": transport, "debt": debt, "utilities": utilities, "clothing": clothing, "vacation": vacation, "unexpected": unexpected, "total": total})
    grandtotal = totalSum

    paymentsList = []

    for i in spendingsList:
        dataObject = {
        "month": i["month"],
        "housing": i["housing"],
        "total": i["total"]
        }
        paymentsList.append(dataObject)
    labels = [dataObject["month"] for dataObject in paymentsList]
    values = [dataObject["total"] for dataObject in paymentsList]
    housing = [dataObject["housing"] for dataObject in paymentsList]
    colors = [ "#F7464A", "#46BFBD", "#FDB45C", "#FEDCBA","#ABCDEF", "#DDDDDD", "#ABCABC", "#CAABB9", "#46F7F3", "#EFCDAB", "#ABEFBE", ]

    return render_template("actual.html", spendingsList=spendingsList, grandtotal=grandtotal, labels=labels, values=values, colors=colors, housing=housing)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
