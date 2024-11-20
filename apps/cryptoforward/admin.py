from django.contrib import admin

from .models import TradingPair, ExchangeChannel, ExchangeOrder, ExchangeAccountInfo, ExcangeSignalTrading, DepositAccount, ExchangeConfig

admin.site.register(TradingPair)
admin.site.register(ExchangeChannel)
admin.site.register(ExchangeOrder)
admin.site.register(ExchangeAccountInfo)
admin.site.register(ExcangeSignalTrading)
admin.site.register(DepositAccount)
admin.site.register(ExchangeConfig)

# Register your models here.
