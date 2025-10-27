"""
Configuration loader with environment variable support
"""
import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def load_config(config_file: str = 'settings.json') -> Dict[str, Any]:
    """
    Load configuration from JSON file with environment variable override support
    
    Environment variables can override settings using the pattern:
    MT5_TELEGRAM_BOT_TOKEN, MT5_TELEGRAM_CHAT_ID, etc.
    
    :param config_file: Path to configuration file
    :return: Configuration dictionary
    """
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Override sensitive values with environment variables if present
        if 'telegram' in config:
            bot_token = os.getenv('MT5_TELEGRAM_BOT_TOKEN')
            chat_id = os.getenv('MT5_TELEGRAM_CHAT_ID')
            
            if bot_token:
                config['telegram']['bot_token'] = bot_token
                logger.info("Using Telegram bot token from environment variable")
            
            if chat_id:
                config['telegram']['chat_id'] = chat_id
                logger.info("Using Telegram chat ID from environment variable")
        
        # Override MT5 credentials with environment variables if present
        if 'accounts' in config:
            for idx, account in enumerate(config['accounts']):
                username = os.getenv(f'MT5_ACCOUNT_{idx}_USERNAME')
                password = os.getenv(f'MT5_ACCOUNT_{idx}_PASSWORD')
                
                if username:
                    account['username'] = username
                    logger.info(f"Using account {idx} username from environment variable")
                
                if password:
                    account['password'] = password
                    logger.info(f"Using account {idx} password from environment variable")
        
        return config
        
    except FileNotFoundError:
        logger.error(f"Configuration file '{config_file}' not found")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        raise


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration structure and required fields
    
    :param config: Configuration dictionary
    :return: True if valid, False otherwise
    """
    if not config:
        logger.error("Configuration is empty")
        return False
    
    # Check accounts
    if 'accounts' not in config or not config['accounts']:
        logger.error("No accounts configured")
        return False
    
    required_account_fields = ['server', 'username', 'password', 'mt5_pathway']
    
    for idx, account in enumerate(config['accounts']):
        for field in required_account_fields:
            if field not in account or not account[field]:
                logger.error(f"Account {idx} missing required field: {field}")
                return False
    
    # Validate Telegram settings if enabled
    if config.get('telegram', {}).get('enabled', False):
        telegram_fields = ['bot_token', 'chat_id']
        for field in telegram_fields:
            if field not in config.get('telegram', {}) or not config['telegram'][field]:
                logger.error(f"Telegram enabled but missing required field: {field}")
                return False
    
    # Validate Ollama settings if enabled
    if config.get('ollama', {}).get('enabled', False):
        if 'model' not in config.get('ollama', {}):
            logger.warning("Ollama enabled but no model specified, using default")
    
    logger.info("Configuration validation passed")
    return True