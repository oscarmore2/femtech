import time
import hmac
import hashlib
import requests
import json

from .trader import ExchangeAPI

class BybitAPI(ExchangeAPI):
    def place_order(self, trading_pair: str, amount: float, order_type: str, pos_side: str):
        url = f"{self.config.base_url}/v2/private/order/create"
        order_data = {
            "symbol": trading_pair,
            "side": order_type.lower(),  # "Buy" 或 "Sell"
            "order_type": "Market",
            "qty": amount,
            "time_in_force": "GoodTillCancel",
            "api_key": self.config.api_key,
            "timestamp": self._get_timestamp(),
            "position_idx": 0,  # 可选（用于多仓/空仓的区分）
            "pos_side": pos_side  # 添加 posSide
        }

        order_data["sign"] = self._generate_signature(order_data)
        response = requests.post(url, data=order_data)
        return response.json()

    def close_order(self, order_id: str):
        url = f"{self.config.base_url}/v2/private/order/cancel"
        cancel_data = {
            "order_id": order_id,
            "api_key": self.config.api_key,
            "timestamp": self._get_timestamp()
        }

        cancel_data["sign"] = self._generate_signature(cancel_data)
        response = requests.post(url, data=cancel_data)
        return response.json()

    def query_order(self, order_id: str):
        url = f"{self.config.base_url}/v2/private/order"
        query_data = {
            "order_id": order_id,
            "api_key": self.config.api_key,
            "timestamp": self._get_timestamp()
        }

        query_data["sign"] = self._generate_signature(query_data)
        response = requests.get(url, params=query_data)
        return response.json()

    def reverse_order(self, order_id: str):
        current_order = self.query_order(order_id)
        
        if 'result' in current_order and current_order['result']:
            order_info = current_order['result']
            current_side = order_info['side']  # "Buy" 或 "Sell"
            current_pos_side = order_info['pos_side']  # 当前持仓方向
            current_amount = order_info['qty']  # 当前订单的数量
            
            new_side = 'Sell' if current_side == 'Buy' else 'Buy'
            new_pos_side = 'Short' if current_pos_side == 'Long' else 'Long'  # 反向持仓
            
            return self.place_order(order_info['symbol'], float(current_amount), new_side, new_pos_side)
        else:
            return {"error": "Order not found or invalid order ID."}

    def _generate_signature(self, data):
        # 按字典序排序参数
        sorted_data = sorted(data.items())
        query_string = '&'.join([f"{key}={value}" for key, value in sorted_data])
        
        # 生成签名
        return hmac.new(self.config.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

    def _get_timestamp(self) -> str:
        return str(int(time.time() * 1000))  # 返回当前时间戳（毫秒）