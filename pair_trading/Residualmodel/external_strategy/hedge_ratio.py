from vnpy.app.portfolio_strategy.backtesting import load_bar_data
from typing import Dict, List
from datetime import datetime
from vnpy.trader.utility import extract_vt_symbol
from vnpy.trader.constant import Interval
import statsmodels.api as sm
import statsmodels.tsa.stattools as ts
import statsmodels.regression.linear_model as srl
import pandas as pd
import numpy as np


class calulate_hedge_ratio:

    def __init__(self,symbols:List[str], collections:Dict[str,str], start:datetime, end:datetime, interval:Interval = Interval.MINUTE):
        """
        set the time period used to calculate the hedge ratio
        """
        self.y_symbol = symbols[0]
        self.y_collection = collections[self.y_symbol]

        self.x_symbol = symbols[1]
        self.x_collection = collections[self.x_symbol]

        self.start = start
        self.end = end
        self.interval = Interval.MINUTE
        
        self.combine_data: pd.DataFrame = pd.DataFrame()

        self.hedge_ratio: float = None
        self.intercept: float = None
        self.ols_model:srl.RegressionResultsWrapper = None
    
    def load_symbol_data(self,symbol:str,collection_name:str):

        """ 
        load bar data of one symbol 
        """
        close_list: List = []
        datetime_list: List = []
        # volume_list: List = []
        symbol_df:pd.DataFrame = pd.DataFrame()

        bars = load_bar_data(vt_symbol=symbol, interval=self.interval, start=self.start, end=self.end, collection_name=collection_name)
   
        for bar in bars:

            close = bar.close_price
            datetime = bar.datetime
            # volume = bar.volume

            close_list.append(close)
            datetime_list.append(datetime)
            # volume_list.append(volume)
        
        symbol_df = pd.DataFrame({symbol:close_list},index=datetime_list)
    
        return symbol_df
    
    def load_symbols_data(self):

        """
        
        """

        y_symbol_data:pd.DataFrame = self.load_symbol_data(symbol=self.y_symbol, collection_name=self.y_collection)
        x_symbol_data:pd.DataFrame = self.load_symbol_data(symbol=self.x_symbol, collection_name=self.x_collection)
        
        self.combine_data:pd.DataFrame = pd.concat([y_symbol_data,x_symbol_data],axis=1)

    
    def get_ols_result(self):
        """
        calculate the hedge ratio by using the OLS method

        y = a*x + b
        """
        X = self.combine_data[self.x_symbol]
        X = sm.add_constant(X)
        y = self.combine_data[self.y_symbol]
        result = sm.OLS(y,X).fit()

        self.hedge_ratio = result.params[1]
        self.intercept = result.params[0]
        self.ols_model = result

        

    
    def get_hege_ratio(self):

        self.load_symbols_data()
        self.get_ols_result()


if __name__ == "__main__":
    HC_RB = calulate_hedge_ratio(symbols=['HC888.SHFE','RB888.SHFE'],
    collections={"HC888.SHFE":"HC888", "RB888.SHFE":"RB888"},
    start=datetime(2019,1,30),
    end=datetime(2019,3,30))
    HC_RB.get_hege_ratio()
    # HC_RB.load_symbols_data()
    # print(HC_RB.combine_data)
    print(f'Hedge ratio：{HC_RB.hedge_ratio};\n Intercept:{HC_RB.intercept}')
    print(HC_RB.ols_model.summary())

    hedge_ratio = HC_RB.hedge_ratio
    intercept = HC_RB.intercept
    
    #针对hedge ratio <1的情况，进行倍数的放缩,要求至少要买满一手
    for n in range(10):
        multiplier_hedge_ratio = int(n*hedge_ratio)
        mulitipler_intecept = int(n*intercept)
        if multiplier_hedge_ratio >=1:
            print(n,multiplier_hedge_ratio,mulitipler_intecept)
            break


        

    

   
