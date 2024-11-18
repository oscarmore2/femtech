import time
import hmac
import hashlib
import base64
import requests
import json

from .trader import ExchangeAPI

class CoinbaseAPI(ExchangeAPI):
    def __init__(self, config):
        self.config = config
        self.positions = {}  # 用于存储持仓信息

    def place_order(self, trading_pair: str, amount: float, order_type: str):
        url = f"{self.config.base_url}/orders"
        order_data = {
            "product_id": trading_pair,
            "side": order_type.lower(),  # "buy" 或 "sell"
            "type": "market",
            "size": amount,
            "post_only": True,
        }

        response = requests.post(url, headers=self._get_headers(), json=order_data)
        result = response.json()

        # 更新持仓状态
        self.update_positions(trading_pair, amount, order_type)
        return result

    def update_positions(self, trading_pair: str, amount: float, order_type: str):
        if trading_pair not in self.positions:
            self.positions[trading_pair] = {"long": 0, "short": 0}

        if order_type == "buy":
            self.positions[trading_pair]["long"] += amount
        elif order_type == "sell":
            self.positions[trading_pair]["short"] += amount

    def close_order(self, order_id: str):
        # Coinbase Pro 不直接支持通过 ID 平仓，需要使用取消订单来实现
        url = f"{self.config.base_url}/orders/{order_id}"
        headers = self._get_headers('DELETE', url)
        response = requests.delete(url, headers=headers)
        return response.json()

    def query_order(self, order_id: str):
        url = f"{self.config.base_url}/orders/{order_id}"
        headers = self._get_headers('GET', url)
        response = requests.get(url, headers=headers)
        return response.json()

    def reverse_order(self, order_id: str):
        current_order = self.query_order(order_id)
        
        if 'id' in current_order:
            current_side = current_order['side']  # "buy" 或 "sell"
            current_amount = current_order['size']  # 当前订单的数量
            
            new_side = 'sell' if current_side == 'buy' else 'buy'
            
            return self.place_order(current_order['product_id'], float(current_amount), new_side)
        else:
            return {"error": "Order not found or invalid order ID."}

    def _get_headers(self, method: str, request_path: str, body=None):
        timestamp = self._get_timestamp()
        signature = self._generate_signature(timestamp, method, request_path, body)
        
        headers = {
            'CB-ACCESS-KEY': self.config.api_key,
            'CB-ACCESS-SIGN': signature,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-PASSPHRASE': self.config.api_passphrase,
            'Content-Type': 'application/json',
        }
        return headers

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body=None) -> str:
        body_str = json.dumps(body) if body else ''
        message = f"{timestamp}{method}{request_path}{body_str}"
        
        hmac_key = self.config.api_secret.encode('utf-8')
        signature = hmac.new(hmac_key, message.encode('utf-8'), hashlib.sha256)
        
        return base64.b64encode(signature.digest()).decode('utf-8')

    def _get_timestamp(self) -> str:
        return str(int(time.time()))  # 返回当前时间戳（秒）