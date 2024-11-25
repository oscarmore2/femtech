import time
import hmac
import hashlib
import base64
import json
import requests
import datetime

from .trader import ExchangeAPI
from ..models import TradingPair, ExchangeOrder

class OKXAPI(ExchangeAPI):
    def place_order(self, trading_pair: TradingPair, amount: float, order_type: str):
        path = '/api/v5/trade/order'
        url = f"{self.base_url}{path}"
        posSide = "long" if order_type == "buy" else "short"
        order_data = {
            "instId": "{0}-{1}-SWAP".format(trading_pair.target_currency, trading_pair.source_currency),
            "tdMode": "cross",
            "side": order_type.lower(),  # "buy" 或 "sell"
            "ordType": "market",
            "sz": str(amount),
            "posSide": posSide.lower(),  # 这里添加 posSide
        }

        print(" ----------> OKX print all order data in open order", order_data)

        headers = self._get_headers('POST', path, order_data)
        response = requests.post(url, headers=headers, json=order_data)
        res = response.json()
        if res["code"] == "0":
            return {"success":True, "msg":"success", "data":res["data"]}
        else:
            return {"success":False, "msg":res}

    def close_order(self, trading_pair: TradingPair, amount: float, order_type: str):
        path = '/api/v5/trade/order'
        url = f"{self.base_url}{path}"
        posSide = "long" if order_type == "sell" else "short"
        order_data = {
            "instId": "{0}-{1}-SWAP".format(trading_pair.target_currency, trading_pair.source_currency),
            "tdMode": "cross",
            "side": order_type.lower(),  # "buy" 或 "sell"
            "ordType": "market",
            "sz": str(amount),
            "posSide": posSide,  # 这里添加 posSide
        }
        print(" ----------> OKX print all order data in close order", order_data)
        headers = self._get_headers('POST', path)
        response = requests.post(url, headers=headers)
        return response.json()

    def query_order(self, order_id: str, trading_pair: TradingPair):
        inst = "{0}-{1}-SWAP".format(trading_pair.target_currency, trading_pair.source_currency)
        path = f'/api/v5/trade/order?ordId={order_id}&instId={inst}'
        url = f"{self.base_url}{path}"
        headers = self._get_headers('GET', path)
        response = requests.get(url, headers=headers)
        return response.json()

    def reverse_order(self, order:ExchangeOrder):
        query_res = self.query_order(order.exchange_orderId, order.trading_pair) #互相认证
        if query_res.get('code') == "0":
            data = json.loads(query_res.get('data'))
            res_close = self.close_order(order.trading_pair, data["sz"], data["side"])
            time.sleep(500)
            new_side = "sell" if data["side"] == "buy" else "buy"
            trade_type = TradingType.BUY_FUTURE_LOW if new_side == "buy" else TradingType.BUY_FUTURE_HIGH
            newOrder = ExchangeOrder.objects.create(
                exchange_orderId="-1",
                exchange=config.exchangeInfo,
                trading_pair=order.trading_pair,
                trading_type=trade_type,
                order_state=ExchangeOrder.State.FINISH,  # 订单状态为 FINISH
                amount=data["sz"]
            )
            newOrder.save()
            res_open = self.place_order(order.trading_pair,  data["sz"], new_side)
            
            if res_open["success"] == True:
                order.order_state = ExchangeOrder.State.REVERSE
                order.save()
                newOrder.exchange_orderId = res_open["data"]["ordId"]
                newOrder.order_state = ExchangeOrder.State.FINISH
                newOrder.save()
                res_open["msg"] = "OKX reverse order successfully"
            return res_open
        else:
            return {"success":False, "msg":query_res.json()}

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