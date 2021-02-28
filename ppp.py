import json, datetime
import numpy as np
import talib
import math
from time import sleep
from binance.enums import ORDER_STATUS_FILLED
from binance.client import Client


#######CONFIGS

def client():
    api_key = ''
    api_secret = ''
    client = Client(api_key, api_secret)

    return client


try:
    config_file = open('bd_config.json', 'r+')
except:
    config_file = open('bd_config.json', 'w+')
    config_default = [
        {
            "currency": "QTUMBTC",
            "kline": {
                "interval": "5m",
                "limit": 60,
            },
            "conditions": {
                "buyIfHave": False,
                "buyFor": 0.0015,
                "common_take_profit": 5,  ## percents
                "RSI": {
                    "enable": True,
                    "buy": 30,
                    "time_period": 14,
                    "sell_profit": 5  ## percents
                },
            },
            "insurance": [
                {
                    "percent": 1,
                    "value": 0.001,
                }
            ],
            "onRedCandles": {
                "repeat": 3,
                "down_price": 1
            },
            "onGreenCandles": {
                "repeat": 3,
                "up_price": 2
            }
        }
    ]
    config_file.write(json.dumps(config_default, sort_keys=True, indent=4))

    config_file = open('bd_config.json', 'w+')

config = json.load(config_file)


#######Functions:


def percent_calc(new, old):
    new = float(new)
    old = float(old)

    try:
        change = (new - old) / ((new + old) / 2) * 100

        return round(change, 3)

    except:
        return 0


def log(currency, text) -> int:
    with open("logs.txt", "a") as handler:
        temp = "[COIN: {}][{}] {} \n"

        return handler.write(temp.format(currency, datetime.datetime.now(), text))


### Data layer


class KlineObject:
    kline = {}

    def __init__(self, kline):
        self.kline = kline

    def _get_key(self, idx: int) -> any:
        return self.kline[idx]

    def open_time(self):
        return self._get_key(0)

    def open(self):
        return self._get_key(1)

    def high(self):
        return self._get_key(2)

    def low(self):
        return self._get_key(3)

    def close(self):
        return self._get_key(4)

    def price(self):
        return self.close()

    def volume(self):
        return self._get_key(5)

    def close_time(self):
        return self._get_key(6)

    def quote_asset_volume(self):
        return self._get_key(7)

    def number_of_trades(self):
        return self._get_key(8)

    def buy_base_asset_volume(self):
        return self._get_key(9)

    def buy_quote_asset_volume(self):
        return self._get_key(10)


class KlineComparator:
    def compare(old_kline: KlineObject, new_kline: KlineObject) -> dict:
        params = {
            "ready": False,
            "price": {
                "down": False,
                "up": False,
                "percent_change": percent_calc(new_kline.price(), old_kline.price()),
                "old": old_kline.close(),
                "new": new_kline.close()
            },
            "vol": {
                "down": False,
                "up": False,
                "percent_change": percent_calc(new_kline.buy_quote_asset_volume(), old_kline.buy_quote_asset_volume()),
                "old": old_kline.buy_quote_asset_volume(),
                "new": new_kline.buy_quote_asset_volume()
            },
            "time_interval": False,
            "time_interval_minute": False,
            "date_old": datetime.datetime.fromtimestamp(old_kline.close_time() / 1000).strftime("%Y-%m-%d %H:%M:%S"),
            "date_new": datetime.datetime.fromtimestamp(new_kline.close_time() / 1000).strftime("%Y-%m-%d %H:%M:%S")
        }

        ## price compare

        if new_kline.price() > old_kline.price():
            params['price']['up'] = True
        else:
            params['price']['down'] = True

        ## volume compare
        if new_kline.buy_quote_asset_volume() > old_kline.buy_quote_asset_volume():
            params['vol']['up'] = True
        else:
            params['vol']['down'] = True

        params['time_interval'] = new_kline.close_time() - old_kline.close_time()
        params['time_interval_minute'] = (params['time_interval'] / 60) / 1000

        params['ready'] = True
        return params


class Worker:
    config = {}
    currency = ''
    klines = []

    def __init__(self, config, currency):
        self.config = config
        self.currency = currency

    def onRedCandles(self):
        return self

    def onGreenCandles(self):
        return self

    def process(self):
        _client = client()

        balance = _client.get_asset_balance(self.currency[:-3])

        if float(balance['free']) > 0 or float(balance['locked']) > 0:
            log(self.currency, "Already have this currency. Dont' buy")

            ## todo getting currency trades and sell it for takeprofit

            return

        klines = _client.get_klines(
            symbol=self.currency,
            interval=self.config['kline']['interval'],
            limit=self.config['kline']['limit']
        )

        normalized_klines = []

        for raw_kline in klines:
            normalized_klines.append(KlineObject(raw_kline))

        rsi_data = []

        for idx in range(0, len(normalized_klines)):
            if idx > 0:
                compared = KlineComparator.compare(normalized_klines[idx - 1], normalized_klines[idx])

                if (self.config['conditions']['RSI']['enable'] == True):
                    rsi_data.append(float(compared['price']['new']))

        ## RSI situation
        if (self.config['conditions']['RSI']['enable'] == True):

            period_rsi = self.config['conditions']['RSI']['time_period']

            RSI = talib.RSI(np.array(rsi_data), timeperiod=period_rsi)

            if RSI[len(RSI) - 1] < self.config['conditions']['RSI']['buy']:
                log(self.currency, "Buy , because RSI is {}".format(RSI[len(RSI) - 1]))

                ticker = _client.get_ticker(symbol=self.currency)
                last_price = float(ticker['lastPrice']) + (float(ticker['lastPrice']) * 0.01)
                count_coins = float(self.config['conditions']['buyFor']) / last_price
                log(self.currency,
                    "Placing Market-Buy order for price {}, total {}".format(format(last_price, '.8f'), count_coins))

                try:
                    order_placing = _client.order_limit_buy(
                        symbol=self.currency,
                        price=format(last_price, '.8f'),
                        quantity=math.floor(count_coins)
                    ) print(order_placing)

                    ## todo make insurance order

                    sleep(2)

                    #if order_placing['status'] == ORDER_STATUS_FILLED:
                        ## if order filled, we place sell order with takeprofit

                    sell_price = float(last_price + (float(self.config['conditions']['RSI']['sell_profit']) * last_price))
                    sell_price = "{}".format(format(sell_price, '.8f'))
                    sell_order = _client.order_limit_sell(
                        symbol=self.currency,
                        quantity=math.floor(count_coins),
                        price=sell_price
                    )

                    print(sell_order)

                    log(self.currency, "Sell order placed.")

                except:
                    pass
                    log(self.currency, "Have a some problems, with RSI B/S operation.")

        else:
            RSI = False


### Exchange logic


# Client = client()

# candles = Client.get_klines(symbol="EOSBTC", interval=Client.KLINE_INTERVAL_5MINUTE, limit=5)

for currconfig in config:
    worker = Worker(currconfig, currconfig['currency'])
    worker.process()