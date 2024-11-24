from abc import ABC, abstractmethod
from ..models import ExchangeConfig, TradingPair, ExchangeOrder

class ExchangeAPI():
    def __init__(self, config: ExchangeConfig, baseUrl:str):
        self.config = config
        self.base_url = baseUrl

    @abstractmethod
    def place_order(self, trading_pair: TradingPair, amount: float, order_type: str):
        pass

    @abstractmethod
    def close_order(self, order_id: str):
        pass

    @abstractmethod
    def query_order(self, order_id: str, trading_pair: TradingPair):
        pass

    @abstractmethod
    def reverse_order(self, order:ExchangeOrder):
        pass

    def _generate_signature(self):
        # 签名生成逻辑，具体实现依赖于子类
        pass

    def _get_timestamp(self):
        # 返回当前时间戳
        pass