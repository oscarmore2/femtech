from django.shortcuts import render
import json
from django.http import HttpResponse, HttpResponseRedirect
from .formatMsg import ParseTradingFormat
from .models import DepositAccount, ExcangeSignalTrading, ExchangeConfig, ExchangeOrder, TradingPair, TradingType
from django_q.tasks import async_task, result
from django.views.decorators.csrf import csrf_exempt
import queue
import requests
from django.core.cache import cache
from django_redis import get_redis_connection
from django_q.tasks import async_task,Task,result
from .exchange_api_factory import ExchangeAPIFactory

accountPair = {} # finger-print:Account pair map
signalPair = {} # finger-print:Signal pair map

signalQueue = queue.Queue()
con = get_redis_connection("default")

def resMsg(data):
    return HttpResponse(json.dumps({"ret":200, "data":data}), content_type="text/json")

def resErrObj(data):
    return HttpResponse(json.dumps({"ret":402, "data":data}), content_type="text/json")

def errorMsg(msg):
    print("something went wrong\n======================\n", msg, "\n======================")
    return HttpResponse(json.dumps({"ret":400, "msg":msg}), content_type="text/json")

def attach_order_result(entity:object, data:object):
    re = request.post(entity.signal_api, data=json.dumps(data))
    if re.status == 200:
        data["order_state"] = ExchangeOrder.State.FINISH
    else:
        data["order_state"] = ExchangeOrder.State.FAILD
    entity.order_list.create(exchange_orderId="signal"+re.data.id, trading_pair=entity.trading_pair, order_state=data["order_state"], trading_type=data["trade_type"], amount=data["amount"])
    entity.order_list.save()
    print("信号下单：{0}".format(re))
    pass

def attach_order_result(entity: object, data: object):
    # 在这里根据交易所的 API 进行下单操作
    response = requests.post(entity.signal_api, data=json.dumps(data))
    
    if response.status_code == 200:
        data["order_state"] = ExchangeOrder.State.FINISH
    else:
        data["order_state"] = ExchangeOrder.State.FAILD

    # 创建新的订单记录
    entity.order_list.create(
        exchange_orderId="signal" + str(response.json().get('id')),
        trading_pair=entity.trading_pair,
        order_state=data["order_state"],
        trading_type=data["trade_type"],
        amount=data["amount"]
    )
    entity.order_list.save()

def execute_tasks_signal(fingerPrint: str, entities: object, context: object):
    if signalQueue.qsize() > 0:
        originalSize = signalQueue.qsize()
        
        # 遍历所有的信号实体
        for num in range(originalSize):
            for signalEntity in entities:
                data = {
                    "amount": context["amount"],
                    "timestamp": datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                    "instrument": context["ticker"],
                }

                # 获取最新的订单状态
                order = signalEntity.order_list.filter(order_state=ExchangeOrder.State.FINISH).latest("id")
                
                # 根据交易方向和信号类型执行相应的交易
                if context["direction"] == "long":
                    if signalEntity.signal_type == SignalType.BUY_LOW_ONLY and order.trading_type == TradingType.SELL_FUTURE_LOW:
                        data = json.loads(signalEntity.format_string_enter_long)
                        data["trade_type"] = TradingType.BUY_FUTURE_LOW
                        async_task(attach_order_result, entity=signalEntity, data=data)
                    elif signalEntity.signal_type == SignalType.SELL_HIGH_ONLY and order.trading_type == TradingType.BUY_FUTURE_HIGH:
                        data = json.loads(signalEntity.format_string_exit_short)
                        data["trade_type"] = TradingType.BUY_FUTURE_HIGH
                        async_task(attach_order_result, entity=signalEntity, data=data)
                    elif signalEntity.signal_type == SignalType.DUEL:
                        # 处理双向信号（暂时未实现）
                        pass  # 以后的实现

                elif context["direction"] == "short":
                    if signalEntity.signal_type == SignalType.BUY_LOW_ONLY and order.trading_type == TradingType.BUY_FUTURE_LOW:
                        data = json.loads(signalEntity.format_string_exit_long)
                        data["trade_type"] = TradingType.SELL_FUTURE_LOW
                        async_task(attach_order_result, entity=signalEntity, data=data)
                    elif signalEntity.signal_type == SignalType.SELL_HIGH_ONLY and order.trading_type == TradingType.SELL_FUTURE_HIGH:
                        data = json.loads(signalEntity.format_string_enter_short)
                        data["trade_type"] = TradingType.BUY_FUTURE_HIGH
                        async_task(attach_order_result, entity=signalEntity, data=data)
                    elif signalEntity.signal_type == SignalType.DUEL:
                        # 处理双向信号（暂时未实现）
                        pass  # 以后的实现

