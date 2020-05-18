from typing import List, Dict, Union,Tuple
from vnpy.trader.constant import Interval
from vnpy.app.portfolio_strategy import StrategyTemplate, StrategyEngine
from vnpy.trader.utility import BarGenerator, ArrayManager
from vnpy.trader.object import TickData, BarData
from vnpy.app.cta_strategy import (
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
    SpreadArrayManager,
    CtaSignal,
    TargetPosTemplate
)
import numpy as np
import talib
from datetime import datetime, timedelta
import statsmodels.tsa.stattools as ts
import statsmodels.api as sm

class DynamicResidualModelStrategy(StrategyTemplate):
    """"""

    author = "yiran"

    x_symbol: str = None
    y_symbol: str = None
    # 策略内动态调整周期
    # 天数
    renew_interval: int = 7
    # 分钟线数据，90天约等于90*240
    hedge_ratio_window: int = 240

    #轨道宽度
    entry_multiplier: float = 3
    price_add = 5
    # 预期价差盈利
    difference_filter_num: float = 50
    difference_exit_rato: float =  1
    # 预期止盈为预期价差盈利的1/2
    # 指标计算参数
    std_window =  240
    std_mean_window_ratio = 0.5


    #固定下单单位
    fixed_size = 1

    #价差值
    spread_value: float = 0

    # 用来过滤交易量低的情况
    spread_volume_threshold = 0
    spread_volume: float = 0
    spread_volume_filter: bool = False

    # 进场，出场点位的缓存
    spread_long_entry: float = 0
    spread_long_exit: float = 0
    spread_long_loss_exit: float = 0

    spread_short_entry: float = 0
    spread_short_exit: float = 0
    spread_short_loss_exit: float =0

    #用来判断操作价差的方向
    open_direction_dict: Dict[str, float] = {}
    close_direction_dict: Dict[str, float] = {}

    # 用来进行参数更新判断
    last_renew_date: datetime = None
    renew_date: datetime = None
    renew_status: bool = False

    # 盈利记录
    last_long_trade_profit:bool = False
    last_short_trade_profit:bool = False

    parameters = [
        "renew_interval",
        "hedge_ratio_window",
        'entry_multiplier',
        "fixed_size",
        "std_window",
        "difference_filter_num"
    ]
    variables = ["x_multiplier","y_multiplier",'x_pos_target','y_pos_target',"spread_volume_filter"]
    spread_record = []
    datetime_record = []
    volume_record = []


    def __init__(
        self,
        strategy_engine: StrategyEngine,
        strategy_name: str,
        vt_symbols: List[str],
        setting: dict
    ):
        """"""
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        
        self.last_tick_time: datetime = None
        self.ams:Dict[str, ArrayManager] = {}
        self.bgs: Dict[str, BarGenerator] = {}

        # 策略内动态调整OLS相关参数,小数参数会被int（）
        self.x_multiplier = 0
        self.y_multiplier = 1

        # 不考虑intercept
        self.intercept = 0

       
        self.short_entry_multiplier = abs(self.entry_multiplier)
        self.short_exit_multiplier = 0
        self.long_entry_multiplier =  -abs(self.entry_multiplier)
        self.long_exit_multiplier = 0

        self.mean_window = int(self.std_window * self.std_mean_window_ratio)

        self.difference_exit_num = self.difference_filter_num * self.difference_exit_rato

        self.y_symbol = self.vt_symbols[0]
        self.x_symbol = self.vt_symbols[1]


        self.x_fixed_size = np.abs(self.fixed_size * self.x_multiplier)
        self.y_fixed_size = np.abs(self.fixed_size * self.y_multiplier)

        self.x_pos_target = 0
        self.y_pos_target = 0
        self.spread_record = []
        self.datetime_record = []
        self.volume_record = []




        # 实例化缓存期货品种价格序列容器
        for vt_symbol in self.vt_symbols:

            self.ams[vt_symbol] =  ArrayManager(size=self.hedge_ratio_window + 50)

        #实例化bg容器
        

        for vt_symbol in self.vt_symbols:

            def on_bar(bar: BarData):
                """"""
                pass

            self.bgs[vt_symbol] = BarGenerator(on_bar)


        # 实例化缓存价差价格序列容器
        self.sam = SpreadArrayManager(size=max(self.std_window,self.mean_window)+50)



    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        self.load_bars(20)

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

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        if (
            self.last_tick_time
            and self.last_tick_time.minute != tick.datetime.minute
        ):
            bars = {}
            for vt_symbol, bg in self.bgs.items():
                bars[vt_symbol] = bg.generate()
            self.on_bars(bars)

        bg: BarGenerator = self.bgs[tick.vt_symbol]
        bg.update_tick(tick)

        self.last_tick_time = tick.datetime


    def on_bars(self, bars: Dict[str, BarData]):
        """"""
        self.cancel_all()

        
        # OLS动态线性回归，需要缓存close_array
        
        self.ams[self.y_symbol].update_bar(bars[self.y_symbol])
        self.ams[self.x_symbol].update_bar(bars[self.x_symbol])
        # 动态线性回归函数
     


        # 计算价差
        # 将价差放入sam 进行后续技术指标计算
        self.spread_value =(bars[self.y_symbol].close_price) - (bars[self.x_symbol].close_price) 
        self.spread_volume = min(bars[self.y_symbol].volume, bars[self.x_symbol].volume)
        self.sam.update_spread(self.spread_value, self.spread_volume)
        self.spread_record.append(self.spread_value)
        self.datetime_record.append(bars[self.y_symbol].datetime)
        self.volume_record.append(min(bars[self.y_symbol].volume,bars[self.x_symbol].volume)) 
    