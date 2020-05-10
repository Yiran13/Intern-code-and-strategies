
from vnpy.app.portfolio_strategy import BacktestingEngine
from vnpy.app.portfolio_strategy.template import StrategyTemplate
from typing import Dict,List
from vnpy.trader.constant import (Direction, Offset, Exchange,
                                  Interval, Status)
from datetime import datetime
from residualmodel_dynamic import DynamicResidualModelStrategy
import multiprocessing
from itertools import product
import pandas as pd


def optimize(
    target_name: str,
    strategy_class: StrategyTemplate,
    setting: dict,
    vt_symbols: List[str],
    interval: Interval,
    start: datetime,
    rates: Dict[str,float],
    slippages: Dict[str,float],
    sizes: Dict[str,int],
    priceticks: Dict[str,float],
    capital: int,
    end: datetime,
    collection_names:Dict[str,str]
):
    """
    Function for running in multiprocessing.pool
    """
    engine = BacktestingEngine()

    engine.set_parameters(
        vt_symbols=vt_symbols,
        interval=interval,
        start=start,
        rates=rates,
        slippages=slippages,
        sizes=sizes,
        priceticks=priceticks,
        capital=capital,
        end=end,
        collection_names=collection_names
    )

    engine.add_strategy(strategy_class, setting)
    engine.load_data()
    engine.run_backtesting()
    engine.calculate_result()
    statistics = engine.calculate_statistics(output=False)

    target_value = statistics[target_name]
    return (str(setting), target_value, statistics)


def run_optimization(strategy_settings:dict,
            target_name:str,
            parameter_pool: list,
            output=True):

            # Get optimization setting and target
            settings = parameter_pool
            target_name = target_name

            # Use multiprocessing pool for running backtesting with different setting
            # Force to use spawn method to create new process (instead of fork on
            # Linux)

            ctx = multiprocessing.get_context("spawn")
            pool = ctx.Pool(multiprocessing.cpu_count())

            results = []
            for setting in settings:
                result = (pool.apply_async(optimize, (
                    target_name,
                    strategy_settings['strategy_class'],
                    setting,
                    strategy_settings['vt_symbols'],
                    strategy_settings['interval'],
                    strategy_settings['start'],
                    strategy_settings['rates'],
                    strategy_settings['slippages'],
                    strategy_settings['sizes'],
                    strategy_settings['priceticks'],
                    strategy_settings['capital'],
                    strategy_settings['end'],
                    strategy_settings['collection_names']
                )))
                results.append(result)

            pool.close()
            pool.join()

            # Sort results and output
            result_values = [result.get() for result in results]
            result_values.sort(reverse=True, key=lambda result: result[1])

            if output:
                for value in result_values:
                    msg = f"参数：{value[0]}, 目标：{value[1]}"
                    print(msg)

            return result_values


if __name__ == '__main__':

    # 初始化基本配置
    strategy_settings = {}
    strategy_settings['strategy_class'] = DynamicResidualModelStrategy
    strategy_settings['vt_symbols'] = ["V888.DCE", 'PP888.DCE']
    strategy_settings['interval'] = Interval.MINUTE
    strategy_settings['start'] = datetime(2019, 3, 1 )
    strategy_settings['end'] = datetime(2019, 10, 1)
    strategy_settings['rates'] = {"V888.DCE": 5/10000, "PP888.DCE": 5/10000}
    strategy_settings['slippages'] = {"V888.DCE": 1, "PP888.DCE": 0.5}
    strategy_settings['sizes'] = {"V888.DCE":5, "PP888.DCE":5}
    strategy_settings['priceticks'] = {"V888.DCE":5, "PP888.DCE":1}
    strategy_settings['capital'] = 1_0000_0,
    strategy_settings['collection_names'] = {"V888.DCE":"V888", "PP888.DCE":"PP888"}

    # 主要参数
    short_entry_multiplier_list = [2,3,4,5,6]
    difference_filter_num_list = [20,40,60,80]
    std_window_list = [30,60,90,120,150,180]

    # 主要参数池
    product_pool = list(product(short_entry_multiplier_list,difference_filter_num_list,std_window_list))

    # 完整参数池
    param_list = []
    for product in product_pool:
        param_dict = {}
        short_entry_multiplier,difference_filter_num,std_window = product
        param_dict['short_entry_multiplier'] = short_entry_multiplier
        param_dict['long_entry_multiplier'] = -short_entry_multiplier
        param_dict['difference_filter_num'] = difference_filter_num
        param_dict['difference_exit_num'] = difference_filter_num / 3
        param_dict['std_window'] = std_window
        param_dict['mean_window'] = std_window /2 
        param_list.append(param_dict)

    # 参数优化 
    results = run_optimization(strategy_settings, "sharpe_ratio",param_list)

    # 参数优化结果处理
    summary_list = []

    for result in  results:
        parameter = result[0]
        statistic = result[-1]
        summary_stat = []
        # 储存参数
        summary_stat.append(parameter)
        # 储存关心的指标
        summary_stat.append(statistic['sharpe_ratio'])
        summary_stat.append(statistic['max_ddpercent'])
        summary_stat.append(statistic['max_drawdown_duration'])
        summary_stat.append(statistic['daily_trade_count'])
        summary_list.append(summary_stat)

    #将结果分类，拆包
    param_array = [summary[0] for summary in summary_list]
    sharpe_array = [summary[1] for summary in summary_list]
    ddp_array = [summary[2] for summary in summary_list]
    dd_array = [summary[3] for summary in summary_list]
    dtc_array = [summary[4] for summary in summary_list]

    #转化成DataFrame
    result_df = pd.DataFrame({'param':param_array,'sharpe_ratio':sharpe_array,'max_ddpercent':ddp_array,
                            'max_drawdown_duration':dd_array, 'daily_trade_count': dtc_array})
    result_df.sort_values('sharpe_ratio',ascending=False,inplace=True)    
    result_df.to_csv('V_PP_optimization.csv',index=False)