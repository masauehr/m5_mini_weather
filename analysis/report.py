"""解析レポート: 日別統計・日変化・気圧の3時間変化量を計算し、グラフ(PNG)を出力する。

使い方: python analysis/report.py <CSVのあるディレクトリ> [出力先(既定 data/report)]

気圧の3時間変化量が -3hPa 以下を「急降下」として表示する。この閾値は暫定値で、
医療・防災の判断には使わない（README の方針）。
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from loader import load_dir
from quality import clean

# 日本語フォントは入っているものだけを使う（無いと警告が大量に出るため）
_avail = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in ["Hiragino Sans", "Noto Sans CJK JP", "IPAexGothic"] if f in _avail] or ["sans-serif"]
DROP_THRESHOLD = -3.0  # hPa / 3時間（暫定）


def pressure_change_3h(df):
    """10分平均に直し、3時間前との差（hPa）を返す。欠測を跨ぐ差は NaN。"""
    p = df["pressure_hpa"].resample("10min").mean()
    return p - p.shift(18)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "data" / "report"
    out.mkdir(parents=True, exist_ok=True)
    df = clean(load_dir(src))

    # 日別統計
    daily = df.groupby(df.index.date).agg(
        温度_平均=("temp_c", "mean"), 温度_最高=("temp_c", "max"), 温度_最低=("temp_c", "min"),
        湿度_平均=("humidity_pct", "mean"), 気圧_平均=("pressure_hpa", "mean"),
        気圧_最高=("pressure_hpa", "max"), 気圧_最低=("pressure_hpa", "min"),
    ).round(2)
    daily.to_csv(out / "daily_summary.csv")
    print(daily.to_string())

    # 気圧の3時間変化量と急降下
    dp = pressure_change_3h(df)
    drops = dp[dp <= DROP_THRESHOLD]
    print(f"\n気圧3時間変化 最小: {dp.min():.2f} hPa（{dp.idxmin():%m-%d %H:%M}）")
    if len(drops):
        print(f"急降下(<= {DROP_THRESHOLD} hPa/3h)の開始〜終了: {drops.index.min():%m-%d %H:%M} 〜 {drops.index.max():%m-%d %H:%M}")
    else:
        print("急降下なし")

    # 時系列グラフ
    fig, ax = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
    ax[0].plot(df.index, df["temp_c"], lw=0.6); ax[0].set_ylabel("気温 [℃]")
    ax[1].plot(df.index, df["humidity_pct"], lw=0.6, color="tab:green"); ax[1].set_ylabel("湿度 [%]")
    ax[2].plot(df.index, df["pressure_hpa"], lw=0.6, color="tab:red"); ax[2].set_ylabel("気圧 [hPa]")
    ax[3].plot(dp.index, dp, lw=0.8, color="tab:purple")
    ax[3].axhline(DROP_THRESHOLD, color="gray", ls="--", lw=0.8)
    ax[3].set_ylabel("気圧3時間変化 [hPa]")
    for a in ax:
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "timeseries.png", dpi=120)
    plt.close(fig)

    # 日変化（時刻別の平均と標準偏差）
    h = df.groupby(df.index.hour)
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.5))
    for a, (c, lab) in zip(ax, [("temp_c", "気温 [℃]"), ("humidity_pct", "湿度 [%]"), ("pressure_hpa", "気圧 [hPa]")]):
        m, s = h[c].mean(), h[c].std()
        a.plot(m.index, m, marker="o", ms=3)
        a.fill_between(m.index, m - s, m + s, alpha=0.2)
        a.set_xlabel("時"); a.set_ylabel(lab); a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "diurnal.png", dpi=120)
    plt.close(fig)
    print(f"\n出力: {out}")


if __name__ == "__main__":
    main()
