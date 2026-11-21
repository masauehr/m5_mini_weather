"""品質チェック: 欠測・読み取り失敗・範囲外・急変（スパイク）・重複を検出して表示する。

使い方: python analysis/quality.py <CSVのあるディレクトリ> [記録周期(秒・既定60)]
"""
import sys

import pandas as pd

from loader import load_dir

# 妥当な範囲（屋外・屋内の一般的な値。超えたら外れ値候補）
LIMITS = {"temp_c": (-20, 50), "humidity_pct": (0, 100), "pressure_hpa": (900, 1100)}
# 1周期あたりの変化がこれを超えたらスパイク候補
SPIKE = {"temp_c": 3.0, "humidity_pct": 15.0, "pressure_hpa": 2.0}


def check(df, interval=60):
    """interval は interval_s 列が無い旧形式CSV用の既定の記録間隔[秒]。"""
    res = {}
    res["行数"] = len(df)
    res["期間"] = f"{df.index.min():%Y-%m-%d %H:%M} 〜 {df.index.max():%Y-%m-%d %H:%M}"

    # 重複
    dup = df.index.duplicated().sum()
    res["重複行"] = int(dup)
    df = df[~df.index.duplicated()]

    # 欠測: 直前の行の記録間隔（interval_s 列）の1.5倍を超える間隔を欠測区間とみなす。
    # interval_s 列が無い旧形式のCSVでは、引数の interval を全行に使う。
    iv = df["interval_s"].fillna(interval) if "interval_s" in df.columns else pd.Series(float(interval), index=df.index)
    prev_iv = iv.shift(1)
    gaps = df.index.to_series().diff()
    big = gaps[gaps > pd.to_timedelta(prev_iv * 1.5, unit="s")]
    missing = int(sum(round(g.total_seconds() / prev_iv.loc[t]) - 1 for t, g in big.items()))
    res["欠測区間"] = [(str((t - g).strftime("%m-%d %H:%M:%S")), str(t.strftime("%m-%d %H:%M:%S"))) for t, g in big.items()]
    res["欠測行数(推定)"] = missing
    res["取得率"] = f"{(len(df) / (len(df) + missing) * 100):.1f}%"
    if "interval_s" in df.columns:
        res["記録間隔(秒)の内訳"] = {int(k): int(v) for k, v in df["interval_s"].value_counts().items()}

    # 読み取り失敗（値が空欄）
    res["読み取り失敗行"] = int(df[list(LIMITS)].isna().all(axis=1).sum())

    # 範囲外・スパイク
    out = {}
    for c, (lo, hi) in LIMITS.items():
        bad = df[(df[c] < lo) | (df[c] > hi)]
        out[c] = [(t.strftime("%m-%d %H:%M"), v) for t, v in bad[c].items()]
    res["範囲外"] = out
    spk = {}
    for c, th in SPIKE.items():
        d = df[c].diff().abs()
        spk[c] = [(t.strftime("%m-%d %H:%M"), round(float(v), 2)) for t, v in d[d > th].items()]
    res["急変(スパイク候補)"] = spk
    return res


def clean(df):
    """範囲外の値を欠損（NaN）にした複製を返す。以降の解析で使う。"""
    df = df[~df.index.duplicated()].copy()
    for c, (lo, hi) in LIMITS.items():
        df.loc[(df[c] < lo) | (df[c] > hi), c] = float("nan")
    return df


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    res = check(load_dir(sys.argv[1]), interval)
    for k, v in res.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
