
from datetime import datetime
from vnpy.app.portfolio_strategy import BacktestingEngine
from vnpy.trader.constant import Interval
from z_score import ZscoreStrategy

engine = BacktestingEngine()

engine.set_parameters(
    vt_symbols=["Y888.DCE", 'P888.DCE'],
    interval=Interval.MINUTE,
    start=datetime(2019, 1, 1 ),
    end=datetime(2019, 6, 30),
    rates={"Y888.DCE": 3/10000, "P888.DCE": 3/10000},
    slippages={"Y888.DCE":0.2, "P888.DCE": 0.2},
    sizes={"Y888.DCE":10, "P888.DCE":10},
    priceticks={"Y888.DCE":2, "P888.DCE":2},
    capital=1_000_00,
    collection_names={"Y888.DCE":"Y888", "P888.DCE":"P888"}

)
engine.add_strategy(ZscoreStrategy, {})
engine.load_data()
engine.run_backtesting()
df = engine.calculate_result()
engine.calculate_statistics()
engine.show_chart()
