
from datetime import datetime
from vnpy.app.portfolio_strategy import BacktestingEngine
from vnpy.trader.constant import Interval
from z_score import ZscoreStrategy

engine = BacktestingEngine()

engine.set_parameters(
    vt_symbols=["HC888.SHFE", 'RB888.SHFE'],
    interval=Interval.MINUTE,
    start=datetime(2019, 3, 1 ),
    end=datetime(2019, 10, 1),
    rates={"HC888.SHFE": 5/10000, "RB888.SHFE": 5/10000},
    slippages={"HC888.SHFE":1, "RB888.SHFE": 0.5},
    sizes={"HC888.SHFE":10, "RB888.SHFE":10},
    priceticks={"HC888.SHFE":2, "RB888.SHFE":1},
    capital=1_000_0,
    collection_names={"HC888.SHFE":"HC888", "RB888.SHFE":"RB888"}

)
engine.add_strategy(ZscoreStrategy, {})
engine.load_data()
engine.run_backtesting()
df = engine.calculate_result()
engine.calculate_statistics()
engine.show_chart()
