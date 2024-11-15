import requests
import json
import hashlib
import time
import hmac
import re
import time
import sys
import os
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from binance.client import Client
load_dotenv()


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

def place_binance_short_order(api_key, api_secret, symbol, quantity, leverage):
    try:
        # Endpoint pour passer des ordres à découvert sur Binance
        url = 'https://api.binance.com/sapi/v1/margin/order'

        # Paramètres de l'ordre
        params = {
            'symbol': symbol,
            'side': 'SELL',  # 'SELL' pour un ordre de vente à découvert
            'sideEffectType': 'MARGIN_BUY',  # 'MARGIN_BUY' pour emprunter des fonds pour l'ordre
            'type': 'MARKET',  # 'MARKET' pour un ordre au marché
            'quantity': (quantity),
            'leverage': leverage,
            'timestamp': int(time.time() * 1000)
        }

        # Création de la chaîne de requête pour la signature
        query_string = '&'.join(f"{key}={params[key]}" for key in params)

        # Génération de la signature HMAC
        signature = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        params['signature'] = signature

        # En-tête de la requête avec la clé API
        headers = {'X-MBX-APIKEY': api_key}

        # Envoi de la requête POST
        response = requests.post(url, params=params, headers=headers)

        # Vérification de la réponse
        if response.status_code == 200:
            print(json.loads(response.text))
            send_telegram_message(TOKEN, chat_id, '\U0001F535 short order successful! \U0001F535')

        else:
            print(f'Erreur lors du placement de l\'ordre de vente à découvert avec effet de levier. Code d\'état : {response.status_code}')
            print(response.text)
            send_telegram_message(TOKEN, chat_id, 'Error placing order with leverage on cross-margin:')
            send_telegram_message(TOKEN, chat_id, (response.text))
    except Exception as e:
        print(f'Une erreur s\'est produite : {str(e)}')


######################################################################################################################################

def repay_short_binance(api_key, api_secret, symbol, quantity, leverage):
    try:
        # Endpoint pour passer des ordres à découvert sur Binance
        url = 'https://api.binance.com/sapi/v1/margin/order'

        # Paramètres de l'ordre
        params = {
            'symbol': symbol,
            'side': 'BUY',  # 'SELL' pour un ordre de vente à découvert
            'sideEffectType': 'AUTO_REPAY',  # 'MARGIN_BUY' pour emprunter des fonds pour l'ordre
            'type': 'MARKET',  # 'MARKET' pour un ordre au marché
            'quantity': (quantity),
            'leverage': leverage,
            'timestamp': int(time.time() * 1000)
        }

        # Création de la chaîne de requête pour la signature
        query_string = '&'.join(f"{key}={params[key]}" for key in params)

        # Génération de la signature HMAC
        signature = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        params['signature'] = signature

        # En-tête de la requête avec la clé API
        headers = {'X-MBX-APIKEY': api_key}

        # Envoi de la requête POST
        response = requests.post(url, params=params, headers=headers)

        # Vérification de la réponse
        if response.status_code == 200:
            print(json.loads(response.text))
            send_telegram_message(TOKEN, chat_id, '\U00002705 Repay order successful! \U00002705')

        else:
            print(f'Erreur lors du placement de l\'ordre de vente à découvert avec effet de levier. Code d\'état : {response.status_code}')
            print(response.text)
            send_telegram_message(TOKEN, chat_id, 'Error placing Repay order with leverage on cross-margin:')
            send_telegram_message(TOKEN, chat_id, (response.text))
    except Exception as e:
        print(f'Une erreur s\'est produite : {str(e)}')


######################################################################################################################################


def get_borrowed_amount(api_key, api_secret, symbol):

    client = Client(api_key, api_secret)

    margin_info = client.get_margin_account()
    for asset in margin_info['userAssets']:
        if asset['asset'] == symbol[:-4]:
            borrowed_amount = float(asset['borrowed'])
            print(f"Emprunt trouvé pour la paire {symbol}: {borrowed_amount}")
            return borrowed_amount
    else:
        raise ValueError(f"Aucune information sur l'emprunt trouvée pour la paire {symbol}")

######################################################################################################################################
