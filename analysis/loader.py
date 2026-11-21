"""CSV読み込みの共通処理（ファームウェアが出力する YYYYMMDD.csv を結合）。"""
from pathlib import Path

import pandas as pd

COLUMNS = ["temp_c", "humidity_pct", "pressure_hpa", "battery_pct"]


def load_dir(path):
    """ディレクトリ内の YYYYMMDD.csv を時刻順に結合して返す（索引は日本時間の時刻）。"""
    files = sorted(Path(path).glob("[0-9]" * 8 + ".csv"))
    if not files:
        raise SystemExit(f"CSVが見つかりません: {path}")
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("Asia/Tokyo")
    df = df.sort_values("timestamp").set_index("timestamp")
    for c in COLUMNS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
