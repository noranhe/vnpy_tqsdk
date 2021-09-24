from datetime import timedelta
from typing import List, Optional
from pytz import timezone
import pandas as pd

from tqsdk import TqApi, TqAuth

from vnpy.trader.datafeed import BaseDatafeed
from vnpy.trader.setting import SETTINGS
from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData, TickData, HistoryRequest

INTERVAL_VT2TQ = {
    Interval.MINUTE: 60,
    Interval.HOUR: 60 * 60,
    Interval.DAILY: 60 * 60 * 24,
    Interval.TICK: 0
}

CHINA_TZ = timezone("Asia/Shanghai")


def to_tq_symbol(symbol, exchange):
    """将交易所代码转换为天勤代码"""
    return f"{exchange.value}.{symbol}"


class TqsdkDatafeed(BaseDatafeed):
    """天勤TQsdk数据服务接口"""

    def __init__(self):
        """"""
        self.username: str = SETTINGS["datafeed.username"]
        self.password: str = SETTINGS["datafeed.password"]

        self.inited: bool = False
        self.api = None
        self.symbols: List[str] = None

    def init(self) -> bool:
        """初始化"""
        if self.inited:
            return True

        if not self.username or not self.password:
            return False

        try:
            self.api = TqApi(auth=TqAuth(self.username, self.password))
        except Exception:
            return False

        if not self.symbols:
            self.symbols = [k for k, v in self.api._data["quotes"].items()]

        self.inited = True
        return True

    def query_bar_history(self, req: HistoryRequest) -> Optional[List[BarData]]:
        """查询k线数据"""
        if not self.inited:
            self.init()

        symbol = req.symbol
        exchange = req.exchange
        interval = req.interval
        start = req.start
        end = req.end

        tq_symbol = to_tq_symbol(symbol, exchange)
        if tq_symbol not in self.symbols:
            return None

        tq_interval = INTERVAL_VT2TQ.get(interval)
        if not tq_interval:
            return None

        # 为了查询夜盘数据
        end += timedelta(1)

        df = self.api.get_kline_data_series(symbol=tq_symbol, duration_seconds=INTERVAL_VT2TQ[interval],
                                            start_dt=start, end_dt=end)

        self.api.close()

        self.inited = False

        data: List[BarData] = []

        if df is not None:
            for ix, row in df.iterrows():
                # 天勤时间为与1970年北京时间相差的秒数，需要加上8小时差
                dt = pd.Timestamp(row["datetime"]).to_pydatetime() + timedelta(hours=8)
                bar = BarData(
                    symbol=symbol,
                    exchange=exchange,
                    interval=interval,
                    datetime=CHINA_TZ.localize(dt),
                    open_price=row["open"],
                    high_price=row["high"],
                    low_price=row["low"],
                    close_price=row["close"],
                    volume=row["volume"],
                    open_interest=row["open_oi"],
                    gateway_name="TQ",
                )
                data.append(bar)
        return data

    def query_tick_history(self, req: HistoryRequest) -> Optional[List[TickData]]:
        """查询Tick数据"""
        if not self.inited:
            self.init()

        symbol = req.symbol
        exchange = req.exchange
        start = req.start
        end = req.end

        tq_symbol = to_tq_symbol(symbol, exchange)
        if tq_symbol not in self.symbols:
            return None

        if req.interval is not Interval.TICK:
            return None

        # 为了查询夜盘数据
        end += timedelta(1)

        df = self.api.get_tick_data_series(symbol=tq_symbol, start_dt=start, end_dt=end)

        self.api.close()
        self.inited = False

        data: List[TickData] = []

        if df is not None:
            for ix, row in df.iterrows():
                # 天勤时间为与1970年北京时间相差的秒数，需要加上8小时差
                dt = pd.Timestamp(row["datetime"]).to_pydatetime() + timedelta(hours=8)
                tick = TickData(
                    symbol=symbol,
                    exchange=exchange,
                    datetime=CHINA_TZ.localize(dt),
                    high_price=row["highest"],
                    low_price=row["lowest"],
                    last_price=row["last_price"],
                    volume=row["volume"],
                    open_interest=row["open_interest"],
                    bid_price_1=row["bid_price1"],
                    bid_volume_1=row["bid_volume1"],
                    ask_price_1=row["ask_price1"],
                    ask_volume_1=row["ask_volume1"],
                    gateway_name="TQ",
                )
                data.append(tick)
        return data