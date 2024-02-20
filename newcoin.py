import argparse
import json
import time
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

from binance.client import Client
from loguru import logger

# 解析命令行参数
parser = argparse.ArgumentParser()
parser.add_argument('--api_key', type=str, required=True, help='Binance API密钥')
parser.add_argument('--api_secret', type=str, required=True, help='Binance API密钥密文')
parser.add_argument('--symbol', type=str, required=True, help='币种，例如BTC')
parser.add_argument('--order_time', type=str, required=True, help='下单时间，格式为 YYYY-MM-DD HH:MM:SS')
parser.add_argument('--api_server', type=str, required=False, default=Client.BASE_ENDPOINT_DEFAULT,
                    help='下单时间，格式为 YYYY-MM-DD HH:MM:SS')
parser.add_argument('--limit', action='store_true', help='是否使用限价单')
parser.add_argument('--price', type=float, required=False, help='限价单的价格')
parser.add_argument('--real', action='store_true', help='是否为真实交易，不设置此flag默认为测试单')
args = parser.parse_args()

if args.limit and not args.price:
    parser.error("限价单需要指定--price参数")

client = Client(args.api_key, args.api_secret, base_endpoint=args.api_server)


# 获取账户的USDT余额
def get_usdt_balance():
    account = client.get_account()
    usdt_balance = next((item for item in account['balances'] if item["asset"] == 'USDT'), None)
    return float(usdt_balance['free']) if usdt_balance else 0


# 创建市价单
def create_market_order(symbol, quantity):
    trade_method = client.create_order if args.real else client.create_test_order
    order = trade_method(
        symbol=symbol,
        side=Client.SIDE_BUY,
        type=Client.ORDER_TYPE_MARKET,
        quoteOrderQty=quantity
    )
    return order


def create_limit_order(symbol, quantity, price):
    trade_method = client.create_order if args.real else client.create_test_order
    order = trade_method(
        symbol=symbol,
        side=Client.SIDE_BUY,
        type=Client.ORDER_TYPE_LIMIT,
        timeInForce=Client.TIME_IN_FORCE_GTC,
        price=str(price),
        quantity=str(quantity)
    )
    return order


# 获取服务器时间并计算延时
def get_server_time():
    server_time = client.get_server_time()
    server_time_ms = server_time['serverTime']
    local_time_ms = int(time.time() * 1000)
    return server_time_ms, local_time_ms


def get_precision(symbol):
    info = client.get_symbol_info(symbol)
    if info:
        filters = {item['filterType']: item for item in info['filters']}
        quantity_precision = None

        if 'LOT_SIZE' in filters:
            quantity_precision = max(len(filters['LOT_SIZE']['stepSize'].rstrip('0').split('.')[-1]), 0)

        return quantity_precision
    else:
        return 2


def adjust_quantity_to_precision(quantity, precision):
    print(precision)
    if precision is not None:
        format_str = '{:0.' + str(precision) + 'f}'
        return format_str.format(Decimal(str(quantity)).quantize(Decimal('1.' + '0' * precision), rounding=ROUND_DOWN))
    else:
        return quantity


server_time_ms, local_time_ms = get_server_time()
delay = local_time_ms - server_time_ms
logger.info(f"服务器延时: {delay} 毫秒")

# 转换下单时间为时间戳
order_time = datetime.strptime(args.order_time, '%Y-%m-%d %H:%M:%S')
order_timestamp = int(order_time.timestamp() * 1000)

last_output_time = None

# 等待到指定时间
symbol = args.symbol + 'USDT'
five_seconds_in_micro_seconds = 5 * 1000 * 1000

quantity_precision = get_precision(symbol)

usdt_balance = get_usdt_balance()
logger.info(f"当前USDT余额: {usdt_balance}")

quantity = adjust_quantity_to_precision(usdt_balance / args.price if args.limit else 0, quantity_precision)
if args.limit:
    logger.info(f"预计购买数量: {quantity}")

while True:
    now = datetime.now()
    delta = order_time - now

    # 检查是否需要输出剩余时间
    if last_output_time is None or (now - last_output_time).total_seconds() >= 5:
        logger.info(f"等待下单时间剩余: {delta.seconds} 秒")
        last_output_time = now  # 更新上次输出时间

    current_time_ms = int(time.time() * 1000)
    if (current_time_ms + delay) >= order_timestamp:
        if usdt_balance > 0:
            while True:
                try:
                    order = None
                    if args.limit:
                        order = create_limit_order(symbol, quantity, args.price)
                    else:
                        order = create_market_order(symbol, usdt_balance)
                    logger.info(f"下单结果: {json.dumps(order, indent=2)}")
                    logger.info(f"总计花费USDT: {usdt_balance}")
                    logger.info(f"下单时间: {datetime.now()}")
                    break
                except Exception as e:
                    logger.error(f"下单失败: {e}")
                    time.sleep(0.1)
            break
        else:
            logger.error("USDT余额不足")
            break
    time.sleep(0.001)  # 频繁检查时间，但避免过度占用CPU
