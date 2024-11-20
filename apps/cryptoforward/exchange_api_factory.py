from .models import ExchangeConfig
from .broker import trader
# from .broker.okx_trader import OKXAPI
# from .broker.binance_trader import BinanceAPI
# from .broker.bybit_trader import BybitAPI
# from .broker.coninbase_trader import CoinbaseAPI
# from .broker.hotcoin_trader import HotcoinAPI
# from .broker.bitget_trader import BitgetAPI
# from .broker.karken_trader import KrakenAPI

class ExchangeAPIFactory:
    @staticmethod
    def get_exchange_api(exchange_name: str, config: ExchangeConfig, baseUrl:str) -> trader.ExchangeAPI:
        # 从 config 中获取与交易所相关的信息
        exchange_channel = config.exchangeInfo
        
        if exchange_channel.name.lower() == 'okx':
            from .broker import okx_trader as okxTrader
            return okxTrader.OKXAPI(config, baseUrl)
        elif exchange_channel.name.lower() == 'kraken':
            from .broker import karken_trader as karkenTrader
            return karkenTrader.KrakenAPI(config, baseUrl)
        elif exchange_channel.name.lower() == 'hotcoin':
            from .broker import hotcoin_trader as hotcoinTrader
            return hotcoinTrader.HotcoinAPI(config, baseUrl)
        elif exchange_channel.name.lower() == 'coinbase':
            from .broker import coninbase_trader as coinbaseTrader
            return coinbaseTrader.CoinbaseAPI(config, baseUrl)
        elif exchange_channel.name.lower() == 'bybit':
            from .broker import bybit_trader as bybitTrader
            return bybitTrader.BybitAPI(config, baseUrl)
        elif exchange_channel.name.lower() == 'bitget':
            from .broker import bitget_trader as bitgetTrader
            return bitgetTrader.BitgetAPI(config, baseUrl)
        elif exchange_channel.name.lower() == 'binance':
            from .broker import binance_trader as binanceTrader
            return binanceTrader.BinanceAPI(config, baseUrl)
        else:
            raise ValueError(f"Unsupported exchange: {exchange_channel.name}")

# 使用示例
# config = ExchangeConfig.objects.get(id=1)
# api = ExchangeAPIFactory.get_exchange_api(config.exchangeInfo.name, config, baseUrl)