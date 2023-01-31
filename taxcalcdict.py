"""
    Python UK trading tax calculator
    
    Copyright (C) 2015  Robert Carver
    
    You may copy, modify and redistribute this file as allowed in the license agreement 
         but you must retain this header
    
    See README.md

"""

import numpy as np
import sys
from tradelist import TradeList, TradeDictByCode
from utils import which_tax_year, star_line, pretty

from taxcalctradegroup import TaxCalcTradeGroup, zero_tax_tuple


class TaxCalcDict(dict):
    """
    A tax calc dict is constructed from a normal trade dict separated by code eg

    trade_dict_bycode=all_trades.separatecode()

    The structure is:
       dict, code keywords
           TaxCalcElement()
    """

    def __init__(self, tradedict):

        '''
        To set up the group we loop over the elements in the trade dict
        '''
        assert type(tradedict) is TradeDictByCode

        for code in tradedict.keys():
            self[code] = TaxCalcElement(tradedict[code])

    def allocate_dict_trades(self, CGTcalc=True):
        [taxelement.allocate_trades(CGTcalc) for taxelement in self.values()]

        return self

    def return_profits(self, taxyear, CGTCalc):
        codes = list(self.keys())
        codes.sort()
        elements_profits = dict([(code, self[code].return_profits_for_code(taxyear, CGTCalc)) for code in codes])
        return elements_profits

    def average_commission(self, taxyear):
        codes = list(self.keys())
        codes.sort()
        average_commissions = dict([(code, self[code].average_commission(taxyear)) for code in codes])

        return average_commissions

    def individual_profits(self, taxyear):
        codes = list(self.keys())
        codes.sort()
        profit_list = [self[code].individual_profits(taxyear) for code in codes]
        profit_list = sum(profit_list, [])

        return profit_list

    def win_loss_ratio_etc(self, tax_year):
        indi_profits = self.individual_profits(tax_year)
        wins = [x for x in indi_profits if x > 0]
        losses = [x for x in indi_profits if x < 0]

        avg_win = np.mean(wins)
        avg_loss = np.mean(losses)

        count_wins = len(wins)
        count_losses = len(losses)

        return avg_win, avg_loss, count_wins, count_losses

    def display_taxes(self, taxyear, CGTCalc, reportinglevel, report=None):
        """
        Run through each element, displaying the tax information in full

        Then print a summary
        """
        assert reportinglevel in ["VERBOSE", "CALCULATE", "NORMAL", "BRIEF", "ANNUAL"]

        if report is None:
            report = sys.stdout

        # Prints, and returns a tuple for each disposal_proceeds, allowable_costs, year_gains, year_losses,
        #        number_disposals, commissions, taxes, gross profit, net profit

        codes = list(self.keys())
        codes.sort()
        elements_taxdata = [self[code].display_taxes_for_code(taxyear, CGTCalc, reportinglevel, report) for code in
                            codes]

        if len(elements_taxdata) == 0:
            report.write(star_line())

            report.write("\n\nNo relevant trades for tax year %d\n\n" % taxyear)
            report.write(star_line())

            return None

        summary_taxdata = map(sum, zip(*elements_taxdata))
        summary_taxdata = list(summary_taxdata)

        assert len(summary_taxdata) == len(zero_tax_tuple)

        # print the summary (always regardless of reporting level)
        display_summary_tax(summary_taxdata, CGTCalc, taxyear, report)

        report.write(star_line())

        return None

    def tax_year_span(self):
        # Get unique list of tax years
        date_list = []

        for tax_element in self.values():
            closing_trade_dates = tax_element.closing_trade_dates()
            date_list.extend(closing_trade_dates)

        tax_years = [which_tax_year(datex) for datex in date_list]
        tax_years = list(set(tax_years))
        tax_years.sort()
        return tax_years


