import requests
from config import Config

def send_alert(message):
    if Config.TELEGRAM_TOKEN and Config.TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
            params = {
                'chat_id': Config.TELEGRAM_CHAT_ID,
                'text': message
            }
            requests.post(url, params=params)
        except Exception as e:
            print(f"Erro ao enviar alerta: {e}")
