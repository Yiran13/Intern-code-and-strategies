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

    # 退出条件
    hold_window: int = 100
    profit_point: float = 20
    exit_point: float = -5
    # profit_pct: float = 0.2
    # exit_pct: float = -0.06

    #轨道宽度
    entry_multiplier: float = 3
    price_add = 2
    
    # 指标计算参数
    std_window =  240*30
    std_mean_window_ratio = 1
    boll_up_cum_threshold = 10
 


    #固定下单单位
    fixed_size = 1

    #价差值
    spread_value: float = 0

    # 用来过滤交易量低的情况
    spread_volume_threshold = 20
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
    boll_up_cum = 0

    # 盈利记录
    last_long_trade_profit:bool = False
    last_short_trade_profit:bool = False

    parameters = [
        'entry_multiplier',
        "fixed_size",
        "std_window",
        'profit_point',
        'exit_point',
        'hold_window',
        'boll_up_cum_threshold'
    ]
    variables = ["x_multiplier","y_multiplier",'x_pos_target','y_pos_target',"spread_volume_filter"]

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


       
        self.short_entry_multiplier = abs(self.entry_multiplier)
        self.short_exit_multiplier = 0
        self.long_entry_multiplier =  -abs(self.entry_multiplier)
        self.long_exit_multiplier = 0

        self.mean_window = int(self.std_window * self.std_mean_window_ratio)

        

        self.y_symbol = self.vt_symbols[0]
        self.x_symbol = self.vt_symbols[1]


        self.x_fixed_size = np.abs(self.fixed_size * 1)
        self.y_fixed_size = np.abs(self.fixed_size * 1)

        self.x_pos_target = 0
        self.y_pos_target = 0




        # 实例化缓存期货品种价格序列容器
        for vt_symbol in self.vt_symbols:

            self.ams[vt_symbol] =  ArrayManager(size=max(self.std_window,self.mean_window)+50)

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

        self.load_bars(max(int(self.std_window/240),10))    

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



        # 计算价差
        # 将价差放入sam 进行后续技术指标计算
        self.spread_value = self.y_fixed_size*(bars[self.y_symbol].close_price) - self.x_fixed_size*(bars[self.x_symbol].close_price)
        self.spread_volume = min(bars[self.y_symbol].volume, bars[self.x_symbol].volume)
        self.sam.update_spread(self.spread_value, self.spread_volume)

        # 成交量过滤，成交量低于指定阈值将不会进行操作
        if self.spread_volume < self.spread_volume_threshold:
            self.spread_volume_filter = False
        else:
            self.spread_volume_filter = True

        if not self.sam.inited:
            return

        # 计算技术指标
        sam = self.sam
        std = sam.std(self.std_window)
        mean = sam.sma(self.mean_window)
        # 计算是否满足做多价差要求
        spread_long_entry = mean + self.long_entry_multiplier * std
        if self.spread_value > spread_long_entry: 
            self.boll_up_cum += 1
        else:
            self.boll_up_cum = 0

        
       
        # 获取每个品种持仓
        self.x_pos = self.get_pos(self.x_symbol)
        self.y_pos = self.get_pos(self.y_symbol)

        if self.x_pos == 0 and self.y_pos == 0:
            # 多开
            if  self.boll_up_cum>self.boll_up_cum_threshold and self.spread_value >= self.spread_long_entry and self.spread_volume_filter:
                self.y_pos_target = self.y_fixed_size
                self.x_pos_target = -self.x_fixed_size

                self.hold_time = 0
                self.start_order = True
                self.boll_up_cum = 0
                # print(self.spread_long_loss_exit,self.spread_long_profit_exit,self.difference_exit_num,self.spread_value - self.difference_exit_num)
                print(f'时间{bars[self.y_symbol].datetime}','多开   ',f'多{self.y_symbol} {self.y_fixed_size} 手 空{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')
            else:
                self.start_order = False
                return
            
                
        elif self.y_pos > 0 and self.x_pos < 0 :
            self.boll_up_cum = 0
            if self.start_order:
                # 近似实际开仓价格
                # self.spread_long_profit_exit = self.spread_value*(1+self.profit_pct)
                self.spread_long_profit_exit = self.spread_value+self.profit_point
                # self.spread_long_loss_exit = self.spread_value*(1+self.exit_pct)
                self.spread_long_loss_exit = self.spread_value+self.exit_point
                self.start_order = False

            # 持仓周期计算
            if self.hold_time < self.hold_window:
                self.hold_time += 1
            elif self.hold_time >= self.hold_window:

                self.y_pos_target = 0
                self.x_pos_target = 0
                self.last_long_trade_profit = None
                
                print(f'时间{bars[self.y_symbol].datetime}','多平 超出持仓时间',f'平多{self.y_symbol} {self.y_fixed_size} 手 平空{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value} {self.hold_time} {self.profit_point}') 
                self.hold_time = 0
            # 多平止盈
            if self.spread_value >= self.spread_long_profit_exit:
                self.y_pos_target = 0
                self.x_pos_target = 0
                self.last_long_trade_profit = True
                self.hold_time = 0
                print(f'时间{bars[self.y_symbol].datetime}','多平 止盈',f'平多{self.y_symbol} {self.y_fixed_size} 手 平空{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')
            # 多平止损
            
            elif self.spread_value <= self.spread_long_loss_exit:
                self.y_pos_target = 0
                self.x_pos_target = 0
                self.last_long_trade_profit = False
                self.hold_time = 0
                print(f'时间{bars[self.y_symbol].datetime}','多平 止损',f'平多{self.y_symbol} {self.y_fixed_size} 手 平空{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')
       

               


        target = {self.x_symbol:self.x_pos_target,
        self.y_symbol:self.y_pos_target}
        for vt_symbol in self.vt_symbols:

            target_pos = target[vt_symbol]
            current_pos = self.get_pos(vt_symbol)

            pos_diff = target_pos - current_pos
            volume = abs(pos_diff)
            bar = bars[vt_symbol]

            if pos_diff > 0:
                price = bar.close_price + self.price_add

                if current_pos < 0:
                    self.cover(vt_symbol, price, volume)
                else:
                    self.buy(vt_symbol, price, volume)
                    
            elif pos_diff < 0:
                price = bar.close_price - self.price_add

                if current_pos > 0:
                    self.sell(vt_symbol, price, volume)
                else:
                    self.short(vt_symbol, price, volume)

    