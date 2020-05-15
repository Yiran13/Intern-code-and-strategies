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
        self.renew_hedge_ratio(bars[self.y_symbol])


        # 计算价差
        # 将价差放入sam 进行后续技术指标计算
        self.spread_value = self.y_fixed_size*(bars[self.y_symbol].close_price) - self.x_fixed_size*(bars[self.x_symbol].close_price) - self.intercept
        self.spread_volume = min(bars[self.y_symbol].volume, bars[self.x_symbol].volume)
        self.sam.update_spread(self.spread_value, self.spread_volume)
        self.spread_record.append(self.spread_value)
        self.datetime_record.append(bars[self.y_symbol].datetime)
        # print(bars[self.y_symbol].datetime,self.spread_value)

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
        spred_long_exit = mean + self.long_exit_multiplier * std
        # 计算是否满足作空价差要求
        spread_short_entry = mean + self.short_entry_multiplier * std
        spread_short_exit = mean + self.short_exit_multiplier * std
        # 预期收益筛选
        if np.abs(spread_long_entry - spred_long_exit) >= self.difference_filter_num:
            self.spread_long_entry = spread_long_entry
            # self.spread_long_exit = spred_long_exit
        else:
            self.spread_long_entry = None
        # 预期收益筛选
        if np.abs(spread_short_entry - spread_short_exit) >= self.difference_filter_num:
            self.spread_short_enrtry = spread_short_entry
            #  self.spread_short_exit = spred_short_exit
        else:
            self.spread_short_enrtry = None
        # 上笔亏损过滤
        if not self.last_long_trade_profit:
            self.spread_long_entry  = None
            self.last_long_trade_profit = True
        elif not self.last_short_trade_profit:
            self.spread_short_enrtry = None
            self.last_short_trade_profit = True

       
        # 获取每个品种持仓
        self.x_pos = self.get_pos(self.x_symbol)
        self.y_pos = self.get_pos(self.y_symbol)

        if self.x_pos == 0 and self.y_pos == 0:
            # 多开
            if self.spread_long_entry and self.spread_value <= self.spread_long_entry and self.spread_volume_filter:
                self.y_pos_target = self.y_fixed_size
                self.x_pos_target = -self.x_fixed_size
                self.spread_long_profit_exit = mean + self.long_exit_multiplier * std
                self.spread_long_loss_exit = self.spread_value - self.difference_exit_num
                # print(self.spread_long_loss_exit,self.spread_long_profit_exit,self.difference_exit_num,self.spread_value - self.difference_exit_num)
                # print(f'时间{bars[self.y_symbol].datetime}','多开   ',f'多{self.y_symbol} {self.y_fixed_size} 手 空{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')
            
            # 空开
            elif  self.spread_short_entry and self.spread_value >= self.spread_short_entry and self.spread_volume_filter:
                self.y_pos_target = -self.y_fixed_size
                self.x_pos_target = self.x_fixed_size
                self.spread_short_profit_exit = mean + self.short_exit_multiplier * std
                self.spread_short_loss_exit = self.spread_value + self.difference_exit_num
                # print(self.spread_short_loss_exit,self.spread_short_profit_exit)
                # print(f'时间{bars[self.y_symbol].datetime}','空开   ',f'空{self.y_symbol} {self.y_fixed_size} 手 多{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')
                
        elif self.y_pos > 0 and self.x_pos < 0 :
            # 多平止盈
            if self.spread_value >= self.spread_long_profit_exit:
                self.y_pos_target = 0
                self.x_pos_target = 0
                self.last_long_trade_profit = True
                # print(f'时间{bars[self.y_symbol].datetime}','多平 止盈',f'平多{self.y_symbol} {self.y_fixed_size} 手 平空{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')
            # 多平止损
            
            elif self.spread_value <= self.spread_long_loss_exit:
                self.y_pos_target = 0
                self.x_pos_target = 0
                self.last_long_trade_profit = False
                # print(f'时间{bars[self.y_symbol].datetime}','多平 止损',f'平多{self.y_symbol} {self.y_fixed_size} 手 平空{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')
             # 多平调参
            
            elif self.renew_status:
                self.y_pos_target = 0
                self.x_pos_target = 0
                # print(f'时间{bars[self.y_symbol].datetime}','多平 调参',f'平多{self.y_symbol} {self.y_fixed_size} 手 平空{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')

        elif self.y_pos < 0 and self.x_pos > 0:

            if self.spread_value <= self.spread_short_profit_exit:
                self.y_pos_target = 0
                self.x_pos_target = 0 
                self.last_short_trade_profit = True
                # print(f'时间{bars[self.y_symbol].datetime}','空平 止盈',f'平空{self.y_symbol} {self.y_fixed_size} 手 平多{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')
            
            elif self.spread_value >= self.spread_short_loss_exit:
                self.y_pos_target = 0
                self.x_pos_target = 0 
                self.last_short_trade_profit = False
                # print(f'时间{bars[self.y_symbol].datetime}','空平 止损',f'平空{self.y_symbol} {self.y_fixed_size} 手 平多{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')
            
            elif self.renew_status:
                self.y_pos_target = 0
                self.x_pos_target = 0 
                # print(f'时间{bars[self.y_symbol].datetime}','空平 调参',f'平空{self.y_symbol} {self.y_fixed_size} 手 平多{self.x_symbol} {self.x_fixed_size} 手',f'价差{self.spread_value}')


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

    def renew_hedge_ratio(self,bar:BarData):
        """
        renew the hedge ratio
        based on the passed days including the not trading days.

        """
        # 计算动态调参时间
        if not self.last_renew_date:

            self.last_renew_date = bar.datetime
            self.renew_date = self.last_renew_date + timedelta(days=self.renew_interval)
            return


        # 动态调参时间
        if bar.datetime >=  self.renew_date:
            self.last_renew_date = bar.datetime
            self.renew_date = self.last_renew_date + timedelta(days=self.renew_interval)

            X = self.ams[self.x_symbol].close[-self.hedge_ratio_window:]
            
            y = self.ams[self.y_symbol].close[-self.hedge_ratio_window:]

            result = sm.OLS(y,X).fit()
            hedge_ratio = result.params
            intercept = 0
            for n in range(10):
                    mulitiplier_x = n*hedge_ratio
                    mulitipler_intercept = n*intercept
                    mulitipler = n
                    if int(mulitiplier_x) >=1:
                        if hedge_ratio*self.x_multiplier < 0:

                            print('warning ! the hedge ratio direction is changed  ')

                        self.x_multiplier = mulitiplier_x
                        self.y_multiplier = mulitipler
                        self.intercept = mulitipler_intercept
                        self.x_fixed_size = int(np.abs(self.fixed_size * self.x_multiplier))
                        self.y_fixed_size = int(np.abs(self.fixed_size * self.y_multiplier))
                    #　可以加入历史协整测试
                        break
            self.renew_status = True
        else:
            self.renew_status = False
