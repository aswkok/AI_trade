#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data Management Utility for AItrade System

This script provides utilities for managing the data storage structure,
including cleanup, compression, and organization of trading data.
"""

import os
import gzip
import json
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataManager:
    """Manages data storage, cleanup, and organization for AItrade system."""
    
    def __init__(self, data_root: str = None):
        """Initialize the data manager.
        
        Args:
            data_root: Root directory for data storage. Defaults to ./data
        """
        if data_root is None:
            data_root = Path(__file__).parent
        self.data_root = Path(data_root)
        
        # Ensure all directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all required directories exist."""
        required_dirs = [
            'market_data/historical',
            'market_data/real_time', 
            'market_data/options_chain',
            'market_data/fundamentals',
            'trading_logs/quantitative',
            'trading_logs/ai_agents',
            'trading_logs/broker_specific/ibkr',
            'trading_logs/broker_specific/alpaca',
            'trading_logs/broker_specific/legacy',
            'trading_logs/error_logs',
            'strategy_states/macd',
            'strategy_states/moving_average',
            'strategy_states/rsi',
            'strategy_states/bollinger_bands',
            'strategy_states/options',
            'ai_reports/daily_analysis',
            'ai_reports/strategy_recommendations',
            'ai_reports/risk_assessments',
            'ai_reports/market_sentiment',
            'system_logs',
            'backtest_results/by_strategy',
            'backtest_results/by_symbol',
            'backtest_results/by_timeframe',
            'performance_metrics/daily',
            'performance_metrics/weekly',
            'performance_metrics/monthly',
            'performance_metrics/yearly',
            'real_time_feeds'
        ]
        
        for dir_path in required_dirs:
            full_path = self.data_root / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            
            # Create .gitkeep if directory is empty
            gitkeep_path = full_path / '.gitkeep'
            if not any(full_path.iterdir()) and not gitkeep_path.exists():
                gitkeep_path.touch()
    
    def cleanup_old_files(self, days_to_keep: Dict[str, int] = None):
        """Clean up old files based on retention policies.
        
        Args:
            days_to_keep: Dictionary mapping directory types to retention days
        """
        if days_to_keep is None:
            days_to_keep = {
                'trading_logs': 180,  # 6 months
                'real_time_feeds': 7,  # 1 week
                'system_logs': 180,   # 6 months
                'market_data/real_time': 30,  # 1 month
            }
        
        for dir_type, days in days_to_keep.items():
            cleanup_dir = self.data_root / dir_type
            if not cleanup_dir.exists():
                continue
                
            cutoff_date = datetime.now() - timedelta(days=days)
            logger.info(f"Cleaning up {dir_type} files older than {days} days")
            
            for file_path in cleanup_dir.rglob('*'):
                if file_path.is_file() and file_path.name != '.gitkeep':
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        logger.info(f"Removing old file: {file_path}")
                        file_path.unlink()
    
    def compress_logs(self, days_to_compress: int = 30):
        """Compress log files older than specified days.
        
        Args:
            days_to_compress: Compress files older than this many days
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_compress)
        
        log_dirs = [
            self.data_root / 'trading_logs',
            self.data_root / 'system_logs'
        ]
        
        for log_dir in log_dirs:
            if not log_dir.exists():
                continue
                
            for log_file in log_dir.rglob('*.log'):
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time < cutoff_date and not str(log_file).endswith('.gz'):
                    logger.info(f"Compressing log file: {log_file}")
                    
                    # Compress the file
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(f"{log_file}.gz", 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    # Remove original file
                    log_file.unlink()
    
    def get_storage_stats(self) -> Dict[str, Dict[str, any]]:
        """Get storage statistics for each data directory.
        
        Returns:
            Dictionary with storage stats for each directory
        """
        stats = {}
        
        for subdir in self.data_root.iterdir():
            if subdir.is_dir() and subdir.name != '__pycache__':
                dir_stats = self._get_dir_stats(subdir)
                stats[subdir.name] = dir_stats
        
        return stats
    
    def _get_dir_stats(self, directory: Path) -> Dict[str, any]:
        """Get statistics for a specific directory.
        
        Args:
            directory: Directory to analyze
            
        Returns:
            Dictionary with file count, total size, etc.
        """
        total_size = 0
        file_count = 0
        latest_file = None
        latest_time = None
        
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.name != '.gitkeep':
                file_count += 1
                total_size += file_path.stat().st_size
                
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if latest_time is None or file_time > latest_time:
                    latest_time = file_time
                    latest_file = file_path.name
        
        return {
            'file_count': file_count,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'latest_file': latest_file,
            'latest_update': latest_time.isoformat() if latest_time else None
        }
    
    def organize_by_date(self, source_dir: str, target_dir: str = None):
        """Organize files by date into YYYY/MM/DD structure.
        
        Args:
            source_dir: Source directory to organize
            target_dir: Target directory (defaults to source_dir/organized)
        """
        source_path = self.data_root / source_dir
        if target_dir is None:
            target_path = source_path / 'organized'
        else:
            target_path = self.data_root / target_dir
        
        target_path.mkdir(parents=True, exist_ok=True)
        
        for file_path in source_path.glob('*'):
            if file_path.is_file() and file_path.name != '.gitkeep':
                # Extract date from filename or modification time
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                # Create year/month/day structure
                date_dir = target_path / f"{file_time.year:04d}" / f"{file_time.month:02d}" / f"{file_time.day:02d}"
                date_dir.mkdir(parents=True, exist_ok=True)
                
                # Move file
                new_path = date_dir / file_path.name
                logger.info(f"Moving {file_path} to {new_path}")
                shutil.move(str(file_path), str(new_path))
    
    def backup_critical_data(self, backup_dir: str):
        """Backup critical trading data.
        
        Args:
            backup_dir: Directory to store backups
        """
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Critical directories to backup
        critical_dirs = [
            'strategy_states',
            'performance_metrics',
            'ai_reports'
        ]
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for dir_name in critical_dirs:
            source_dir = self.data_root / dir_name
            if source_dir.exists():
                backup_name = f"{dir_name}_{timestamp}"
                target_dir = backup_path / backup_name
                
                logger.info(f"Backing up {source_dir} to {target_dir}")
                shutil.copytree(source_dir, target_dir)
    
    def generate_data_report(self) -> str:
        """Generate a comprehensive data storage report.
        
        Returns:
            Formatted report string
        """
        stats = self.get_storage_stats()
        
        report = []
        report.append("# AItrade Data Storage Report")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Data Root: {self.data_root}")
        report.append("")
        
        total_size = 0
        total_files = 0
        
        for dir_name, dir_stats in stats.items():
            report.append(f"## {dir_name}")
            report.append(f"- Files: {dir_stats['file_count']}")
            report.append(f"- Size: {dir_stats['total_size_mb']} MB")
            report.append(f"- Latest: {dir_stats['latest_file'] or 'None'}")
            report.append(f"- Updated: {dir_stats['latest_update'] or 'Never'}")
            report.append("")
            
            total_size += dir_stats['total_size_mb']
            total_files += dir_stats['file_count']
        
        report.append("## Summary")
        report.append(f"- Total Files: {total_files}")
        report.append(f"- Total Size: {total_size:.2f} MB")
        report.append("")
        
        return "\n".join(report)


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='AItrade Data Management Utility')
    parser.add_argument('--cleanup', action='store_true', help='Clean up old files')
    parser.add_argument('--compress', action='store_true', help='Compress old log files')
    parser.add_argument('--stats', action='store_true', help='Show storage statistics')
    parser.add_argument('--backup', type=str, help='Backup critical data to specified directory')
    parser.add_argument('--organize', type=str, help='Organize files by date in specified directory')
    
    args = parser.parse_args()
    
    manager = DataManager()
    
    if args.cleanup:
        logger.info("Starting cleanup of old files...")
        manager.cleanup_old_files()
    
    if args.compress:
        logger.info("Starting compression of old log files...")
        manager.compress_logs()
    
    if args.stats:
        print(manager.generate_data_report())
    
    if args.backup:
        logger.info(f"Starting backup to {args.backup}...")
        manager.backup_critical_data(args.backup)
    
    if args.organize:
        logger.info(f"Organizing files in {args.organize}...")
        manager.organize_by_date(args.organize)


if __name__ == '__main__':
    main()