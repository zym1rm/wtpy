from pandas import DataFrame as df
import pandas as pd
import os
import json

from wtpy.wrapper import WtWrapper

class HftContext:
    '''
    Context是策略可以直接访问的唯一对象\n
    策略所有的接口都通过Context对象调用\n
    Context类包括以下几类接口：\n
    1、时间接口（日期、时间等）,接口格式如：stra_xxx\n
    2、数据接口（K线、财务等）,接口格式如：stra_xxx\n
    3、下单接口（设置目标仓位、直接下单等）,接口格式如：stra_xxx\n
    '''

    def __init__(self, id, stra, wrapper: WtWrapper, engine):
        self.__stra_info__ = stra       #策略对象,对象基类BaseStrategy.py
        self.__wrapper__ = wrapper      #底层接口转换器
        self.__id__ = id                #策略ID
        self.__bar_cache__ = dict()     #K线缓存
        self.__tick_cache__ = dict()    #Tick缓存,每次都重新去拉取,这个只做中转用,不在python里维护副本
        self.__sname__ = stra.name()    
        self.__engine__ = engine          #交易环境

    def on_init(self):
        '''
        初始化,一般用于系统启动的时候
        '''
        self.__stra_info__.on_init(self)

    def on_getticks(self, code:str, curTick:dict, isLast:bool):
        key = code
        if key not in self.__tick_cache__:
            self.__tick_cache__[key] = list()
        elif not isinstance(self.__tick_cache__[key], list):
            self.__tick_cache__[key] = list()

        ticks = self.__tick_cache__[key]
            
        if curTick is not None:          
            ticks.append(curTick)

        if isLast:
            localTicks = df(ticks)
            tickTime = localTicks["time"]
            localTicks.insert(0,'ticktime', tickTime)
            localTicks = localTicks.set_index("time") 
            self.__tick_cache__[key] = localTicks

    def on_getbars(self, code:str, period:str, curBar:dict, isLast:bool):
        key = "%s#%s" % (code, period)
        if key not in self.__bar_cache__:
            self.__bar_cache__[key] = list()
        elif not isinstance(self.__bar_cache__[key], list):
            self.__bar_cache__[key] = list()

        bars = self.__bar_cache__[key]
            
        if curBar is not None:          
            bars.append(curBar)

        if isLast:
            localBars = df(bars)
            barTime = localBars["time"]
            localBars.insert(0,'bartime', barTime)
            localBars = localBars.set_index("time") 
            self.__bar_cache__[key] = localBars


    def on_tick(self, code:str, newTick):
        self.__stra_info__.on_tick(self, code, newTick)

    def on_channel_ready(self):
        self.__stra_info__.on_channel_ready(self)

    def on_channel_lost(self):
        self.__stra_info__.on_channel_lost(self)

    def on_entrust(self, localid:int, stdCode:str, bSucc:bool, msg:str):
        self.__stra_info__.on_entrust(self, localid, stdCode, bSucc, msg)

    def on_order(self, localid:int, stdCode:str, isBuy:bool, totalQty:float, leftQty:float, price:float, isCanceled:bool):
        self.__stra_info__.on_order(self, localid, stdCode, isBuy, totalQty, leftQty, price, isCanceled)

    def on_trade(self, stdCode:str, isBuy:bool, qty:float, price:float):
        self.__stra_info__.on_trade(self, stdCode, isBuy, qty, price)

    def on_bar(self, code:str, period:str, newBar:dict):
        '''
        K线闭合事件响应
        @code   品种代码
        @period K线基础周期
        @times  周期倍数
        @newBar 最新K线
        '''        
        key = "%s#%s" % (code, period)

        if key not in self.__bar_cache__:
            return

        try:
            self.__bar_cache__[key].loc[newBar["bartime"]] = pd.Series(newBar)
            self.__bar_cache__[key].closed = True
            self.__stra_info__.on_bar(self, code, period, newBar)
        except ValueError as ve:
            print(ve)
        else:
            return

    def stra_log_text(self, message:str):
        '''
        输出日志
        @message    消息内容\n
        '''
        self.__wrapper__.hft_log_text(self.__id__, message)
        
    def stra_get_date(self):
        '''
        获取当前日期\n
        @return int,格式如20180513
        '''
        return self.__wrapper__.hft_get_date()

    def stra_get_time(self):
        '''
        获取当前时间,24小时制,精确到分\n
        @return int,格式如1231
        '''
        return self.__wrapper__.hft_get_time()

    def stra_get_secs(self):
        '''
        获取当前秒数,精确到毫秒\n
        @return int,格式如1231
        '''
        return self.__wrapper__.hft_get_secs()

    def stra_get_price(self, code):
        '''
        获取最新价格,一般在获取了K线以后再获取该价格
        @return 最新价格
        '''
        return self.__wrapper__.hft_get_price(code)

    def stra_get_bars(self, code:str, period:str, count:int):
        '''
        获取历史K线
        @code   合约代码
        @period K线周期,如m3/d7
        @count  要拉取的K线条数
        @isMain 是否是主K线
        '''
        key = "%s#%s" % (code, period)

        if key in self.__bar_cache__:
            #这里做一个数据长度处理
            return self.__bar_cache__[key].iloc[-count:]

        cnt =  self.__wrapper__.hft_get_bars(self.__id__, code, period, count)
        if cnt == 0:
            return None

        df_bars = self.__bar_cache__[key]
        df_bars.closed = False

        return df_bars

    def stra_get_ticks(self, code:str, count:int):
        '''
        获取tick数据
        @code   合约代码
        @count  要拉取的tick数量
        '''
        cnt = self.__wrapper__.hft_get_ticks(self.__id__, code, count)
        if cnt == 0:
            return None
        
        df_ticks = self.__tick_cache__[code]
        return df_ticks

    def stra_get_position(self, code:str = ""):
        '''
        读取当前仓位\n
        @code       合约/股票代码\n
        @usertag    入场标记
        @return     正为多仓,负为空仓
        '''
        return self.__wrapper__.hft_get_position(self.__id__, code)

    def stra_get_undone(self, stdCode:str):
        return self.__wrapper__.hft_get_undone(self.__id__, stdCode)


    def user_save_data(self, key:str, val):
        '''
        保存用户数据
        @key    数据id
        @val    数据值,可以直接转换成str的数据均可
        '''
        self.__wrapper__.hft_save_user_data(self.__id__, key, str(val))

    def user_load_data(self, key:str, defVal = None, vType = float):
        '''
        读取用户数据
        @key    数据id
        @defVal 默认数据,如果找不到则返回改数据,默认为None
        @return 返回值,默认处理为float数据
        '''
        ret = self.__wrapper__.hft_load_user_data(self.__id__, key, "")
        if ret == "":
            return defVal

        return vType(ret)

    def stra_get_comminfo(self, code:str):
        '''
        获取品种详情\n
        @code   合约代码如SHFE.ag.HOT,或者品种代码如SHFE.ag\n
        @return 品种信息,结构请参考ProductMgr中的ProductInfo
        '''
        if self.__engine__ is None:
            return None
        return self.__engine__.getProductInfo(code)

    def stra_sub_ticks(self, stdCode:str):
        '''
        订阅实时行情数据\n
        获取K线和tick数据的时候会自动订阅，这里只需要订阅额外要检测的品种即可\n
        @code   品种代码
        '''
        self.__wrapper__.hft_sub_ticks(self.__id__, stdCode)

    def stra_cancel(self, localid:int):
        '''
        撤销指定订单\n
        @id         策略ID\n
        @localid    下单时返回的本地订单号
        '''
        return self.__wrapper__.hft_cancel(self.__id__, localid)

    def stra_cancel_all(self, stdCode:str, isBuy:bool):
        '''
        撤销指定品种的全部买入订单or卖出订单\n
        @id         策略ID\n
        @stdCode    品种代码\n
        @isBuy      买入or卖出
        '''
        idstr = self.__wrapper__.hft_cancel_all(self.__id__, stdCode, isBuy)
        ids = idstr.split(",")
        localids = list()
        for localid in ids:
            localids.append(int(localid))
        return localids

    def stra_buy(self, stdCode:str, price:float, qty:float):
        '''
        买入指令\n
        @id         策略ID\n
        @stdCode    品种代码\n
        @price      买入价格, 0为市价\n
        @qty        买入数量
        '''
        idstr = self.__wrapper__.hft_buy(self.__id__, stdCode, price, qty)
        ids = idstr.split(",")
        localids = list()
        for localid in ids:
            localids.append(int(localid))
        return localids

    def stra_sell(self, stdCode:str, price:float, qty:float):
        '''
        卖出指令\n
        @id         策略ID\n
        @stdCode    品种代码\n
        @price      卖出价格, 0为市价\n
        @qty        卖出数量
        '''
        idstr = self.__wrapper__.hft_sell(self.__id__, stdCode, price, qty)
        ids = idstr.split(",")
        localids = list()
        for localid in ids:
            localids.append(int(localid))
        return localids