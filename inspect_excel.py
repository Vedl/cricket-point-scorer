import pandas as pd

try:
    df = pd.read_excel('Sim(AutoRecovered)(AutoRecovered) copy.xlsx', header=None)
    print("\nRows 0-20:")
    print(df.iloc[0:20])
except Exception as e:
    print(f"Error reading excel: {e}")
