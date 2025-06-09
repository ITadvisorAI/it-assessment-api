import os
import sys
import pandas as pd

sys.path.insert(0, os.getcwd())

from market_lookup import suggest_hw_replacements, suggest_sw_replacements


def test_suggest_hw_replacements():
    df = pd.DataFrame({'Device Name': ['Server1', 'Server2']})
    result = suggest_hw_replacements(df)
    assert 'Recommended Model' in result.columns
    assert len(result['Recommended Model'].dropna()) == len(df)


def test_suggest_sw_replacements():
    df = pd.DataFrame({'Software Name': ['App1', 'App2']})
    result = suggest_sw_replacements(df)
    assert 'Recommended Model' in result.columns
    assert len(result['Recommended Model'].dropna()) == len(df)
