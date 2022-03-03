import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps

from helpers import apology, login_required, usd


def main():


        personalFinance = {}
        allData = []
        minimum = []
        maximum = []
        what = []
        income = 30000

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
        miscMin = usd(float(income) * 0.05)
        miscMax = usd(float(income) * 0.10)

        payments = ["Housing","Pension,Insurance","Groceries,Food","Medical,Health","Transportation","Debt","Utilities","Clothing","Vacationing","Unexpected Necessities"]


        personalFinance = ({"minimum": usd(housingMin), "maximum": housingMax},{"minimum": foodMin, "maximum": foodMax},{"minimum": piMin, "maximum": piMax},{"minimum": healthMin, "maximum": healthMax},{"minimum": transportMin, "maximum": transportMax},{"minimum": debtsMin, "maximum": debtsMax},{"minimum": utilitiesMin, "maximum": utilitiesMax},{"minimum": clothingMin, "maximum": clothingMax},{"minimum": vacationingMin, "maximum": vacationingMax},{"minimum": miscMin, "maximum": miscMax})



        valuesMinimum = [dataObject["minimum"] for dataObject in personalFinance]
        print(valuesMinimum)
        valuesMaximum = [dataObject["maximum"] for dataObject in personalFinance]
        print(valuesMaximum)
main()