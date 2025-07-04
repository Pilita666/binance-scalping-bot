import time
import logging
import schedule
import pandas as pd
from datetime import datetime, timedelta
from binance.client import Client
from sklearn.ensemble import GradientBoostingClassifier
from joblib import load, dump
from ta import add_all_ta_features
from ta.utils import dropna

from config import Config
from strategies.scalping_strategy import ScalpingStrategy
from risk_management import RiskManager
from monitor import send_alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ScalpingBot:
    def __init__(self):
        self.client = Client(Config.API_KEY, Config.API_SECRET)
        self.risk_manager = RiskManager(self.client)
        self.strategy = ScalpingStrategy()
        self.model = None
        self.load_model()
        self.active_trades = []
        self.performance_metrics = {
            'wins': 0,
            'losses': 0,
            'total_trades': 0,
            'daily_pnl': 0
        }
        
    def load_model(self):
        try:
            self.model = load(Config.MODEL_PATH)
            logger.info("Modelo carregado com sucesso")
        except:
            logger.warning("Modelo não encontrado. Treinando novo modelo...")
            self.train_model()
            
    def train_model(self):
        """Treina o modelo com dados históricos"""
        from data.fetch_data import fetch_historical_data
        
        logger.info("Iniciando coleta de dados para treinamento...")
        df = fetch_historical_data(self.client, Config.TRAINING_PERIOD)
        
        logger.info("Processando dados...")
        df = self.preprocess_data(df)
        
        logger.info("Treinando modelo...")
        X = df.drop(['target'], axis=1)
        y = df['target']
        
        self.model = GradientBoostingClassifier(n_estimators=200, learning_rate=0.1,
                                             max_depth=5, random_state=42)
        self.model.fit(X, y)
        
        logger.info(f"Acurácia do modelo: {self.model.score(X, y):.2%}")
        
        # Salvar modelo
        dump(self.model, Config.MODEL_PATH)
        logger.info("Modelo treinado e salvo")
        
    def preprocess_data(self, df):
        """Prepara os dados para treinamento"""
        df = dropna(df)
        df = add_all_ta_features(df, open="open", high="high", low="low", 
                               close="close", volume="volume")
        
        # Definir target (1 se o preço subiu no próximo período, 0 caso contrário)
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        
        # Remover colunas desnecessárias
        df = df.drop(['open', 'high', 'low', 'close', 'volume'], axis=1)
        
        return dropna(df)
        
    def select_pair(self):
        """Seleciona o melhor par para operar"""
        # Implementação mais sofisticada que considera:
        # - Volatilidade
        # - Volume
        # - Correlação com o mercado
        # - Spread de compra/venda
        pass
        
    def get_features(self, pair):
        """Obtém features em tempo real para o par"""
        klines = self.client.get_klines(symbol=pair, interval=Config.TIMEFRAME, limit=100)
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume',
                                         'close_time', 'quote_asset_volume', 'trades',
                                         'taker_buy_base', 'taker_buy_quote', 'ignore'])
        
        df = df.astype({
            'open': float, 'high': float, 'low': float, 
            'close': float, 'volume': float
        })
        
        df = add_all_ta_features(df, open="open", high="high", low="low", 
                               close="close", volume="volume")
        
        return df.iloc[-1:].drop(['open', 'high', 'low', 'close', 'volume'], axis=1)
        
    def execute_trade(self, pair, signal):
        """Executa a operação com gerenciamento de risco"""
        if not self.risk_manager.check_risk_limits():
            logger.warning("Limites de risco atingidos. Nenhuma operação será executada.")
            return
            
        try:
            ticker = self.client.get_symbol_ticker(symbol=pair)
            price = float(ticker['price'])
            
            # Calcular tamanho da posição com base no gerenciamento de risco
            usdc_balance = float(self.client.get_asset_balance(asset='USDC')['free'])
            trade_size = min(Config.MAX_TRADE_SIZE * usdc_balance, usdc_balance * 0.5)
            quantity = trade_size / price
            
            if signal == 'buy':
                order = self.client.create_order(
                    symbol=pair,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_MARKET,
                    quantity=self.round_quantity(pair, quantity)
                )
                
                # Registrar trade ativo
                self.active_trades.append({
                    'pair': pair,
                    'entry_price': price,
                    'quantity': quantity,
                    'entry_time': datetime.now(),
                    'stop_loss': price * (1 - Config.STOP_LOSS),
                    'take_profit': price * (1 + Config.TAKE_PROFIT)
                })
                
                logger.info(f"Compra executada: {quantity:.4f} {pair} a {price:.6f}")
                send_alert(f"📈 COMPRA {pair} - Preço: {price:.6f}")
                
            elif signal == 'sell':
                # Verificar se temos o ativo
                base_asset = pair.replace('USDC', '')
                balance = float(self.client.get_asset_balance(asset=base_asset)['free'])
                
                if balance >= quantity:
                    order = self.client.create_order(
                        symbol=pair,
                        side=SIDE_SELL,
                        type=ORDER_TYPE_MARKET,
                        quantity=self.round_quantity(pair, quantity)
                    )
                    
                    # Registrar trade
                    self.performance_metrics['total_trades'] += 1
                    pnl = (price - next(t['entry_price'] for t in self.active_trades if t['pair'] == pair)) * quantity
                    self.performance_metrics['daily_pnl'] += pnl
                    
                    if pnl > 0:
                        self.performance_metrics['wins'] += 1
                    else:
                        self.performance_metrics['losses'] += 1
                    
                    logger.info(f"Venda executada: {quantity:.4f} {pair} a {price:.6f}")
                    send_alert(f"📉 VENDA {pair} - Preço: {price:.6f} | PnL: ${pnl:.2f}")
                    
        except Exception as e:
            logger.error(f"Erro ao executar ordem: {str(e)}")
            send_alert(f"❌ ERRO na ordem: {str(e)}")
            
    def round_quantity(self, pair, quantity):
        """Arredonda a quantidade para o tamanho de lote permitido"""
        info = self.client.get_symbol_info(pair)
        step_size = float([f['stepSize'] for f in info['filters'] if f['filterType'] == 'LOT_SIZE'][0])
        return round(int(quantity / step_size) * step_size, 8)
        
    def monitor_trades(self):
        """Monitora trades ativos e executa SL/TP"""
        for trade in self.active_trades[:]:
            ticker = self.client.get_symbol_ticker(symbol=trade['pair'])
            current_price = float(ticker['price'])
            
            # Verificar stop loss
            if current_price <= trade['stop_loss']:
                self.execute_trade(trade['pair'], 'sell')
                self.active_trades.remove(trade)
                send_alert(f"🛑 STOP LOSS acionado para {trade['pair']}")
                
            # Verificar take profit
            elif current_price >= trade['take_profit']:
                self.execute_trade(trade['pair'], 'sell')
                self.active_trades.remove(trade)
                send_alert(f"🎯 TAKE PROFIT acionado para {trade['pair']}")
                
            # Verificar tempo máximo
            elif (datetime.now() - trade['entry_time']).seconds > 300:  # 5 minutos
                self.execute_trade(trade['pair'], 'sell')
                self.active_trades.remove(trade)
                send_alert(f"⏰ Trade expirado por tempo para {trade['pair']}")
                
    def run(self):
        """Loop principal do bot"""
        logger.info("Iniciando bot de scalping avançado...")
        send_alert("🤖 Bot iniciado com sucesso")
        
        # Agendar tarefas
        schedule.every(10).seconds.do(self.trading_cycle)
        schedule.every(1).minutes.do(self.monitor_trades)
        schedule.every(6).hours.do(self.risk_manager.check_risk_limits)
        schedule.every(Config.RETRAIN_INTERVAL).days.do(self.train_model)
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Encerrando bot...")
                send_alert("🛑 Bot encerrado pelo usuário")
                break
            except Exception as e:
                logger.error(f"Erro no loop principal: {str(e)}")
                send_alert(f"⚠️ ERRO no bot: {str(e)}")
                time.sleep(60)
                
    def trading_cycle(self):
        """Ciclo completo de trading"""
        pair = self.select_pair()
        if not pair:
            return
            
        features = self.get_features(pair)
        prediction = self.model.predict(features)
        confidence = self.model.predict_proba(features).max()
        
        # Só opera se a confiança for alta
        if confidence > 0.7:
            signal = 'buy' if prediction[0] == 1 else 'sell'
            self.execute_trade(pair, signal)
