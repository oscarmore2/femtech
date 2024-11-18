from .models import ExchangeConfig

class ExchangeAPIFactory:
    @staticmethod
    def get_exchange_api(exchange_name: str, config: ExchangeConfig) -> ExchangeAPI:
        # 从 config 中获取与交易所相关的信息
        exchange_channel = config.exchangeInfo
        
        if exchange_channel.name.lower() == 'okx':
            from broker.okx_trader import OKXAPI
            return OKXAPI(config)
        elif exchange_channel.name.lower() == 'kraken':
            from broker.karken_trader import KrakenAPI
            return KrakenAPI(config)
        elif exchange_channel.name.lower() == 'hotcoin':
            from broker.hotcoin_trader import HotcoinAPI
            return HotcoinAPI(config)
        elif exchange_channel.name.lower() == 'coinbase':
            from broker.coninbase_trader import CoinbaseAPI
            return CoinbaseAPI(config)
        elif exchange_channel.name.lower() == 'bybit':
            from broker.bybit_trader import BybitAPI
            return BybitAPI(config)
        elif exchange_channel.name.lower() == 'bitget':
            from broker.bitget_trader import BitgetAPI
            return BitgetAPI(config)
        elif exchange_channel.name.lower() == 'binance':
            from broker.binance_trader import BinanceAPI
            return BinanceAPI(config)
        else:
            raise ValueError(f"Unsupported exchange: {exchange_channel.name}")

# 使用示例
# config = ExchangeConfig.objects.get(id=1)
# api = ExchangeAPIFactory.get_exchange_api(config.exchangeInfo.name, config)