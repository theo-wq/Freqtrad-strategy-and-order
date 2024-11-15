import requests
import json
import hashlib
import time
import hmac
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from binance.client import Client
import os
load_dotenv()

######################################################################################################################################

def format_quantity_for_binance(symbol, quantity):

    exchange_info_url = 'https://api.binance.com/api/v3/exchangeInfo'
    exchange_info_response = requests.get(exchange_info_url)
    exchange_info_data = json.loads(exchange_info_response.text)

    for symbol_info in exchange_info_data['symbols']:

        if symbol_info['symbol'] == symbol:
            lot_size_filter = next(filter(lambda x: x['filterType'] == 'LOT_SIZE', symbol_info['filters']), None)
            if lot_size_filter:
                min_qty = float(lot_size_filter['minQty'])
                max_qty = float(lot_size_filter['maxQty'])
                step_size = float(lot_size_filter['stepSize'])

                quantity = float(quantity)

                quantity = round(quantity / step_size) * step_size
                quantity = max(min_qty, min(max_qty, quantity))

                return '{:.8f}'.format(quantity)
            else:
                print(f"Paire {symbol} ne contient pas de filtre LOT_SIZE.")
                return None
    print(f"Paire {symbol} non trouvée dans les informations d'échange.")

    return None

######################################################################################################################################

chat_id =  os.getenv('chat_id')
TOKEN =  os.getenv('TOKEN')

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

def place_binance_order(api_key, api_secret, symbol, side, type, quantity, leverage):

    url = 'https://api.binance.com/sapi/v1/margin/order'

    params = {
        'symbol': symbol,
        'side': side,
        'type': type,
        'quantity': quantity,
        'leverage': leverage,
        'timestamp': int(time.time() * 1000)
    }

    query_string = '&'.join(f"{key}={params[key]}" for key in params)

    signature = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params['signature'] = signature

    headers = {'X-MBX-APIKEY': api_key}
    response = requests.post(url, params=params, headers=headers)

    if response.status_code == 200:
        print('Order with leverage on cross-margin successful!')
        print(json.loads(response.text))
        send_telegram_message(TOKEN, chat_id, '\U0001F535 Long order successful! \U0001F535')
    else:

        print('Error placing order with leverage on cross-margin:')
        print(response.text)
        send_telegram_message(TOKEN, chat_id, 'Error placing order with leverage on cross-margin:')
        send_telegram_message(TOKEN, chat_id, (response.text))


######################################################################################################################################

def get_binance_price(symbol):
    base_url = "https://api.binance.com/api/v3/ticker/price"
    params = {"symbol": symbol}

    response = requests.get(base_url, params=params)

    if response.status_code == 200:

        data = response.json()
        if 'price' in data:

            return float(data['price'])

        else:

            print("La réponse ne contient pas le prix attendu.")
            return None
    else:

        print(f"Erreur lors de la récupération du prix ({response.status_code}): {response.text}")
        return None

######################################################################################################################################

def format_pair(pair):

    formatted_pair = pair.replace('/', '')
    return formatted_pair

######################################################################################################################################

def format_pair_usd (pair):

    formatted = pair.replace('/USDC', '')
    return formatted

######################################################################################################################################

def sell_buy(signal_type):

    if signal_type == 'Entry':
        return 'BUY'
    else :
        return 'SELL'

#####################################################################################################################################

def clear_log_file(file_path):

    try:
        with open(file_path, 'w') as log_file:
            log_file.truncate(0)
        print('\n-------------------------------------------------------')
        print(f"Contenu du fichier de log effacé avec succès.")
    except Exception as e:

        print(f"Une erreur s'est produite : {e}")

######################################################################################################################################
api_key = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')

client = Client(api_key, api_secret)

def get_solde_coin(paire):


    try:
        margin_account = client.get_margin_account(type='cross')

        solde_coin = next((asset['free'] for asset in margin_account['userAssets'] if asset['asset'] == paire), None)

        if solde_coin is not None:

            return solde_coin
        else:

            print(f"Le solde de {paire} n'a pas été trouvé dans le compte de marge croisée.")
    except Exception as e:

        print(f"Erreur lors de la récupération du solde : {e}")

######################################################################################################################################

def start_tab():
    paire = 'USDC'
    try:
        margin_account = client.get_margin_account(type='cross')

        solde_coin = next((asset['free'] for asset in margin_account['userAssets'] if asset['asset'] == paire), None)

        if solde_coin is not None:

            print('-------------------------------------------------------')
            print(f"Solde de {paire} dans le compte de marge : {solde_coin}")
            print('-------------------------------------------------------')

            return solde_coin

        else:

            print(f"Le solde de {paire} n'a pas été trouvé dans le compte de marge croisée.")
    except Exception as e:

        print(f"Erreur lors de la récupération du solde : {e}")

######################################################################################################################################

def balance_only ():
    paire = 'USDC'
    try:
        margin_account = client.get_margin_account(type='cross')

        solde_coin = next((asset['free'] for asset in margin_account['userAssets'] if asset['asset'] == paire), None)

        if solde_coin is not None:

            return solde_coin

        else:

            print(f"Le solde de {paire} n'a pas été trouvé dans le compte de marge croisée.")
    except Exception as e:

        print(f"Erreur lors de la récupération du solde : {e}")

######################################################################################################################################


def check_balance_state (order_price, balance, number_of_order):

    balance = float(balance)
    max_order = balance / number_of_order
    max_order = round(max_order, 2)

    if max_order < order_price:

        print('La balance est insuffisante pour placer',number_of_order, 'ordres a', order_price)
        print('la valeur max de chaque ordre est donc de', max_order)
    else:

        print('La balance est suffisante pour placer',number_of_order, 'ordres a', order_price)
        print('la valeur max de chaque ordre est de', max_order)

######################################################################################################################################

def get_solde_coin_none(paire):

    margin_account = client.get_margin_account(type='cross')
    solde_coin = next((asset['free'] for asset in margin_account['userAssets'] if asset['asset'] == paire), None)
    if solde_coin is not None:
        return solde_coin
    elif solde_coin is None:
        return None

######################################################################################################################################

def get_binance_price_none(symbol):
    base_url = "https://api.binance.com/api/v3/ticker/price"
    params = {"symbol": symbol}

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()
        if 'price' in data:
            return float(data['price'])
        else:
            print("La réponse ne contient pas le prix attendu.")
            return 404
    else:
        print(f"Erreur lors de la récupération du prix ({response.status_code}): {response.text}")
        return 404

######################################################################################################################################

def left_over_check(pair):
    try:
        left_value = get_solde_coin_none(format_pair_usd(pair))
        if left_value == None:
            print('left value is none')
            return 84
        left_value = float(left_value)
        left_value =  left_value * (1 - 0.001)
        formatted_pair = format_pair(pair)
        left_value = format_quantity_for_binance(format_pair(pair), left_value)
        price = get_binance_price_none(formatted_pair)
        price = int(price)
        if price == None:
            price = 0
        left_value = round(float(left_value), 2)
        left_value = left_value * price
        if left_value > 5:
            print('left value is greater than 5')
            place_binance_order(api_key, api_secret, format_pair(pair), 'SELL', 'MARKET', left_value, 5)
        elif left_value <= 5:
            return 84
    except Exception as e:
        error_message = str(e)
        if "n'a pas été trouvé" in error_message and "compte de marge croisée" in error_message:
            print('probleme avec checkpairexist')
        else:
            import traceback
            traceback.print_exc()

######################################################################################################################################