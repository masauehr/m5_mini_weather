"""マークごとの区間集計: 「ここから測る」の印（mark列）で記録を区間に分け、区間ごとの統計と図を出す。

使い方: python analysis/segments.py <CSVのあるディレクトリ> [出力先(既定 data/segments)]

- mark列に値がある行を区間の開始とする。マーク番号は電源投入後の連番で、再起動すると1に戻るため、
  区間は番号ではなく**時刻順**に数える（区間1, 区間2, ...）。最初のマークより前は「マーク前」。
- 移動式では、場所ごとにマークを付けて測り、区間ごとの気温・湿度・気圧を比べる使い方を想定する。
- 位置はCSVに含まれない。場所との対応は、マークの時刻とスマホの位置ログ等で後から結びつける（docs/portable.md）。
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager

from loader import load_dir
from quality import clean

_avail = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in ["Hiragino Sans", "Noto Sans CJK JP", "IPAexGothic"] if f in _avail] or ["sans-serif"]


def add_segments(df):
    """各行に区間番号（segment）を付ける。0=最初のマークより前、1以降=マークごと。"""
    df = df.copy()
    if "mark" not in df.columns:
        df["mark"] = float("nan")
    df["segment"] = df["mark"].notna().cumsum()
    return df


def summarize(df):
    """区間ごとの開始・終了・長さ・行数と、気温・湿度・気圧の平均/最小/最大を表にする。"""
    rows = []
    for seg, g in df.groupby("segment"):
        label = "マーク前" if seg == 0 else f"区間{seg}(M{int(g['mark'].iloc[0])})"
        t = g["temp_c"]
        rows.append({
            "区間": label,
            "開始": f"{g.index.min():%m-%d %H:%M:%S}",
            "終了": f"{g.index.max():%m-%d %H:%M:%S}",
            "分": round((g.index.max() - g.index.min()).total_seconds() / 60, 1),
            "行数": len(g),
            "気温平均": round(t.mean(), 2), "気温最小": round(t.min(), 2), "気温最大": round(t.max(), 2),
            "湿度平均": round(g["humidity_pct"].mean(), 1),
            "気圧平均": round(g["pressure_hpa"].mean(), 2),
        })
    return pd.DataFrame(rows)


def plot(df, out_png):
    fig, ax = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    marks = df[df["mark"].notna()]
    for a, (c, lab, color) in zip(ax, [("temp_c", "気温 [℃]", "tab:blue"), ("humidity_pct", "湿度 [%]", "tab:green"),
                                       ("pressure_hpa", "気圧 [hPa]", "tab:red")]):
        a.plot(df.index, df[c], lw=0.7, color=color)
        for t in marks.index:
            a.axvline(t, color="gray", ls="--", lw=0.8)
        a.set_ylabel(lab)
        a.grid(alpha=0.3)
    for t, m in marks["mark"].items():
        ax[0].annotate(f"M{int(m)}", (t, ax[0].get_ylim()[1]), xytext=(2, -12), textcoords="offset points", fontsize=8)
    fig.suptitle("マークで区切った記録（点線=マーク）", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "data" / "segments"
    out.mkdir(parents=True, exist_ok=True)
    df = add_segments(clean(load_dir(sys.argv[1])))
    if df["mark"].notna().sum() == 0:
        print("mark列に印がありません（全体を1区間として集計します）")
    table = summarize(df)
    print(table.to_string(index=False))
    table.to_csv(out / "segments_summary.csv", index=False)
    plot(df, out / "segments.png")
    print(f"\n出力: {out}")


if __name__ == "__main__":
    main()