def execute_account_trading(fingerPrint: str, accounts: object, context: object):
    for account in accounts:
        # 获取该账户的配置
        exchange_configs = ExchangeConfig.objects.filter(account=account)

        for exchange_config in exchange_configs:
            if not exchange_config.isActive:
                print("{0}未启用，跳过".format(exchange_config.name))
                continue
            
            async_task(execute_trading_single_account, fingerPrint=context["fingerPrint"], exchange_config=exchange_config, context=context)

def execute_trading_single_account(fingerPrint: str, exchange_config: object, context: object):
    # 创建 API 实例
    print(f"欢迎来到{exchange_config.exchangeInfo.name}的交易")
    exchange_api = ExchangeAPIFactory.get_exchange_api(
        exchange_config.exchangeInfo.name,  # 使用 exchangeInfo 获取交易所名称
        exchange_config,  # 直接传递整个配置对象
        exchange_config.exchangeInfo.base_url # 传入基础路径
    )

    # 检查是否有正在执行的订单
    ongoing_orders = ExchangeOrder.objects.filter(
        trading_pair__finger_print=fingerPrint,
        exchange=exchange_config.exchangeInfo
    ).exclude(order_state=ExchangeOrder.State.REVERSE)

    pair = TradingPair.objects.get(finger_print=fingerPrint)

    if ongoing_orders.exists():
        for order in ongoing_orders:
            current_direction = "long"
            if order.trading_type == TradingType.BUY_FUTURE_HIGH:
                current_direction = "short"
            # 判断订单方向与 context["direction"] 是否一致
            # TODO: 以后处理未完成的订单
            if current_direction != context["direction"].lower():
                if not order.exchange_orderId == "-1":
                    response = exchange_api.reverse_order(order.exchange_orderId)
                    if response["success"] == True:
                        print(f" Yeah! Order id {order.id} reverse successful")
                    else:
                        msg = response["msg"]
                        print(f" Order id {order.id} reverse have problem with {msg}")
                else:
                    print(f"Invaild exchange_orderId in order id {order.id}")
            else:
                print(f"Current order {order.id} direction matches context direction: {current_direction}")
    else:
        ord_Type = "buy" if context["direction"] == "long" else "sell"
        trade_type = TradingType.BUY_FUTURE_LOW if context["direction"] == "long" else TradingType.BUY_FUTURE_HIGH
        order = ExchangeOrder.objects.create(
            exchange=exchange_config.exchangeInfo,
            exchange_orderId="-1",
            trading_pair=pair,
            trading_type=trade_type,
            order_state=ExchangeOrder.State.OPEN,  # 订单状态为 FINISH
            amount=context["amount"]
        )
        order.save()
        # 没有找到订单，进行下单操作
        data = {
            "amount": context["amount"],
            "ticker": context["ticker"],
            "direction": context["direction"],
            # 添加其他必要的参数，确保方向与 context 一致
        }
        ord_Type = "buy" if context["direction"] == "long" else "sell"

        # 调用下单方法
        response = exchange_api.place_order(
            trading_pair= pair,
            amount=context["amount"],
            order_type= ord_Type,  # 确保为小写
        )
        if response["success"] == True:  # 假设响应中有 code 字段
            # 更新订单记录
            data = response["data"]
            order_info = response  # 假设响应中包含订单信息
            order.exchange_orderId = data["ordId"]
            order.order_state = ExchangeOrder.State.FINISH
            order.save()
            print("Order placed successfully:", order_info)
        else:
            print("Order placement failed:", response)

def doAccountLogin():
    pass

# Create your views here.
@csrf_exempt
def trade_API_view(request):
    if request.method == "POST":
        txt = request.body.decode("utf-8")
        data = ParseTradingFormat(txt)

        if "fingerPrint" in data:
            # 找到对应的 ExchangeSignalTrading
            signals = ExcangeSignalTrading.objects.filter(trade_pair__finger_print=data["fingerPrint"])
            if signals.exists():
                # 异步任务处理信号交易
                async_task(execute_tasks_signal, fingerPrint=data["fingerPrint"], entities=signals.all(), context=data)

            # 找到对应的 DepositAccount
            accounts = DepositAccount.objects.filter(trade_pair__finger_print=data["fingerPrint"])
            if accounts.exists():
                # 异步任务处理账户交易
                async_task(execute_account_trading, fingerPrint=data["fingerPrint"], accounts=accounts, context=data)

            return resMsg("ok")

        return errorMsg("incoming data wrong, incoming data not correct: {0}".format(txt))

    return errorMsg("wrong method")