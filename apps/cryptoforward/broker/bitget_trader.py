import time
import hmac
import hashlib
import requests
import json
import base64

from .trader import ExchangeAPI
from ..models import TradingPair

class BitgetAPI(ExchangeAPI):
    def place_order(self, trading_pair: TradingPair, amount: float, order_type: str, pos_side: str):
        path = "/api/v2/mix/order/place-order"
        url = f"{self.base_url}{path}"
        symbol = ""
        productType = ""
        if self.config.isMock:
            symbol = "S{0}S{1}".format(str.upper(trading_pair.target_currency), str.upper(trading_pair.source_currency))
            productType = "S{0}-FUTURE".format(str.upper(trading_pair.source_currency))
        else:
            symbol = "{0}{1}".format(str.upper(trading_pair.target_currency), str.upper(trading_pair.source_currency))
            productType = "{0}-FUTURE".format(str.upper(trading_pair.source_currency))
        # trade_side = "open" if pos_side == "long" else "close"
        order_data = {
            "symbol": symbol,
            "productType": productType,
            "marginMode" : "crossed",
            "price": "0",  # 市场订单不需要指定价格
            "size": str(amount),
            "side": order_type.lower(),  # "buy" 或 "sell"
            "orderType": "market",
            "tradeSide": "open"  # 添加 posSide
        }

        headers = self._get_headers('POST', path, order_data)
        response = requests.post(url, headers=headers, json=order_data)
        return response.json()

    def close_order(self, order_id: str):
        url = f"{self.base_url}/api/v1/order/{order_id}/close"
        headers = self._get_headers('POST', url)
        response = requests.post(url, headers=headers)
        return response.json()

    def query_order(self, order_id: str):
        url = f"{self.base_url}/api/v1/order/{order_id}"
        headers = self._get_headers('GET', url)
        response = requests.get(url, headers=headers)
        return response.json()

    def reverse_order(self, order_id: str):
        current_order = self.query_order(order_id)
        
        if 'data' in current_order and current_order['data']:
            current_side = current_order['data']['side']  # "buy" 或 "sell"
            current_amount = current_order['data']['size']  # 当前订单的数量
            
            new_side = 'sell' if current_side == 'buy' else 'buy'
            new_pos_side = 'long' if current_order['data']['posSide'] == 'short' else 'short'  # 反向持仓
            
            return self.place_order(current_order['data']['symbol'], float(current_amount), new_side, new_pos_side)
        else:
            return {"error": "Order not found or invalid order ID."}

    def _get_headers(self, method: str, request_path: str, body=None):
        timestamp = self._get_timestamp()
        signature = self._generate_signature(timestamp, method, request_path, body)
        
        headers = {
            'Content-Type': 'application/json',
            'ACCESS-KEY': self.config.api_key,
            'ACCESS-SIGN': signature,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-PASSPHRASE': self.config.api_passphrase,
            'locale': 'zh-CN',
        }
        print("-----> bitget get header with ", headers)
        return headers

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body=None) -> str:
        body_str = json.dumps(body) if body else ''
        message = f"{timestamp}{method}{request_path}{body_str}"

        print("-----> bitget sign with data ", message)
        
        hmac_key = self.config.api_secret.encode('utf8')
        signature = hmac.new(hmac_key, message.encode('utf-8'), hashlib.sha256)
        
        return str(base64.b64encode(signature.digest()), 'utf8')

    def _get_timestamp(self) -> str:
        return str(int(time.time() * 1000))  # 返回当前时间戳（毫秒）