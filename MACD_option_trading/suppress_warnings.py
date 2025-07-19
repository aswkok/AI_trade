#!/usr/bin/env python3
"""
Helper module to suppress specific numpy warnings that occur during options calculations.
This helps keep the terminal display clean.
"""

import warnings
import numpy as np

def suppress_options_calculation_warnings():
    """
    Suppress specific RuntimeWarnings related to division by zero and invalid values
    that occur during options calculations.
    """
    # Suppress divide by zero warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning, message="divide by zero encountered")
    
    # Suppress invalid value warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered")
    
    # Log that warnings are being suppressed
    print("Options calculation warnings suppressed for cleaner display")
