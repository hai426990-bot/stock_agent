import logging
import os
from datetime import datetime
from config import Config

log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

level_name = os.getenv('LOG_LEVEL') or ('DEBUG' if Config.FLASK_DEBUG else 'INFO')
log_level = getattr(logging, level_name.upper(), logging.INFO)

logger = logging.getLogger('stock_agent')
logger.setLevel(log_level)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')

log_file = os.path.join(log_dir, f'stock_agent_{datetime.now().strftime("%Y%m%d")}.log')
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(log_level)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)
console_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

__all__ = ['logger']
