from abc import ABC, abstractmethod

class ExchangeAPI():
    def __init__(self, config: ExchangeConfig):
        self.config = config

    @abstractmethod
    def place_order(self, trading_pair: str, amount: float, order_type: str):
        pass

    @abstractmethod
    def close_order(self, order_id: str):
        pass

    @abstractmethod
    def query_order(self, order_id: str):
        pass

    @abstractmethod
    def reverse_order(self, order_id: str):
        pass

    def _generate_signature(self):
        # 签名生成逻辑，具体实现依赖于子类
        pass

    def _get_timestamp(self):
        # 返回当前时间戳
        pass