class TaxCalcElement(object):
    """
    A tax calc element is constructed from a normal trade list for one code eg.

    tradelist=all_trades.separatecode()['a code']

    The structure is:
       attributes: matched, unmatched
           matched: list of TaxCalcTradeGroup objects (begins as empty)

            unmatched: TradeList of all unmatched trades. Initially this inherits all the trades in tradelist
    """

    def __init__(self, trade_list):
        """
        To set up the group we populate unmatched and have an empty matched
        """
        assert type(trade_list) is TradeList
        assert trade_list.check_same_code() is True
        self.matched = {}
        self.unmatched = trade_list

    def __repr__(self):
        return "%s %d matched, %d unmatched" % (self.code(), len(self.matched), len(self.unmatched))

    def code(self):
        if len(self.matched) > 0:
            return self.matched.values()[0].closing_trade.Code
        elif len(self.unmatched) > 0:
            return self.unmatched[0].Code
        else:
            return ""

    def closing_trade_dates(self):
        closing_dates = [tax_calc_group.closing_trade.Date for tax_calc_group in self.matched.values()]
        return closing_dates

    def allocate_trades(self, CGTcalc):

        """
        One by one, push the closing trades (from earliest to latest) into matched

        Then match them
        """

        # Find, and pop,  next closing trade in unmatched list
        # This will be none if there aren't any
        # Then add to tax calc trade group

        num_trades = 1

        while True:
            earliest_closing_trade = self.unmatched.pop_earliest_closing_trade()

            if earliest_closing_trade is None:
                break

            # Now create the matched group. This will pop things out of self.allocated
            tax_calc_group = self.match_for_group(earliest_closing_trade, CGTcalc)

            self.matched[num_trades] = tax_calc_group

            num_trades = num_trades + 1

        if len(self.unmatched) > 0:

            if self.unmatched.final_position() == 0:
                # Now we've got rid of the closing trades, we're probably left with a bunch of opening trades

                # The last one of these must be a closer with a different sign, pretending to be
                #  an opener

                while len(self.unmatched) > 0:
                    # Make it into a closer, and then run a match

                    # get the last trade
                    self.unmatched.date_sort()

                    trade_to_match = self.unmatched.pop()
                    trade_to_match.modify(tradetype="Close")

                    tax_calc_group = self.match_for_group(trade_to_match, CGTcalc)
                    self.matched[num_trades] = tax_calc_group

                    num_trades = num_trades + 1

                assert len(self.unmatched) == 0

            else:
                # We've got positions remaining, which is fine
                pass

        return self

    def match_for_group(self, trade_to_match, CGTcalc):
        """
        Build up a tax calc trade group with trades that match the closing trade, which are popped out of self

        If you want to change the logic for how trades are matched, this is the place to do it

        """

        # Create the group initially with just
        tax_calc_group = TaxCalcTradeGroup(trade_to_match)

        if CGTcalc:

            # Same day
            while tax_calc_group.is_unmatched():

                tradeidx = self.unmatched.idx_of_last_trade_same_day(trade_to_match)
                if tradeidx is None:
                    break

                # Remove the trade (creating a partial if needed)
                popped_trade = self.unmatched.partial_pop_idx(tradeidx, tax_calc_group.count_unmatched())

                # Add to list
                tax_calc_group.same_day.append(popped_trade)

            # 30 day rule
            while tax_calc_group.is_unmatched():

                tradeidx = self.unmatched.idx_of_first_trade_next_30days(trade_to_match)
                if tradeidx is None:
                    break

                # Remove the trade (creating a partial if needed)
                popped_trade = self.unmatched.partial_pop_idx(tradeidx, tax_calc_group.count_unmatched())

                # Add to list
                tax_calc_group.within_month.append(popped_trade)

        # S104 (what we do without CGT calc, or what's left
        # This is a bit more complicated because we need to do a
        #            proportionate partial pop of all previous trades

        if tax_calc_group.is_unmatched():

            # Get all the previous trades
            tradeidxlist = self.unmatched.idx_of_trades_before_datetime(trade_to_match)

            if len(tradeidxlist) > 0:
                # Remove a proportion of all previous trades
                popped_trades = self.unmatched._proportionate_pop_idx(tradeidxlist, tax_calc_group.count_unmatched())

                # Add to list
                tax_calc_group.s104 = popped_trades

        if tax_calc_group.is_unmatched():
            print("Can't find a match for %d lots of ...:" % tax_calc_group.count_unmatched())
            print(tax_calc_group.closing_trade)
            raise Exception()

        return tax_calc_group

    def return_profits_for_code(self, taxyear, CGTCalc):
        # Returns a list of profits
        groupidlist = list(self.matched.keys())
        groupidlist.sort()

        # Last is always net p&l
        taxdata = [
            self.matched[groupid].group_display_taxes(taxyear, CGTCalc, reportinglevel="", groupid=groupid, report=None,
                                                      display=False)[-1] \
            for groupid in groupidlist]

        return taxdata

    def display_taxes_for_code(self, taxyear, CGTCalc, reportinglevel, report=None):
        # Prints, and returns a tuple for each disposal_proceeds, allowable_costs, year_gains, year_losses,
        #        number_disposals, commissions, taxes, gross profit, net profit

        groupidlist = list(self.matched.keys())
        groupidlist.sort()

        taxdata = [self.matched[groupid].group_display_taxes(taxyear, CGTCalc, reportinglevel, groupid, report) for
                   groupid in groupidlist]
        if len(taxdata) == 0:
            return zero_tax_tuple

        # Sum up the tuple, and return the sums
        sum_taxdata = map(sum, zip(*taxdata))
        sum_taxdata = list(sum_taxdata)
        assert len(sum_taxdata) == len(zero_tax_tuple)

        return sum_taxdata

    def average_commission(self, taxyear):
        # Returns the average commission
        groupidlist = list(self.matched.keys())
        groupidlist.sort()

        # Last is always net p&l
        taxdata = [self.matched[groupid].group_display_taxes(taxyear, CGTCalc=True, reportinglevel="", groupid=groupid,
                                                             report=None, display=False) \
                   for groupid in groupidlist]

        commissions = [x[5] for x in taxdata]
        quants = [x[8] for x in taxdata]

        total_comm = sum(commissions)
        total_quant = sum(quants)

        if total_quant == 0.0:
            if total_comm == 0:
                return np.nan
            else:
                return 0.0

        return total_comm / (2.0 * total_quant)

    def individual_profits(self, taxyear):
        # Returns the profits of each individual trade
        groupidlist = self.matched.keys()
        groupidlist.sort()

        # Last is always net p&l
        taxdata = [self.matched[groupid].group_display_taxes(taxyear, CGTCalc=True, reportinglevel="", groupid=groupid,
                                                             report=None, display=False) \
                   for groupid in groupidlist]

        profits = [x[9] for x in taxdata]

        return profits


