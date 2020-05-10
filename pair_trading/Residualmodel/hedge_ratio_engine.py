from vnpy.app.portfolio_strategy.backtesting import load_bar_data
from typing import Dict, List, Tuple
from datetime import datetime,timedelta
from vnpy.trader.utility import extract_vt_symbol
from vnpy.trader.constant import Interval
import pandas as pd
import numpy as np
from hedge_ratio import calulate_hedge_ratio
import statsmodels.tsa.stattools as ts

class hedge_ratio_engine:

    def __init__(self,symbols:List[str], collections:Dict[str,str], interval:Interval = Interval.MINUTE, coint_p_value_threshold:float = 0.10):
        self.symbols = symbols
        self.collections = collections 
        self.interval = Interval
        
        self.coint_p_value_threshold = coint_p_value_threshold

        self.y_symbol = symbols[0]
        self.y_collection = collections[self.y_symbol]

        self.x_symbol = symbols[1]
        self.x_collection = collections[self.x_symbol]


        self.interval = Interval.MINUTE

        self.in_sample_start: datetime = None
        self.in_sample_end: datetime = None
        self.in_sample_period: timedelta = None

        self.out_of_sample_start: datetime = None
        self.out_of_sample_end: datetime = None
        self.out_of_sample_period: timedelta = None
        self.calulate_hedge_ratio: calulate_hedge_ratio = None
        
        # 缓存OLS的结果,对于hedge_ratio是小数的情况，需要对hedge_ratio进行扩大
        self.hedge_ratio: float = None
        self.intercept: float = None
        self.multiplier: int = None
        self.multiplier_hedge_ratio: int = None
        self.mulitipler_intecept: float = None

        # 缓存coint_test的p_value
        self.coint_p_value: float = None
        
        # 缓存 in_sample 和 out_sample相关数据为后续回测和检查是否使用未来数据做准备
        self.in_sample_recorder:List[Tuple] = []
        self.out_sample_recorder:List[Tuple] = []
        
    
    def in_sample_dates(self,start:datetime,sample_days:int):
        """
        generate the sample dates based on the given start date and the numer of sample days
        """
        self.in_sample_period = timedelta(days=sample_days)
        self.in_sample_start = start
        self.in_sample_end = self.in_sample_start + self.in_sample_period
    
    def out_of_sample_dates(self,start:datetime, out_sample_days:int):
        """
        generate the out of sample dates based on the given start date and the numer of out_sample days
        
        To be simple, we just assuming the start date of out_of_sample dates equals to the end date of in_sample
        dates
        """
        self.out_of_sample_period = timedelta(days=out_sample_days)
        self.out_of_sample_start = start
        self.out_of_sample_end = self.out_of_sample_start + self.out_of_sample_period

    def generate_in_out_sample_dates(self,orignal_start:datetime,backtesting_end: datetime, in_sample_days:int=90, out_of_sample_days:int=30):
        start = orignal_start
        while start + timedelta(days=in_sample_days) + timedelta(days=out_of_sample_days) <= backtesting_end:
            self.in_sample_dates(start=start, sample_days=in_sample_days)
            self.out_of_sample_dates(start=self.in_sample_end, out_sample_days=out_of_sample_days)

            print(f'in_sample_start:{self.in_sample_start}\nin_sample_end:{self.in_sample_end}\n')

            self.calulate_hedge_ratio = calulate_hedge_ratio(symbols=self.symbols,collections=self.collections,start=self.in_sample_start,end=self.in_sample_end,interval=self.interval)
            self.calulate_hedge_ratio.get_hege_ratio()
            self.hedge_ratio = self.calulate_hedge_ratio.hedge_ratio
            self.intercept = self.calulate_hedge_ratio.intercept
            self.calculate_coint_p_value()
            if self.coint_p_value < self.coint_p_value_threshold:
                for n in range(10):
                    self.multiplier_hedge_ratio = n*self.hedge_ratio
                    self.mulitipler_intecept = n*self.intercept
                    if int(self.multiplier_hedge_ratio) >=1:
                        print('the result in in_sample_period:', n, self.multiplier_hedge_ratio,self.mulitipler_intecept)
                        print(f'coint_p_value is：{self.coint_p_value}')
                        self.multiplier = n

                    
                        out_sample_record = (self.out_of_sample_start,self.out_of_sample_end, self.multiplier_hedge_ratio, self.multiplier,self.mulitipler_intecept)
                        self.out_sample_recorder.append(out_sample_record)
                        
                        in_sample_record = (self.in_sample_start, self.in_sample_end)
                        self.in_sample_recorder.append(in_sample_record)

                        print('p-value is less than the threshold,the strategy can be run in the next month')


                        break
            print(f'out_sample_start:{self.out_of_sample_start}\nout_of_sample_end:{self.out_of_sample_end}')
            # start = start + timedelta(days=in_sample_days) + timedelta(days=out_of_sample_days)
            start = self.out_of_sample_end-timedelta(days=in_sample_days)
        
    def calculate_coint_p_value(self):
        """
        monitor if the residul obtained by the ols method is stationary or not 
        """
        ols_model = self.calulate_hedge_ratio.ols_model
        self.coint_p_value = ts.adfuller(ols_model.resid,autolag='BIC')[1]
        
           
        
if __name__ == '__main__':

    HC_RB = hedge_ratio_engine(symbols=['HC888.SHFE','RB888.SHFE'],
    collections={"HC888.SHFE":"HC888", "RB888.SHFE":"RB888"})
    HC_RB.generate_in_out_sample_dates(orignal_start=datetime(2019,1,17),backtesting_end=datetime(2020,1,30))
    print(HC_RB.out_sample_recorder)
    print(HC_RB.in_sample_recorder)
    
    #end=datetime(2019,3,30)

        
      

   
    

    
