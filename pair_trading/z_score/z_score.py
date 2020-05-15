from typing import List, Dict

from vnpy.app.portfolio_strategy import StrategyTemplate, StrategyEngine
from vnpy.trader.utility import BarGenerator, ArrayManager
from vnpy.trader.object import TickData, BarData
from vnpy.trader.constant import Interval
import numpy as np
import pandas as pd
import statsmodels.formula.api as sml


class ZscoreStrategy(StrategyTemplate):
    """"""

    author = "ruonan yiran"

    bar_interval = 5
    bar_frequency = Interval.MINUTE

    fixed_size1 = 1
    fixed_size2 = 1
    boll_dev = 3.5
    spread_window = 100

    df = []
    mean = []
    std = []
    spread = []

    boll_up = 0
    boll_down = 0
    boll_mean = 0
    boll_std = 0
    spread = 0
    zscore = 0
    spread_mean = 0
    spread_std = 0
    spread_value = 0

    parameters = [
        "boll_dev",
        "fixed_size1",
        "fixed_size2",
        "spread_window",
    ]

    variables = [
        "boll_up",
        "boll_down",
        "boll_mean",
        "boll_std",
        "spread",
        "zscore",
        "spread_mean",
        "spread_std",
        "spread_value"
    ]

    def __init__(
        self,
        strategy_engine: StrategyEngine,
        strategy_name: str,
        vt_symbols: List[str],
        setting: dict
    ):
        """"""
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)

        # 单品种K线合成class
        self.bars = {}
        for vt_symbol in self.vt_symbols:
            self.bars[vt_symbol] = Single_bar(self,vt_symbol)

        self.y_symbol = vt_symbols[0]
        self.x_symbol = vt_symbols[1]
        
        
        # 单品种K线获取接口
        self.am1 = self.bars[self.y_symbol].am
        self.am2 = self.bars[self.x_symbol].am
        
        # 用来计算是否合成了一根bar
    
        self.bar_count = 1 

    
        self.df = []
        self.mean = []
        self.std = []
        self.spread = []

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        self.load_bars(10)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")
    
    def on_bars(self, bars: Dict[str, BarData]):
        """"""
        # 更新1分钟k线
        for vt_symbol in bars:
            
            self.bars[vt_symbol].on_bar(bars[vt_symbol])

        y_bar_count = self.bars[self.y_symbol].bar_count
        x_bar_count = self.bars[self.x_symbol].bar_count
        
        #　判断逻辑
        if self.bar_count == y_bar_count and self.bar_count == x_bar_count:
            self.bar_count += 1
            self.on_5min_bars(bars)
            

        


    def on_5min_bars(self, bars: Dict[str, BarData]):
        """"""
        self.cancel_all()
       
        am1 = self.am1
        am2 = self.am2

        bar1 = bars[self.y_symbol]
        bar2 = bars[self.x_symbol]

        if not am1.inited or not am2.inited:
            return
        

        self.df = pd.concat([pd.Series(am1.close),pd.Series(am2.close)], axis=1).dropna()
        self.df.columns = [self.y_symbol.split('.')[0],self.x_symbol.split('.')[0]]

        model = sml.ols(formula='%s ~ %s'%(self.df.columns[0],self.df.columns[1]), data = self.df)
        result=model.fit()

        self.spread_array = result.resid
        self.spread.append(self.spread_array[1])
        self.spread_value = self.spread[-1]

        self.spread_mean = self.spread_array[-self.spread_window:].mean()
        self.mean.append(self.spread_mean)
        self.boll_mean = self.mean[-1]

        self.spread_std = self.spread_array[-self.spread_window:].std()
        self.std.append(self.spread_std)
        self.boll_std = self.std[-1]

        self.zscore = self.spread_value - self.boll_mean/self.boll_std

        self.boll_up = self.boll_mean + self.boll_std * self.boll_dev
        self.boll_down = self.boll_mean - self.boll_std * self.boll_dev     

        y_pos = self.get_pos(self.y_symbol)
        x_pos = self.get_pos(self.x_symbol)

        if y_pos == 0 and x_pos == 0:

            if self.zscore > self.boll_up:

                self.buy(self.y_symbol, bar1.close_price + 5, self.fixed_size1)
                self.short(self.x_symbol, bar2.close_price - 5, self.fixed_size2)

            if self.zscore < self.boll_down:

                self.buy(self.x_symbol, bar2.close_price + 5, self.fixed_size2)
                self.short(self.y_symbol, bar1.close_price - 5, self.fixed_size1) 

        elif y_pos > 0:
            if self.zscore <= self.boll_mean:
                self.sell(self.y_symbol, bar1.close_price - 5, abs(y_pos))  
                self.cover(self.x_symbol, bar2.close_price + 5, abs(x_pos)) 

        elif y_pos < 0:

            if self.zscore >= self.boll_mean:
                self.cover(self.y_symbol, bar1.close_price + 5, abs(y_pos))
                self.sell(self.x_symbol, bar2.close_price - 5, abs(x_pos)) 

        self.put_event()
    



class Single_bar:
    
    """
    用来生成单品种的K线
    
    """

    def __init__(self, strategy:StrategyTemplate, vt_symbol:str):
        """"""
        # 和portfolio的接口
        self.portfolio= strategy
        self.vt_symbol = vt_symbol
        
        # 需要合成的K线周期设置
        self.bar_interval = self.portfolio.bar_interval
        self.bar_frequency = self.portfolio.bar_frequency


        # K线合成工具和储存容器
        self.bg = BarGenerator(self.on_bar, self.bar_interval, self.on_5min_bar,self.bar_frequency)
        self.am = ArrayManager()
        
        # K线合成计数
        self.bar_count  = 0


    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

    def on_5min_bar(self, bar: BarData):
        """"""
        self.bar_count += 1
        self.am.update_bar(bar)


        

