
from pymongo import MongoClient, ASCENDING
import pandas as pd
import numpy as np
from datetime import datetime
import talib
import matplotlib.pyplot as plt
import scipy.stats as st
import scipy.stats as sc

class DataAnalyzer(object):
    """
    """
    def __init__(self, exportpath="", datformat=['datetime', 'high_price', 'low_price', 'open_price', 'close_price','volume','interval','symbol','open_interest']):
        self.mongohost = None
        self.mongoport = None
        self.db = None
        self.collection = None
        self.df = pd.DataFrame()
        self.exportpath = exportpath
        self.datformat = datformat
        self.startBar = 2
        self.endBar = 12
        self.step = 2
        self.pValue = 0.015
    def db_to_df(self, db, collection, symbol, start, end,interval='1m', mongohost="localhost", mongoport=27017, export2csv=False):
        """读取MongoDB数据库行情记录，输出到Dataframe中
        db:database_name;
        collection: specific_table_name;
        symbol:contract_symbol recorded in the collection ;
        start: datetime
        end: datetime
        
        
        
        """
        self.mongohost = mongohost
        self.mongoport = mongoport
        self.db = db
        self.collection = collection
        self.symbol = symbol 
        self.interval = interval
        dbClient = MongoClient(self.mongohost, self.mongoport, connectTimeoutMS=500)
        db = dbClient[self.db]
#         db.adminCommand({setParameter:1, internalQueryExecMaxBlockingSortBytes:335544320})
        cursor = db[self.collection].find({'symbol':self.symbol,'interval':self.interval})
        self.df = pd.DataFrame(list(cursor))
        self.df = self.df[self.datformat]
        self.df = self.df.reset_index(drop=True)
        slice_df = self.df.set_index(self.datformat[0])
        slice_df = slice_df[start:end]
        self.df = slice_df.reset_index()
        path = self.exportpath + self.collection + ".csv"
        if export2csv == True:
            self.df.to_csv(path, index=True, header=True)
        return self.df
    def csv_to_df(self, csvpath, dataname="csv_data", export2csv=False):
        """读取csv行情数据，输入到Dataframe中"""
        csv_df = pd.read_csv(csvpath)
        self.df = csv_df[self.datformat]
        self.df["datetime"] = pd.to_datetime(self.df['datetime'])
        # self.df["high_price"] = self.df['high_price'].astype(float)
        # self.df["low_price"] = self.df['low_price'].astype(float)
        # self.df["open_price"] = self.df['open_price'].astype(float)
        # self.df["close_pricw"] = self.df['close_price'].astype(float)
        # self.df["volume"] = self.df['volume'].astype(int)
        self.df = self.df.reset_index(drop=True)
        path = self.exportpath + dataname + ".csv"
        if export2csv == True:
            self.df.to_csv(path, index=True, header=True)
        return self.df
    def df_to_minute_Bar(self, inputdf, barmins,interval='1m', crossmin=1, export2csv=False):
        """
        输入分钟k线dataframe数据，合并多多种数据，
        例如三分钟/5分钟等，如果开始时间是9点1分，crossmin = 0；
        如果是9点0分，crossmin为1
        默认是1m数据
        """
        inputdf = inputdf.loc[inputdf['interval'] == '1m']
        dfbarmin = pd.DataFrame()
        highBarMin = 0
        lowBarMin = 0
        openBarMin = 0
        volumeBarmin = 0
        datetime = 0
        for i in range(0, len(inputdf) - 1):
            bar = inputdf.iloc[i, :].to_dict()
            if openBarMin == 0:
                openBarmin = bar["open_price"]
            if highBarMin == 0:
                highBarMin = bar["high_price"]
            else:
                highBarMin = max(bar["high_price"], highBarMin)
            if lowBarMin == 0:
                lowBarMin = bar["low_price"]
            else:
                lowBarMin = min(bar["low_price"], lowBarMin)
            closeBarMin = bar["close_price"]
            datetime = bar["datetime"]
            volumeBarmin += int(bar["volume"])
            interval = bar['interval']
            open_interest = bar['open_interest']
            symbol = bar['symbol']
            # X分钟已经走完
            if not (bar["datetime"].minute + crossmin) % barmins:  # 可以用X整除
                # 生成上一X分钟K线的时间戳
                barMin = {'datetime': datetime, 'high_price': highBarMin, 'low_price': lowBarMin, 'open_price': openBarmin,
                          'close_price': closeBarMin, 'volume' : volumeBarmin,'open_interest': open_interest, 'symbol': symbol}
                dfbarmin = dfbarmin.append(barMin, ignore_index=True)
                highBarMin = 0
                lowBarMin = 0
                openBarMin = 0
                volumeBarmin = 0
        if export2csv == True:
            dfbarmin.to_csv(self.exportpath + "bar" + str(barmins)+ str(self.collection) + ".csv", index=True, header=True)
        return dfbarmin
    def df_cci(self, inputdf, n, export2csv=False):
        
        """
        调用talib方法计算CCI指标，写入到df并输出
        
        采用了滞后一个bar形成技术指标
        """
        dfcci = inputdf
        dfcci["cci"] = None
        for i in range(n, len(inputdf)-1):
            df_ne = inputdf.loc[i - n + 1:i, :]
            cci = talib.CCI(np.array(df_ne["high_price"]), np.array(df_ne["low_price"]), np.array(df_ne["close_price"]), n)
            dfcci.loc[i+1, "cci"] = cci[-1]
        dfcci = dfcci.fillna(0)
        dfcci = dfcci.replace(np.inf, 0)
        if export2csv == True:
            dfcci.to_csv(self.exportpath + "dfcci" + ".csv", index=True, header=True)
        return dfcci