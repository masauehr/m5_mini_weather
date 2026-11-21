"""ダミーCSV生成（実機が無くても解析を作れるようにする合成データ）。

実測ではなく乱数で作った値。意図的に欠測・欠損値・外れ値・気圧の急降下を混ぜる。
出力: data/dummy/YYYYMMDD.csv（data/ はgit除外）

使い方: python analysis/make_dummy.py [日数(既定7)] [出力先(既定 data/dummy)] [開始日 YYYY-MM-DD(既定 2026-11-01)]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "data" / "dummy"
    out.mkdir(parents=True, exist_ok=True)
    start = sys.argv[3] if len(sys.argv) > 3 else "2026-11-01"
    rng = np.random.default_rng(42)

    idx = pd.date_range(start, periods=days * 1440, freq="1min", tz="Asia/Tokyo")
    hour = np.asarray(idx.hour + idx.minute / 60, dtype=float)
    n = len(idx)

    # 気温: 日変化（14時最高）＋緩やかな変動＋ノイズ
    temp = 22 + 4 * np.sin((hour - 8) / 24 * 2 * np.pi) + np.cumsum(rng.normal(0, 0.01, n)) + rng.normal(0, 0.05, n)
    # 湿度: 気温と逆相関
    hum = np.clip(65 - 2.5 * (temp - 22) + rng.normal(0, 0.5, n), 20, 100)
    # 気圧: 半日周期の潮汐＋ゆっくりした変動＋3日目に約8hPaの急降下
    pres = 1013 + 0.6 * np.sin(hour / 12 * 2 * np.pi) + np.cumsum(rng.normal(0, 0.003, n)) + rng.normal(0, 0.03, n)
    drop_start = 2 * 1440 + 12 * 60
    pres[drop_start:drop_start + 360] -= np.linspace(0, 8, 360)
    pres[drop_start + 360:] -= 8
    bat = np.clip(100 - np.arange(n) / 1440 * 12, 5, 100).astype(int)

    df = pd.DataFrame({"timestamp": idx, "temp_c": temp.round(2), "humidity_pct": hum.round(1),
                       "pressure_hpa": pres.round(2), "battery_pct": bat})

    # 意図的な不具合: 読み取り失敗（値が空欄の行）、行ごとの欠測、外れ値（スパイク）
    fail = rng.choice(n, size=max(3, n // 2000), replace=False)
    df.loc[fail, ["temp_c", "humidity_pct", "pressure_hpa"]] = np.nan
    df = df.drop(index=range(1440 + 300, 1440 + 360))  # 1日目に1時間の欠測（電池切れ想定）
    spike = rng.choice(df.index, size=2, replace=False)
    df.loc[spike, "temp_c"] = 85.0

    df["date"] = df["timestamp"].dt.strftime("%Y%m%d")
    for date, g in df.groupby("date"):
        g = g.drop(columns="date").copy()
        g["timestamp"] = g["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S+09:00")
        g.to_csv(out / f"{date}.csv", index=False)
    print(f"{days}日分を {out} に出力しました")


if __name__ == "__main__":
    main()
