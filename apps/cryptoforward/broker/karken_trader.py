import time
import hmac
import hashlib
import requests
import json

from .trader import ExchangeAPI
from ..models import TradingPair

class KrakenAPI(ExchangeAPI):
    def place_order(self, trading_pair: TradingPair, amount: float, order_type: str, pos_side: str):
        url = f"{self.base_url}/0/private/AddOrder"
        order_data = {
            "pair": trading_pair,
            "type": order_type.lower(),  # "buy" 或 "sell"
            "ordertype": "market",
            "volume": amount,
        }

        headers = self._get_headers(order_data)
        response = requests.post(url, headers=headers, data=order_data)
        return response.json()

    def close_order(self, order_id: str):
        url = f"{self.base_url}/0/private/CancelOrder"
        order_data = {
            "txid": order_id
        }

        headers = self._get_headers(order_data)
        response = requests.post(url, headers=headers, data=order_data)
        return response.json()

    def query_order(self, order_id: str):
        url = f"{self.base_url}/0/private/QueryOrders"
        order_data = {
            "txid": order_id
        }

        headers = self._get_headers(order_data)
        response = requests.post(url, headers=headers, data=order_data)
        return response.json()

    def reverse_order(self, order_id: str):
        current_order = self.query_order(order_id)
        
        if 'result' in current_order and current_order['result']:
            order_info = current_order['result'][order_id]
            current_side = order_info['type']  # "buy" 或 "sell"
            current_amount = order_info['vol']  # 当前订单的数量
            
            new_side = 'sell' if current_side == 'buy' else 'buy'
            
            return self.place_order(order_info['pair'], float(current_amount), new_side)
        else:
            return {"error": "Order not found or invalid order ID."}

    def _get_headers(self, body=None):
        nonce = str(int(time.time() * 1000))
        body_str = json.dumps(body) if body else ''
        message = nonce + body_str
        signature = self._generate_signature(message)

        headers = {
            'API-Key': self.config.api_key,
            'API-Sign': signature,
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        return headers

    def _generate_signature(self, message: str) -> str:
        # 生成签名
        secret = base64.b64decode(self.config.api_secret)
        return base64.b64encode(hmac.new(secret, message.encode('utf-8'), hashlib.sha512).digest()).decode('utf-8')