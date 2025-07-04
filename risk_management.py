from datetime import datetime
import pandas as pd
from config import Config

class RiskManager:
    def __init__(self, client):
        self.client = client
        self.daily_start_balance = self.get_usdc_balance()
        self.today = datetime.now().date()
        
    def get_usdc_balance(self):
        return float(self.client.get_asset_balance(asset='USDC')['free'])
        
    def check_daily_loss_limit(self):
        current_balance = self.get_usdc_balance()
        daily_pnl = current_balance - self.daily_start_balance
        daily_loss = -daily_pnl
        
        if daily_loss >= Config.DAILY_LOSS_LIMIT * self.daily_start_balance:
            return False
        return True
        
    def check_max_trades(self, trade_count):
        return trade_count < Config.MAX_TRADES_PER_DAY
        
    def check_risk_limits(self):
        # Verificar se é um novo dia
        if datetime.now().date() != self.today:
            self.daily_start_balance = self.get_usdc_balance()
            self.today = datetime.now().date()
            
        return all([
            self.check_daily_loss_limit(),
            self.check_max_trades(0)  # Implementar contagem de trades
        ])
