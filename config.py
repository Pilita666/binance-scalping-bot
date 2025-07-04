import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Binance
    API_KEY = os.getenv('BINANCE_API_KEY')
    API_SECRET = os.getenv('BINANCE_API_SECRET')
    
    # Configurações de trading
    BASE_ASSET = 'USDC'
    QUOTE_ASSETS = ['USDC']
    EXCLUDE_PAIRS = ['USDCUSDC']
    TIMEFRAME = '1m'
    TRAINING_PERIOD = '365 days ago UTC'
    
    # Parâmetros de risco
    MAX_TRADE_SIZE = 0.1  # 10% do capital
    DAILY_LOSS_LIMIT = 0.05  # 5%
    STOP_LOSS = 0.01  # 1%
    TAKE_PROFIT = 0.02  # 2%
    MAX_TRADES_PER_DAY = 100
    
    # Configurações do modelo
    MODEL_PATH = 'models/scalping_model.pkl'
    RETRAIN_INTERVAL = 7  # dias
    
    # Monitoramento
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
