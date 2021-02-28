#######Binance Pump detector
#START: screen -AdmS loc python3 binance_pd.py or python3 binance_pd.py
#STOP: screen -dr loc + ctrl c

from binance.client import Client
from binance.websockets import BinanceSocketManager
import requests
import json, os

#######CONFIG########
api_key = ''
api_secret = ''

telegram_bot_token = ''
telegram_chat_id = ''

dump_notify = True

if dump_notify:
    ### DUMP NOTIFIER CONFIG
    dump_notify_percent_change = -1  # price change in percents

pump_notify = True

if pump_notify:
    ### PUMP NOTIFIER CONFIG
    pump_notify_percent_change = 1  # price change in percents


#####################
###FUNCTIONS


def send_message(text):
    global telegram_bot_token, telegram_chat_id
    sstr = "https://api.telegram.org/bot{}/sendMessage".format(telegram_bot_token)
    payload = {
        "chat_id": telegram_chat_id,
        "text": text,
        "parse_mode": "markdown"
    }

    return requests.post(sstr, payload).content


def percent_calc(new, old):
    new = float(new)
    old = float(old)

    change = (new - old) / ((new + old) / 2) * 100

    return round(change, 3)


def link(pair):
    return "https://binance.com/trade.html?symbol={}".format(pair)
	

#####################
client = Client(api_key, api_secret)

bm = BinanceSocketManager(client)

base_pair = "BTC"
data = dict()
pairs = []
ticker = client.get_ticker()

for _row in ticker:
    if "BTC" in _row['symbol']:
        pairs.append(_row)
    else:
        continue

print("Pairs collected")

sockets = []
for pair in pairs:
    kkey = "%s@ticker" % pair['symbol']
    sockets.append(kkey.lower())

print("Socket keys collected")

print("Starting sockets")


def send_dump_message(data, pchange, old):
    print(send_message(
        "↘️ Dumping `{}` \n ✨Price change {} % \n 💸Price: {} ({}) \n 💰 {}".format(data['pair'], pchange,
                                                                                 data['last_price'],
                                                                                 old['last_price'],
                                                                                 link(data['pair']))))


def send_pump_message(data, pchange, old):
    print(send_message(
        "↗️ Pumping `{}` \n ✨Price change {} % \n 💸Price {} ({}) \n 💰 {}".format(data['pair'], pchange,
                                                                                data['last_price'],
                                                                                old['last_price'], link(data['pair']))))


def process_update(last_data, new_data):
    # print("-")
    # pchange = round(float(new_data['price_change_percent']) - float(last_data['price_change_percent']), 4)

    pchange = percent_calc(new_data['last_price'], last_data['last_price'])

    # print("Changes {}  , new {} , last {}, Change {} ".format(new_data['pair'],new_data['price_change_percent'],last_data['price_change_percent'], pchange))

    if dump_notify and pchange < 0 and pchange < float(dump_notify_percent_change):
        send_dump_message(new_data, pchange, last_data)

    if pump_notify and pchange > 0 and pchange > float(pump_notify_percent_change):
        send_pump_message(new_data, pchange, last_data)


# todo process sckt msg
def on_message(msg):
    fmess = convert_message_keys_to_normal(msg['data'])
    # print("stream: {} data: {}".format(msg['stream'], msg['data']))
    # print("Ticker {} , DATA: {}".format(msg['stream'], fmess))

    # process updates
    if fmess['pair'] in data:
        process_update(data.pop(fmess['pair']), fmess)

    # save data
    data[fmess['pair']] = fmess
	
#def on_message(msg):
    #fmess = convert_message_keys_to_normal(msg['data'])
    # print("stream: {} data: {}".format(msg['stream'], msg['data']))
    # print("Ticker {} , DATA: {}".format(msg['stream'], fmess))

    ##SAVE to json

    #fname = "{}.json".format(fmess['pair'])

    #try:
        #fh = open(fname, 'r+')
    #except:
        # if file does not exist, create it
        #fh = open(fname, 'w+')

    #with fh as handle:
        #try:
            #jdata = json.load(handle.read())

            #jdata["data"].append(fmess)
        #except:
            # handle error
            #jdata = {
                #"data": []
            #}
            #jdata['data'][0] = fmess

        #handle.flush()
        #handle.truncate()
        #json.dump(jdata, handle)

    # process updates
    #if fmess['pair'] in data:
        #process_update(data.pop(fmess['pair']), fmess)

    # save data
    #data[fmess['pair']] = fmess


def convert_message_keys_to_normal(message):
    new_message = {
        "pair": message['s'],
        "price_change": message['p'],
        "price_change_percent": message['P'],
        "last_price": message['c']
    }

    return new_message


socket_connection = bm.start_multiplex_socket(sockets, on_message)
# socket_connection = bm.start_multiplex_socket(['eosbtc@ticker'], on_message)

bm.start()
