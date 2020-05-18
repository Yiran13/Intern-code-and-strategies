from vnpy.trader.constant import (Exchange, Interval)
import pandas as pd
from vnpy.trader.database import database_manager
from vnpy.trader.object import (BarData,TickData)
from datetime import timedelta

# 封装函数
def move_df_to_mongodb(imported_data:pd.DataFrame,collection_name:str):
    bars = []
    start = None
    count = 0

    for row in imported_data.itertuples():

        bar = BarData(

              symbol=row.symbol,
              exchange=row.exchange,
              datetime=row.datetime,
              interval=row.interval,
              volume=row.volume,
              open_price=row.open,
              high_price=row.high,
              low_price=row.low,
              close_price=row.close,
              open_interest=row.open_interest,
              gateway_name="DB",

        )


        bars.append(bar)

        # do some statistics
        count += 1
        if not start:
            start = bar.datetime
    end = bar.datetime

    # insert into database
    database_manager.save_bar_data(bars, collection_name)
    print(f'Insert Bar: {count} from {start} - {end}')

def move_rqdata_symbol_to_mongodb(symbol:str,exchange:Exchange, interval:Interval=Interval.MINUTE):
    '''
    rqdata 数据源 1分钟数据处理
    '''

    imported_data = pd.read_csv(f'D:/chorme_download/{symbol}888.csv')
    imported_data['exchange'] = exchange
    imported_data['interval'] = Interval.MINUTE
    float_columns = ['close', 'high', 'low', 'open', 'volume', 'open_interest']
    for col in float_columns:
        imported_data[col] = imported_data[col].astype('float')
    datetime_format = '%Y%m%d %H:%M:%S'
    imported_data['datetime'] = pd.to_datetime(imported_data['datetime'],format=datetime_format)
    if interval == Interval.MINUTE:
        adjustment = timedelta(minutes=1)
        # 米筐数据时间戳和vn.py本身处理的不一致，因此需要对齐处理
        imported_data['datetime'] = imported_data['datetime'] - adjustment
        imported_data['symbol'] =symbol+'888'
        move_df_to_mongodb(imported_data,symbol+'888')
        pass
    else:
        print('请检查时间戳是否会有没有对齐的情况')
    # print(imported_data.columns)
    



def move_single_symbol_to_mongodb(symbol:str,year:int,exchange:Exchange, interval:Interval=Interval.MINUTE):
    '''
    jinshuyuan 数据源 1分钟数据处理
    '''
    imported_data = pd.read_csv(f'D:/1分钟数据压缩包/FutAC_Min1_Std_{year}/{symbol}主力连续.csv',encoding='gbk')
    imported_data['市场代码'] = exchange
    imported_data['interval'] = Interval.MINUTE
    float_columns = ['开', '高', '低', '收', '成交量', '持仓量']
    for col in float_columns:
        imported_data[col] = imported_data[col].astype('float')
    datetime_format = '%Y%m%d %H:%M:%S'
    imported_data['时间'] = pd.to_datetime(imported_data['时间'],format=datetime_format)
    # print(imported_data.columns)
    imported_data.columns = ['exchange','symbol','datetime','open','high','low','close','volume','成交额','open_interest','interval']
    imported_data['symbol'] =symbol+'88'
    move_df_to_mongodb(imported_data,symbol+'88')


if __name__ == "__main__":

    # 读取需要入库的csv文件，该文件是用gbk编码
    
    move_rqdata_symbol_to_mongodb(symbol='HC',exchange=Exchange.SHFE)
    move_rqdata_symbol_to_mongodb(symbol='RB',exchange=Exchange.SHFE)
    move_rqdata_symbol_to_mongodb(symbol='CU',exchange=Exchange.SHFE)
    # move_rqdata_symbol_to_mongodb(symbol='RB',exchange=Exchange.SHFE)
    move_rqdata_symbol_to_mongodb(symbol='NI',exchange=Exchange.SHFE)
    move_rqdata_symbol_to_mongodb(symbol='L',exchange=Exchange.DCE)
    move_rqdata_symbol_to_mongodb(symbol='Y',exchange=Exchange.DCE)
    move_rqdata_symbol_to_mongodb(symbol='P',exchange=Exchange.DCE)
    # move_rqdata_symbol_to_mongodb(symbol='EG',exchange=Exchange.DCE)

    # imported_data = pd.read_csv('D:/1分钟数据压缩包/FutAC_Min1_Std_2016/rb主力连续.csv',encoding='gbk')
    # # 将csv文件中 `市场代码`的 SC 替换成 Exchange.SHFE SHFE
    # imported_data['市场代码'] = Exchange.SHFE
    # # 增加一列数据 `inteval`，且该列数据的所有值都是 Interval.MINUTE
    # imported_data['interval'] = Interval.MINUTE
    # # 明确需要是float数据类型的列
    # float_columns = ['开', '高', '低', '收', '成交量', '持仓量']
    # for col in float_columns:
    #   imported_data[col] = imported_data[col].astype('float')
    # # 明确时间戳的格式
    # # %Y/%m/%d %H:%M:%S 代表着你的csv数据中的时间戳必须是 2020/05/01 08:32:30 格式
    # datetime_format = '%Y%m%d %H:%M:%S'
    # imported_data['时间'] = pd.to_datetime(imported_data['时间'],format=datetime_format)
    # # 因为没有用到 成交额 这一列的数据，所以该列列名不变
    # imported_data.columns = ['exchange','symbol','datetime','open','high','low','close','volume','成交额','open_interest','interval']
    # imported_data['symbol'] ='rb88'
    # move_df_to_mongodb(imported_data,'rb88')
