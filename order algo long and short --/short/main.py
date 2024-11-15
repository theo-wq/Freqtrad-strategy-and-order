import requests
import json
import hashlib
import time
import hmac
from binance.client import Client
import re
import sys
import time
import os
from watchdog.observers import Observer
from telegram import Bot
from telegram import Update
from watchdog.events import FileSystemEventHandler
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from utils import format_quantity_for_binance
from utils import place_binance_order
from utils import get_binance_price
from utils import format_pair
from utils import sell_buy
from utils import clear_log_file
from utils import get_solde_coin
from utils import format_pair_usd
from utils import start_tab
from utils import check_balance_state
from utils import balance_only
from short_utils import place_binance_short_order
from short_utils import repay_short_binance
from short_utils import get_borrowed_amount

######################################################################################################################################
load_dotenv()

path = '/home/freqtrade/long/user_data/logs/freqtrade.log'
number_of_order = 5
balance = balance_only()
order_price = (balance / number_of_order) - (balance)
liste_crypto = []

######################################################################################################################################
#telegram bot

chat_id =  os.getenv('chat_id')
TOKEN =  os.getenv('TOKEN')

def start_command(update: Update):
    update.send_message("Hello! I am your bot. I will send you a message every time a trade is executed")

def handle_message(update: Update):
    update.send_message("I am a bot, please use the /start command")

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND))


######################################################################################################################################

def start_info ():
    clear_log_file(path)
    start_tab()
    print('valeur definie pour chaque ordre soumis : ', order_price)
    check_balance_state(order_price, balance, number_of_order)
    print('-------------------------------------------------------')
    print('\n')

start_info()

######################################################################################################################################

api_key = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')

######################################################################################################################################

def send_telegram_message(TOKEN, chat_id, message):
    api_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {'chat_id': chat_id, 'text': message}

    response = requests.get(api_url, params=params)

    # Vous pouvez vérifier le statut de la requête
    if response.status_code == 200:
        print("Message envoyé avec succès")
    else:
        print(f"Erreur lors de l'envoi du message. Code d'erreur : {response.status_code}")

######################################################################################################################################

def check_repay_balance(pair):

    client = Client(api_key, api_secret)
    act_price = get_binance_price(pair+'USDT')

    try:
        margin_account = client.get_margin_account(type='cross')

        asset_info = next((asset for asset in margin_account['userAssets'] if asset['asset'] == pair), None)

        if asset_info:
            net_asset = asset_info['netAsset']
            act_price = float(act_price)
            net_asset = float(net_asset)
            net_asset = (net_asset * act_price)
            rounded_net_asset = round(net_asset, 2)
            return rounded_net_asset
        else:
            print(f"L'actif {pair} n'a pas été trouvé dans le compte de marge croisée.")
    except Exception as e:
        print(f"Erreur lors de la récupération de l'actif net : {e}")

######################################################################################################################################

def parse_short_trade_log(log_line):

    entry_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ - freqtrade.persistence.trade_model - INFO - LIMIT_BUY has been fulfilled for Trade\(id=\d+, pair=(\w+/[\w/]+),', log_line)
    exit_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ - freqtrade.freqtradebot - INFO - Exit for (\w+/[\w/]+) detected\. Reason: (.+)', log_line)

    if entry_match:
        timestamp = entry_match.group(1)
        pair = entry_match.group(2)
        signal_type = "Entry"
    elif exit_match:
        timestamp = exit_match.group(1)
        pair = exit_match.group(2)
        signal_type = "Exit"
    else:
        return None, None, None

    return timestamp, pair, signal_type

def process_log_short(log_line):
    global number_of_order_open
    timestamp, pair, signal_type = parse_short_trade_log(log_line)
    if timestamp and pair and signal_type:
        price_currency = get_binance_price(format_pair(pair))
        quantity = order_price / price_currency
        quantity = format_quantity_for_binance(format_pair(pair), quantity)
        if signal_type == 'Entry':
            #print('SHORT :',quantity,' of ', pair, ' for ', order_price)
            #not util due to merge telegram bot
            #send_telegram_message(TOKEN, chat_id, 'SHORT : '+str(quantity)+' of '+str(pair))
            place_binance_short_order(api_key, api_secret, format_pair(pair), quantity, 5)
            print('--------------------------------------------------------------------------------------------------------------------------------------------------------------------------\
--------------------\n')
        if signal_type == 'Exit':
            symbol = pair
            symbol = format_pair(symbol)
            quantity_sell =  get_borrowed_amount(api_key,api_secret,symbol)
            quantity_sell = format_quantity_for_binance(symbol, quantity_sell)
            #print('REPAY :', pair, ' for ', quantity_sell)
            #not util due to merge telegram bot
            #send_telegram_message(TOKEN, chat_id, 'repay : '+str(quantity_sell)+' of '+str(pair))
            repay_short_binance(api_key, api_secret, symbol, quantity_sell, 5)
            remaining_balance = check_repay_balance(symbol)
            send_telegram_message(TOKEN, chat_id, str(remaining_balance)+' USDT of '+str(pair)+' remain in the wallet')
            print('--------------------------------------------------------------------------------------------------------------------------------------------------------------------------\
--------------------\n')

class LogHandlershort(FileSystemEventHandler):
    def __init__(self, log_file_path_short):
        self.log_file_path = log_file_path_short
        self.last_position = 0

    def on_modified(self, event):
        if event.is_directory:
            return
        with open(self.log_file_path, 'r') as file:
            file.seek(self.last_position)
            new_logs = file.readlines()
            for log_line in new_logs:
                process_log_short(log_line)
            self.last_position = file.tell()


log_file_path_short = path

observer = Observer()

log_handler_short = LogHandlershort(log_file_path_short)

observer.schedule(log_handler_short, path=os.path.dirname(log_file_path_short), recursive=False)
observer.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()

observer.join()


######################################################################################################################################
#telegram bot

application.run_polling()



######################################################################################################################################
