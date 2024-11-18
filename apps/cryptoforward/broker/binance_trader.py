import time
import hmac
import hashlib
import base64
import requests
import json
from .trader import ExchangeAPI

class BinanceAPI(ExchangeAPI):
    def place_order(self, trading_pair: str, amount: float, order_type: str, pos_side: str):
        url = f"{self.config.base_url}/fapi/v1/order"
        order_data = {
            "symbol": trading_pair,
            "side": order_type.upper(),  # "BUY" 或 "SELL"
            "type": "MARKET",
            "quantity": amount,
            "positionSide": pos_side.upper(),  # "LONG" 或 "SHORT"
            "timestamp": self._get_timestamp()
        }

        order_data["signature"] = self._generate_signature(order_data)
        response = requests.post(url, headers=self._get_headers(), params=order_data)
        return response.json()

    def close_order(self, order_id: str):
        url = f"{self.config.base_url}/api/v3/order"
        timestamp = self._get_timestamp()
        
        params = {
            "symbol": order_id,  # 这里需要根据实际情况调整
            "timestamp": timestamp,
            "signature": self._generate_signature(timestamp, order_id)
        }

        response = requests.delete(url, params=params)
        return response.json()

    def query_order(self, order_id: str):
        url = f"{self.config.base_url}/api/v3/order"
        timestamp = self._get_timestamp()
        
        params = {
            "symbol": order_id,  # 这里需要根据实际情况调整
            "timestamp": timestamp,
            "signature": self._generate_signature(timestamp, order_id)
        }

        response = requests.get(url, params=params)
        return response.json()

    def reverse_order(self, order_id: str):
        current_order = self.query_order(order_id)
        
        if 'status' in current_order and current_order['status'] == 'FILLED':
            order_info = current_order
            current_side = order_info['side']  # "BUY" 或 "SELL"
            current_pos_side = order_info['positionSide']  # "LONG" 或 "SHORT"
            current_amount = order_info['origQty']  # 当前订单的数量
            
            new_side = 'SELL' if current_side == 'BUY' else 'BUY'
            new_pos_side = 'SHORT' if current_pos_side == 'LONG' else 'LONG'  # 反向持仓
            
            return self.place_order(order_info['symbol'], float(current_amount), new_side, new_pos_side)
        else:
            return {"error": "Order not found or invalid order ID."}

    def _generate_signature(self, timestamp: str, trading_pair: str, amount: float, order_type: str = None) -> str:
        query_string = f"symbol={trading_pair}&side={order_type}&type=MARKET&quantity={amount}&timestamp={timestamp}"
        signature = hmac.new(self.config.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return signature.hexdigest()

    def _get_timestamp(self) -> str:
        return str(int(time.time() * 1000))  # 返回当前时间戳（毫秒）