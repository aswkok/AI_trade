#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data Configuration for AItrade System

This module provides centralized configuration for data storage paths,
ensuring all components use the organized data structure consistently.
"""

import os
from pathlib import Path

# Base data directory
DATA_ROOT = Path(__file__).parent / "data"

# Market Data Paths
MARKET_DATA_ROOT = DATA_ROOT / "market_data"
HISTORICAL_DATA_DIR = MARKET_DATA_ROOT / "historical"
REAL_TIME_DATA_DIR = MARKET_DATA_ROOT / "real_time"
OPTIONS_CHAIN_DIR = MARKET_DATA_ROOT / "options_chain"
FUNDAMENTALS_DIR = MARKET_DATA_ROOT / "fundamentals"

# Trading Logs Paths
TRADING_LOGS_ROOT = DATA_ROOT / "trading_logs"
QUANTITATIVE_LOGS_DIR = TRADING_LOGS_ROOT / "quantitative"
AI_AGENTS_LOGS_DIR = TRADING_LOGS_ROOT / "ai_agents"
BROKER_LOGS_ROOT = TRADING_LOGS_ROOT / "broker_specific"
IBKR_LOGS_DIR = BROKER_LOGS_ROOT / "ibkr"
ALPACA_LOGS_DIR = BROKER_LOGS_ROOT / "alpaca"
LEGACY_LOGS_DIR = BROKER_LOGS_ROOT / "legacy"
ERROR_LOGS_DIR = TRADING_LOGS_ROOT / "error_logs"

# Strategy States Paths
STRATEGY_STATES_ROOT = DATA_ROOT / "strategy_states"
MACD_STATES_DIR = STRATEGY_STATES_ROOT / "macd"
MA_STATES_DIR = STRATEGY_STATES_ROOT / "moving_average"
RSI_STATES_DIR = STRATEGY_STATES_ROOT / "rsi"
BOLLINGER_STATES_DIR = STRATEGY_STATES_ROOT / "bollinger_bands"
OPTIONS_STATES_DIR = STRATEGY_STATES_ROOT / "options"

# AI Reports Paths
AI_REPORTS_ROOT = DATA_ROOT / "ai_reports"
DAILY_ANALYSIS_DIR = AI_REPORTS_ROOT / "daily_analysis"
STRATEGY_RECOMMENDATIONS_DIR = AI_REPORTS_ROOT / "strategy_recommendations"
RISK_ASSESSMENTS_DIR = AI_REPORTS_ROOT / "risk_assessments"
MARKET_SENTIMENT_DIR = AI_REPORTS_ROOT / "market_sentiment"

# Performance Metrics Paths
PERFORMANCE_METRICS_ROOT = DATA_ROOT / "performance_metrics"
DAILY_PERFORMANCE_DIR = PERFORMANCE_METRICS_ROOT / "daily"
WEEKLY_PERFORMANCE_DIR = PERFORMANCE_METRICS_ROOT / "weekly"
MONTHLY_PERFORMANCE_DIR = PERFORMANCE_METRICS_ROOT / "monthly"
YEARLY_PERFORMANCE_DIR = PERFORMANCE_METRICS_ROOT / "yearly"

# Backtest Results Paths
BACKTEST_RESULTS_ROOT = DATA_ROOT / "backtest_results"
BACKTEST_BY_STRATEGY_DIR = BACKTEST_RESULTS_ROOT / "by_strategy"
BACKTEST_BY_SYMBOL_DIR = BACKTEST_RESULTS_ROOT / "by_symbol"
BACKTEST_BY_TIMEFRAME_DIR = BACKTEST_RESULTS_ROOT / "by_timeframe"

# Other Paths
SYSTEM_LOGS_DIR = DATA_ROOT / "system_logs"
REAL_TIME_FEEDS_DIR = DATA_ROOT / "real_time_feeds"

# Legacy paths for backward compatibility
LEGACY_DATA_CACHE_DIR = Path(__file__).parent / "data_cache"
LEGACY_STRATEGY_STATE_DIR = Path(__file__).parent / "strategy_state"
LEGACY_RESULTS_DIR = Path(__file__).parent / "results"


def get_data_path(data_type: str, subtype: str = None) -> Path:
    """
    Get the appropriate data path for a given data type.
    
    Args:
        data_type: Type of data (market_data, logs, states, etc.)
        subtype: Subtype within the data type
        
    Returns:
        Path object for the data location
    """
    path_mapping = {
        'market_data': {
            'historical': HISTORICAL_DATA_DIR,
            'real_time': REAL_TIME_DATA_DIR,
            'options': OPTIONS_CHAIN_DIR,
            'fundamentals': FUNDAMENTALS_DIR
        },
        'logs': {
            'quantitative': QUANTITATIVE_LOGS_DIR,
            'ai_agents': AI_AGENTS_LOGS_DIR,
            'ibkr': IBKR_LOGS_DIR,
            'alpaca': ALPACA_LOGS_DIR,
            'legacy': LEGACY_LOGS_DIR,
            'errors': ERROR_LOGS_DIR,
            'system': SYSTEM_LOGS_DIR
        },
        'states': {
            'macd': MACD_STATES_DIR,
            'moving_average': MA_STATES_DIR,
            'rsi': RSI_STATES_DIR,
            'bollinger_bands': BOLLINGER_STATES_DIR,
            'options': OPTIONS_STATES_DIR
        },
        'ai_reports': {
            'daily': DAILY_ANALYSIS_DIR,
            'recommendations': STRATEGY_RECOMMENDATIONS_DIR,
            'risk': RISK_ASSESSMENTS_DIR,
            'sentiment': MARKET_SENTIMENT_DIR
        },
        'performance': {
            'daily': DAILY_PERFORMANCE_DIR,
            'weekly': WEEKLY_PERFORMANCE_DIR,
            'monthly': MONTHLY_PERFORMANCE_DIR,
            'yearly': YEARLY_PERFORMANCE_DIR
        },
        'backtest': {
            'strategy': BACKTEST_BY_STRATEGY_DIR,
            'symbol': BACKTEST_BY_SYMBOL_DIR,
            'timeframe': BACKTEST_BY_TIMEFRAME_DIR
        }
    }
    
    if data_type not in path_mapping:
        raise ValueError(f"Unknown data type: {data_type}")
    
    if subtype is None:
        # Return the root directory for this data type
        return DATA_ROOT / data_type
    
    if subtype not in path_mapping[data_type]:
        raise ValueError(f"Unknown subtype '{subtype}' for data type '{data_type}'")
    
    return path_mapping[data_type][subtype]


def ensure_data_dir(data_type: str, subtype: str = None) -> Path:
    """
    Ensure a data directory exists and return its path.
    
    Args:
        data_type: Type of data
        subtype: Subtype within the data type
        
    Returns:
        Path object for the data location (guaranteed to exist)
    """
    path = get_data_path(data_type, subtype)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_file_path(log_type: str, filename: str = None) -> Path:
    """
    Get the path for a log file with automatic date-based naming.
    
    Args:
        log_type: Type of log (quantitative, ai_agents, ibkr, etc.)
        filename: Optional specific filename
        
    Returns:
        Path object for the log file
    """
    from datetime import datetime
    
    log_dir = get_data_path('logs', log_type)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    if filename is None:
        # Generate date-based filename
        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f"{log_type}_{date_str}.log"
    
    return log_dir / filename


def migrate_legacy_data():
    """
    Migrate data from legacy directory structure to new organized structure.
    This function should be called once during system upgrade.
    """
    import shutil
    
    migrations = [
        (LEGACY_DATA_CACHE_DIR, HISTORICAL_DATA_DIR, "historical market data"),
        (LEGACY_STRATEGY_STATE_DIR, STRATEGY_STATES_ROOT, "strategy states"),
        (LEGACY_RESULTS_DIR, DAILY_ANALYSIS_DIR, "AI reports")
    ]
    
    for source, target, description in migrations:
        if source.exists():
            print(f"Migrating {description} from {source} to {target}")
            target.mkdir(parents=True, exist_ok=True)
            
            for item in source.glob('*'):
                if item.is_file():
                    target_file = target / item.name
                    if not target_file.exists():
                        shutil.copy2(item, target_file)
                        print(f"  Copied: {item.name}")


# File naming conventions
def get_market_data_filename(symbol: str, start_date: str, end_date: str, data_type: str = "historical") -> str:
    """Generate standardized market data filename."""
    return f"{symbol}_{start_date}_{end_date}.csv"


def get_strategy_state_filename(symbol: str, strategy: str, date: str = None) -> str:
    """Generate standardized strategy state filename."""
    from datetime import datetime
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    return f"{symbol}_{strategy}_state_{date}.json"


def get_ai_report_filename(symbol: str, report_type: str, date: str = None) -> str:
    """Generate standardized AI report filename."""
    from datetime import datetime
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    return f"{symbol}_{report_type}_{date}.md"


# Ensure all directories exist when module is imported
def _initialize_directories():
    """Initialize all data directories."""
    try:
        from data.data_management import DataManager
        DataManager(DATA_ROOT)
    except ImportError:
        # Fallback: create directories manually
        all_dirs = [
            HISTORICAL_DATA_DIR, REAL_TIME_DATA_DIR, OPTIONS_CHAIN_DIR, FUNDAMENTALS_DIR,
            QUANTITATIVE_LOGS_DIR, AI_AGENTS_LOGS_DIR, IBKR_LOGS_DIR, ALPACA_LOGS_DIR,
            LEGACY_LOGS_DIR, ERROR_LOGS_DIR, SYSTEM_LOGS_DIR,
            MACD_STATES_DIR, MA_STATES_DIR, RSI_STATES_DIR, BOLLINGER_STATES_DIR, OPTIONS_STATES_DIR,
            DAILY_ANALYSIS_DIR, STRATEGY_RECOMMENDATIONS_DIR, RISK_ASSESSMENTS_DIR, MARKET_SENTIMENT_DIR,
            DAILY_PERFORMANCE_DIR, WEEKLY_PERFORMANCE_DIR, MONTHLY_PERFORMANCE_DIR, YEARLY_PERFORMANCE_DIR,
            BACKTEST_BY_STRATEGY_DIR, BACKTEST_BY_SYMBOL_DIR, BACKTEST_BY_TIMEFRAME_DIR,
            REAL_TIME_FEEDS_DIR
        ]
        
        for directory in all_dirs:
            directory.mkdir(parents=True, exist_ok=True)


# Initialize directories when module is imported
_initialize_directories()