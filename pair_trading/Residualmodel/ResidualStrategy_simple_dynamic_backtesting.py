from datetime import datetime
from vnpy.app.portfolio_strategy import BacktestingEngine
from vnpy.trader.constant import Interval
# from residualstrategy_simple import DynamicResidualModelStrategy
from simple_strategy_1_1 import DynamicResidualModelStrategy
# from residualstrategy_simple_with_moving_exit import DynamicResidualModelStrategy
# from trend_following_version1 import ATR_RSI_Strategy
# from portfolio_signals import TredningFollowingSignals
# from portfolio_masignals import MASignals
# from portfolio_macdsignals import MACDSignals


#%%
#
engine = BacktestingEngine()

engine.set_parameters(
    vt_symbols=["HC888.SHFE", 'RB888.SHFE'],
    interval=Interval.MINUTE,
    start=datetime(2014, 12, 31 ),
    end=datetime(2015,4, 1),
    rates={"HC888.SHFE": 5/10000, "RB888.SHFE": 5/10000},
    slippages={"HC888.SHFE":2, "RB888.SHFE": 1},
    sizes={"HC888.SHFE":10, "RB888.SHFE":10},
    priceticks={"HC888.SHFE":2, "RB888.SHFE":1},
    capital=1_000_0,
    collection_names={"HC888.SHFE":"HC888", "RB888.SHFE":"RB888"}

)
engine.add_strategy(DynamicResidualModelStrategy, {'profit_pct':1,'boll_up_cum_threshold':10 })
engine.load_data()
engine.run_backtesting()
df = engine.calculate_result()
engine.calculate_statistics()
engine.show_chart()
