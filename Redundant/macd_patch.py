#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This script patches the main.py file to add MACD position logging.
"""

import re

# Read the main.py file
with open('main.py', 'r') as f:
    content = f.read()

# Replace the execute_signals method to include MACD position logging
pattern = r'(\s+# Extract signal information\n\s+curr_signal = latest_signal\[\'signal\'\]\n\s+position_change = latest_signal\[\'position\'\]\n\s+position_type = latest_signal\[\'position_type\'\]\n\s+shares = latest_signal\[\'shares\'\]\n\s+action = latest_signal\[\'action\'\]\n\s+\n\s+# Log the current signal\n\s+logger\.info\(f"{symbol} - Signal: {curr_signal}, Position: {position_change}, Action: {action}, Shares: {shares}"\))'

replacement = r'''        # Extract signal information
        curr_signal = latest_signal['signal']
        position_change = latest_signal['position']
        position_type = latest_signal['position_type']
        shares = latest_signal['shares']
        action = latest_signal['action']
        macd_position = latest_signal['macd_position'] if 'macd_position' in latest_signal else 'UNKNOWN'
        
        # Log the current signal with MACD position
        logger.info(f"{symbol} - Signal: {curr_signal}, Position: {position_change}, MACD Position: {macd_position}, Action: {action}, Shares: {shares}")'''

# Apply the replacement
updated_content = re.sub(pattern, replacement, content)

# Write the updated content back to main.py
with open('main.py', 'w') as f:
    f.write(updated_content)

print("Successfully updated main.py to include MACD position logging.")
