"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.md

"""

import pandas as pd

from databasefxrates import get_fx_data
from yfinancefxrates import get_yfinance_fx_rates


def generate_fx_dictionary(all_currencies, source, from_date=None, to_date=None):
    """
    Return pd dataframe of currencies

    all_currencies is list of currencies to get

    fx source can be: 'FIXED' uses fixed rates for whole year, 'YFINANCE' downloads rates from www.YFINANCE.com
      'DATABASE' this is my function for accessing my own database. It won't work for you, need to roll your own
    """

    if source == "CSV":
        fx_dict = dict([(currency, get_fx_data(currency)) for currency in all_currencies])
    elif source == "FIXED":
        fx_dict = dict([(currency, get_fixed_fx_data(currency)) for currency in all_currencies])
    elif source == "YFINANCE":
        if not from_date or not to_date:
            raise Exception("Missing from_date or end_date to retrieve the fx data from yfinance")
        fx_dict = dict([(currency, get_yfinance_fx_rates(currency, from_date, to_date)) for currency in all_currencies])
    else:
        raise Exception("Source %s for fx data unknown. Use DATABASE or FIXED" % source)

    return fx_dict


def get_fixed_fx_data(currency):
    """
    Use this if you don't have proper FX data and are happy to use fixed values

    Rate starts in 2008 (before that old CGT rules applied) and will be forward filled as required
    """
    RATE_DICT = dict(GBP=1.0, USD=0.60, KRW=0.00078, JPY=0.0038, EUR=0.66, CHF=0.66, AUD=0.55)

    if currency not in RATE_DICT:
        raise Exception("Don't have an fx rate for %s " % currency)

    rate_value = RATE_DICT[currency]

    print("Warning using approximate rate of %f for %s" % (rate_value, currency))

    return pd.Series([rate_value], index=[pd.datetime(2008, 1, 1)])
