import time
import hmac
import hashlib
import base64
import json
import requests
import datetime

from .trader import ExchangeAPI
from ..models import TradingPair

class OKXAPI(ExchangeAPI):
    def place_order(self, trading_pair: TradingPair, amount: float, order_type: str, pos_side: str):
        path = '/api/v5/trade/order'
        url = f"{self.base_url}{path}"
        order_data = {
            "instId": "{0}-{1}".format(trading_pair.target_currency, trading_pair.source_currency),
            "tdMode": "cross",
            "side": order_type.lower(),  # "buy" 或 "sell"
            "ordType": "market",
            "sz": str(amount),
            "posSide": pos_side.lower(),  # 这里添加 posSide
        }

        print(" ----------> OKX print all order data", order_data)

        headers = self._get_headers('POST', path, order_data)
        response = requests.post(url, headers=headers, json=order_data)
        return response.json()

    def close_order(self, order_id: str):
        path = f'/api/v5/trade/order/{order_id}/close'
        url = f"{self.base_url}/api/v5/trade/order/{order_id}/close"
        headers = self._get_headers('POST', path)
        response = requests.post(url, headers=headers)
        return response.json()

    def query_order(self, order_id: str):
        url = f"{self.base_url}/api/v5/trade/order/{order_id}"
        headers = self._get_headers('GET', f'/api/v5/trade/order/{order_id}')
        response = requests.get(url, headers=headers)
        return response.json()

    def reverse_order(self, order_id: str):
        current_order = self.query_order(order_id)
        
        if 'data' in current_order and current_order['data']:
            order_info = current_order['data'][0]
            current_side = order_info['side']  # "buy" 或 "sell"
            current_pos_side = order_info['posSide']  # 当前持仓方向
            current_amount = order_info['sz']  # 当前订单的数量
            
            new_side = 'sell' if current_side == 'buy' else 'buy'
            new_pos_side = 'long' if current_pos_side == 'short' else 'short'  # 反向持仓
            
            return self.place_order(order_info['instId'], float(current_amount), new_side, new_pos_side)
        else:
            return {"error": "Order not found or invalid order ID."}

    def _get_headers(self, method: str, request_path: str, body=None):
        timestamp = self._get_timestamp()
        signature = self._generate_signature(timestamp, method, request_path, body)
        
        headers = {
            'OK-ACCESS-KEY': self.config.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.config.api_passphrase,
            'Content-Type': 'application/json'
        }
        if self.config.isMock:
            headers['x-simulated-trading'] = "1"
        return headers

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body=None) -> str:
        body_str = json.dumps(body) if body else ''
        
        message = f"{timestamp}{str.upper(method)}{request_path}{body_str}"
        print(" ----------> Okx get message is ", message)

        # hmac_key = self.config.api_secret.encode('utf-8')
        signature = hmac.new(bytes(self.config.api_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        
        return base64.b64encode(signature.digest())

    def _get_timestamp(self):
        now = datetime.datetime.utcnow()
        t = now.isoformat("T", "milliseconds")
        return t + "Z"