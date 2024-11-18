from django.shortcuts import render
import json
from django.http import HttpResponse, HttpResponseRedirect
from .formatMsg import ParseTradingFormat
from .models import DepositAccount, ExcangeSignalTrading
from django_q.tasks import async_task, result
from django.views.decorators.csrf import csrf_exempt
from Queue import Queue
import requests
from django.core.cache import cache
from django_redis import get_redis_connection
from django_q.tasks import async_task,Task,result
from .exchange_api_factory import ExchangeAPIFactory

accountPair = {} # finger-print:Account pair map
signalPair = {} # finger-print:Signal pair map

signalQueue = Queue()
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
            # 创建 API 实例
            exchange_api = ExchangeAPIFactory.get_exchange_api(
                exchange_config.exchangeInfo.name,  # 使用 exchangeInfo 获取交易所名称
                exchange_config  # 直接传递整个配置对象
            )

            # 检查是否有正在执行的订单
            ongoing_orders = ExchangeOrder.objects.filter(
                trading_pair__finger_print=fingerPrint,
                order_state=ExchangeOrder.State.FINISH
            )

            if ongoing_orders.exists():
                for order in ongoing_orders:
                    # 判断订单方向与 context["direction"] 是否一致
                    current_direction = order.trading_type  # 假设 trading_type 存储了订单方向
                    if current_direction != context["direction"]:
                        # 反转持仓方向
                        response = exchange_api.reverse_order(order.exchange_orderId)
                        if response.get('code') == 200:  # 假设响应中有 code 字段
                            # 更新订单记录
                            order.order_state = ExchangeOrder.State.REVERSED  # 假设有一个 REVERSED 状态
                            order.trading_type = context["direction"]  # 更新方向为新的方向
                            order.save()
                            print(f"Order {order.exchange_orderId} reversed successfully.")
                        else:
                            print(f"Failed to reverse order {order.exchange_orderId}: {response}")
                    else:
                        print(f"Current order direction matches context direction: {current_direction}")

            else:
                # 没有找到订单，进行下单操作
                data = {
                    "amount": context["amount"],
                    "ticker": context["ticker"],
                    "direction": context["direction"],
                    # 添加其他必要的参数，确保方向与 context 一致
                }
                # 调用下单方法
                response = exchange_api.place_order(
                    trading_pair=fingerPrint,
                    amount=context["amount"],
                    order_type=context["direction"].lower(),  # 确保为小写
                    pos_side=context.get("pos_side", "LONG")  # 默认使用 LONG 或根据需要修改
                )
                if response.get('code') == 200:  # 假设响应中有 code 字段
                    # 更新订单记录
                    order_info = response  # 假设响应中包含订单信息
                    ExchangeOrder.objects.create(
                        exchange_orderId=order_info.get('id'),
                        trading_pair=fingerPrint,
                        order_state=ExchangeOrder.State.FINISH,  # 订单状态为 FINISH
                        trading_type=context["direction"],  # 设置为当前方向
                        amount=context["amount"]
                    )
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