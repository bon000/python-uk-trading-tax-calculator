"""
    Python UK trading tax calculator

    Copyright (C) 2015  Robert Carver

    You may copy, modify and redistribute this file as allowed in the license agreement
         but you must retain this header

    See README.md
"""
import yfinance as yf
import pandas as pd
import datetime


def get_prices_history(tickers, from_date, to_date, columns=['Close']):
    """
    Returns a DataFrame of prices for a list of tickers from Yahoo Finance API
    """
    prices = pd.DataFrame()

    for ticker in tickers:
        obj = yf.Ticker(ticker)
        ticker_prices = obj.history(start=from_date, end=to_date, interval="1d")[columns]

        if not ticker_prices.dropna().empty:
            prices = pd.concat([prices, ticker_prices], axis=1)
        else:
            print(f"{ticker} has no data!")
    return prices


def get_yfinance_fx_rates(currency, from_date, to_date):
    """
    Given a currency code eg USDAUD returns a pandas data frame with the YFINANCE price series

    Daily prices only
    """

    if currency == "GBP":
        # Return a pd of 1's from index to present day
        d_range = pd.date_range(from_date, to_date)
        data = pd.Series(1.0, index=d_range)
    else:
        data = get_prices_history(["GBP" + currency + "=X"], from_date, to_date)
        # prices.Close = prices.Close.dt.tz_localize('UTC').dt.tz_convert('Europe/London', errors='coerce')

    #print("FX Rates GBP to : " + currency)
    #print(data)
    return data