def display_summary_tax(summary_taxdata, CGTCalc, taxyear, report):
    """
        taxdata contains a list of tuples
        # Each tuplue (gbp_disposal_proceeds, gbp_allowable_costs, gbp_gains, gbp_losses, number_disposals,
                commissions, taxes, gbp_gross_profit, gbp_net_profit)
    
        
        
        """

    # Unpack tuple
    (gbp_disposal_proceeds, gbp_allowable_costs, gbp_gains, gbp_losses, number_disposals,
     gbp_commissions, gbp_taxes, gbp_gross_profit, abs_quantity, gbp_net_profit) = summary_taxdata

    report.write(star_line())

    report.write("\n\n                Summary for tax year ending 5th April %d \n" % taxyear)
    report.write("\n                              Figures in GBP\n\n")

    if CGTCalc:
        report.write(
            "Disposal Proceeds = %s, Allowable Costs = %s, Disposals = %d \n Year Gains = %s  Year Losses = %s PROFIT = %s\n" % \
            (pretty(gbp_disposal_proceeds), pretty(gbp_allowable_costs),
             number_disposals, pretty(gbp_gains), pretty(gbp_losses), pretty(gbp_net_profit)))

    else:
        report.write("Gross trading profit %s, Commission paid %s, Taxes paid %s, Net profit %s\n" % \
                     (pretty(gbp_gross_profit), pretty(gbp_commissions),
                      pretty(gbp_taxes), pretty(gbp_net_profit)))

        report.write(
            "\nNot included: interest paid, interest received, data and other fees, internet connection,...\n hardware, software, books, subscriptions, office space, Dividend income (report seperately)\n\n")

    report.write("\n\n")
