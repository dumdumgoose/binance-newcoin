import argparse
import time
from datetime import datetime

from binance.client import Client

# 解析命令行参数
parser = argparse.ArgumentParser()
parser.add_argument('--api_key', type=str, required=True, help='Binance API密钥')
parser.add_argument('--api_secret', type=str, required=True, help='Binance API密钥密文')
parser.add_argument('--symbol', type=str, required=True, help='币种，例如BTC')
parser.add_argument('--order_time', type=str, required=True, help='下单时间，格式为 YYYY-MM-DD HH:MM:SS')
parser.add_argument('--api_server', type=str, required=False, default=Client.BASE_ENDPOINT_DEFAULT,
                    help='下单时间，格式为 YYYY-MM-DD HH:MM:SS')
parser.add_argument('--real', action='store_true', help='是否为真实交易，不设置此flag默认为测试单')
args = parser.parse_args()

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
    print(trade_method)
    return order


# 获取服务器时间并计算延时
def get_server_time():
    server_time = client.get_server_time()
    server_time_ms = server_time['serverTime']
    local_time_ms = int(time.time() * 1000)
    return server_time_ms, local_time_ms


server_time_ms, local_time_ms = get_server_time()
delay = local_time_ms - server_time_ms
print(f"服务器延时: {delay} 毫秒")

# 转换下单时间为时间戳
order_time = datetime.strptime(args.order_time, '%Y-%m-%d %H:%M:%S')
order_timestamp = int(order_time.timestamp() * 1000)

# 等待到指定时间
symbol = args.symbol + 'USDT'
while True:
    current_time_ms = int(time.time() * 1000)
    if (current_time_ms + delay) >= order_timestamp:
        usdt_balance = get_usdt_balance()
        if usdt_balance > 0:
            while True:
                try:
                    order = create_market_order(symbol, usdt_balance)
                    print(f"下单结果: {order}")
                    print(f"总计花费USDT: {usdt_balance}")
                    print(f"下单时间: {datetime.now()}")
                    break
                except Exception as e:
                    print(f"下单失败: {e}")
                    time.sleep(0.1)
            break
        else:
            print("USDT余额不足")
            break
    time.sleep(0.001)  # 频繁检查时间，但避免过度占用CPU
