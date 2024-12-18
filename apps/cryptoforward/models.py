from django.db import models
from django.contrib.auth.models import User as AuthUser, AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import make_password
from .formatMsg import GetTradingDefaultInfoFormat
from django.utils.translation import gettext_lazy as _

import hashlib
from datetime import datetime

class TradingType(models.IntegerChoices):
        BUY = 1, _("买入")
        SELL = 2, _("卖出")
        BUY_FUTURE_LOW = 3, _("做多买入")
        SELL_FUTURE_HIGH = 4, _("做空卖出")
        SELL_FUTURE_LOW = 5, _("做多卖出")
        BUY_FUTURE_HIGH = 6, _("做空买入")

class SignalType(models.IntegerChoices):
    DUEL = 1, _("双向")
    BUY_LOW_ONLY= 2, _("只做多")
    SELL_HIGH_ONLY = 3, _("只做空")


# Create your models here.
class TradingPair (models.Model):
    def hashId(self):
        m1 = hashlib.md5(str(datetime.now()).encode("utf-8"))
        return m1.hexdigest()
        
    finger_print = models.TextField(primary_key=True, blank=True, editable=False, verbose_name="指纹值")
    treading_pair_currency = models.CharField(max_length=200, verbose_name="交易对名称")
    target_currency = models.CharField(max_length=200, default="BTC", verbose_name="交易币种")
    source_currency = models.CharField(max_length=200, default="USDT", verbose_name="基准币种")
    trading_context = models.TextField(blank=True, verbose_name="交易信息Context(json 格式)")

    def save(self, **kwargs):
        if len(self.finger_print) < 1:
            self.finger_print = self.hashId()
        print("satate {0}".format(self._state.adding))
        self.trading_context = GetTradingDefaultInfoFormat(self.finger_print)
        super().save(**kwargs)

    def __str__(self):
        return "{0}-{1}-{2}".format(self.target_currency, self.source_currency, self.finger_print)

class ExchangeChannel(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200, verbose_name="交易所名称")
    base_url = models.CharField(max_length=200, verbose_name="交易所rest接口base url")
    ws_url = models.CharField(max_length=200, verbose_name="交易所websocket接口base url")

    def __str__(self):
        return self.name


class ExchangeOrder(models.Model):
    class State(models.IntegerChoices):
        OPEN = 1, _("打开")
        FINISH = 2, _("完成")
        FAILD = 3, _("失败")
        REVERSE = 4, _("被反转")
    
    id = models.AutoField(primary_key=True)
    exchange_orderId = models.CharField(max_length=200, verbose_name="交易所订单Id")
    exchange = models.ForeignKey(ExchangeChannel, blank=True, null=True, on_delete=models.CASCADE, related_name='exchange_order', verbose_name="关联交易所")
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE, related_name='order_trading_pair', verbose_name="关联交易对")
    amount = models.FloatField(default=0.0, verbose_name="交易数量")
    leverge = models.FloatField(default=1.0, verbose_name="交易杠杆")
    order_state = models.IntegerField(choices=State, verbose_name="订单状态")
    trading_type = models.IntegerField(choices=TradingType, default=1, verbose_name="交易类型")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="交易创建时间")
    
    def __str__(self):
        if self.exchange == None:
            return f"Null-{self.exchange_orderId}"
        else:
            return f"{self.exchange.name}-{self.exchange_orderId}"
    
class ExchangeAccountInfo(models.Model):
    id = models.AutoField(primary_key=True)
    user_name = models.CharField(max_length=200, verbose_name="交易所账户名")
    token = models.CharField(max_length=200, verbose_name="交易所接口 token")
    exchange = models.ForeignKey(ExchangeChannel, on_delete=models.CASCADE, related_name='exchange_account', verbose_name="关联交易所")

    def __str__(self):
        return self.user_name

class ExcangeSignalTrading(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200, verbose_name="交易管道信号名称")
    trade_pair = models.ForeignKey(TradingPair, blank=True, null=True, on_delete=models.CASCADE, related_name='pipeline_trading_pair', verbose_name="关联交易对" )
    signal_api = models.CharField(max_length=200, verbose_name="交易信号api")
    related_account = models.ForeignKey(ExchangeAccountInfo, blank=True, null=True, on_delete=models.CASCADE, related_name='signal_trading_pair', verbose_name="关联账户(可空)")
    format_string_enter_long = models.TextField(blank=True, verbose_name="多仓进场交易信号格式(json 格式)")
    format_string_exit_long = models.TextField(blank=True, verbose_name="多仓离场交易信号格式(json 格式)")
    format_string_enter_short = models.TextField(blank=True, verbose_name="空仓进场交易信号格式(json 格式)")
    format_string_exit_short = models.TextField(blank=True, verbose_name="多仓离场交易信号格式(json 格式)")
    order_list = models.ManyToManyField(ExchangeOrder, blank=True, verbose_name="订单列表")
    signal_type = models.IntegerField(choices=SignalType, default=1, verbose_name="对冲交易类型")

    def __str__(self):
        return self.name

class AccountManager(BaseUserManager):
    def create_user(self, username, email, password=None):
        if not username:
            raise ValueError('Users must have a username')

        user = self.model(
            username=username,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password):
        user = self.create_user(
            username=username,
            password=password,
        )
        user.is_admin = True
        user.save(using=self._db)
        return user

class DepositAccount(AbstractBaseUser):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=100, unique=True, verbose_name="账户名")
    nickname = models.CharField(max_length=100, blank=True, verbose_name="昵称")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    trade_pair = models.ManyToManyField(TradingPair, blank=True, null=True, related_name='account_trading_pair', verbose_name="关联交易对")
    order_list = models.ManyToManyField(ExchangeOrder, blank=True, verbose_name="订单列表")

    objects = AccountManager()

    USERNAME_FIELD = 'username'

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.password = make_password(self.password)  # 确保在创建时加密密码
        super(DepositAccount, self).save(*args, **kwargs)

    def __str__(self):
        return self.nickname

class ExchangeConfig(models.Model):
    id = models.AutoField(primary_key=True)
    name =  models.CharField(max_length=200, verbose_name="交易配置名称")
    exchangeInfo = models.ForeignKey(ExchangeChannel, on_delete=models.CASCADE, related_name='exchange_config_pair', verbose_name="所属交易所")
    account = models.ForeignKey(DepositAccount, on_delete=models.CASCADE, related_name='account_config_pair', verbose_name="所属账号")
    api_key = models.TextField(max_length=255, blank=True, null=True, verbose_name="API密钥")  # API密钥
    api_secret = models.TextField(max_length=255, blank=True, null=True, verbose_name="API密钥的secret")  # API密钥的secret
    api_passphrase = models.TextField(max_length=255, blank=True, null=True, verbose_name="可选的passphrase")  # 可选的passphrase
    isMock = models.BooleanField(default=True, verbose_name="是否模拟交易")
    isActive = models.BooleanField(default=True, verbose_name="是否是否启用")
    order_list = models.ManyToManyField(ExchangeOrder, blank=True, verbose_name="订单列表")

    def __str__(self):
        return self.name if self.isActive else "{0}(未启用)".format(self.name)
