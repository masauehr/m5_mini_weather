"""気象庁AMeDASとの比較: 自分の観測値を最寄りのAMeDAS地点の10分値と突き合わせる。

使い方（リポジトリ直下から）:
  python analysis/compare_jma.py --find 地点名                      # 地点IDを検索
  python analysis/compare_jma.py <CSVディレクトリ> --station <地点ID> [--altitude 設置標高m] [--out 出力先]

- 地点ID・設置標高は引数で渡す（設置場所が推定できる情報をリポジトリに書かないため）。
- 取得したAMeDAS JSONは data/jma_cache/ にキャッシュ（git除外）。気象庁のサーバーへの負荷を減らす。
- 気圧: 自分の値は観測地点の気圧（海面更正なし）。--altitude を与えると海面気圧に換算して
  AMeDASの海面気圧(normalPressure)と比べる。与えない場合は水平方向の差（バイアス）を除いた比較が主になる。
- 出典: 気象庁ホームページ（アメダス）。利用規約を遵守すること。
"""
import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

from loader import load_dir
from quality import clean

BASE = "https://www.jma.go.jp/bosai/amedas/"
ROOT = Path(__file__).resolve().parent.parent
JST = "Asia/Tokyo"

_avail = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in ["Hiragino Sans", "Noto Sans CJK JP", "IPAexGothic"] if f in _avail] or ["sans-serif"]


def http_json(url):
    """JSONを取得する。404は None を返す。礼儀として間隔を空ける。"""
    req = urllib.request.Request(url, headers={"User-Agent": "m5_mini_weather-research"})
    time.sleep(0.3)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def find_stations(word):
    table = http_json(BASE + "const/amedastable.json")
    for sid, v in table.items():
        if word in v.get("kjName", "") or word in v.get("knName", "") or word.lower() in v.get("enName", "").lower():
            print(f"{sid}\t{v['kjName']}\t標高{v.get('alt')}m\t観測項目:{v.get('elems')}")


def fetch_point(stn, start, end, cache_dir):
    """start〜end（JST）を覆う3時間ブロックを取得し、10分値のDataFrameにして返す。"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows = {}
    now = datetime.now()
    day = start.normalize().to_pydatetime().replace(tzinfo=None)
    last = end.to_pydatetime().replace(tzinfo=None)
    while day <= last:
        for h in range(0, 24, 3):
            b0 = day + timedelta(hours=h)
            b1 = b0 + timedelta(hours=3)
            if b1 < start.to_pydatetime().replace(tzinfo=None) or b0 > last or b0 > now:
                continue
            name = f"{b0:%Y%m%d}_{h:02d}.json"
            path = cache_dir / name
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                data = http_json(f"{BASE}data/point/{stn}/{name}")
                # 進行中のブロックは未完成なのでキャッシュしない
                if data is not None and b1 < now - timedelta(hours=2):
                    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            if not data:
                continue
            for ts, v in data.items():
                rows[ts] = v
        day += timedelta(days=1)
    if not rows:
        raise SystemExit("AMeDASデータを取得できませんでした（地点ID・期間を確認してください。過去データの保持期間は限られます）")

    def val(v, k):
        x = v.get(k)
        return x[0] if x and x[1] == 0 else np.nan  # 品質フラグ0のみ採用

    df = pd.DataFrame(
        {ts: {"temp": val(v, "temp"), "humidity": val(v, "humidity"),
              "pressure": val(v, "pressure"), "normalPressure": val(v, "normalPressure")} for ts, v in rows.items()}
    ).T
    df.index = pd.to_datetime(df.index, format="%Y%m%d%H%M%S").tz_localize(JST)
    return df.sort_index().astype(float)


def to_sea_level(p, t, alt):
    """観測地点の気圧(hPa)を海面気圧へ換算（気象庁の海面更正と同じ型の標準式）。"""
    return p * (1 - 0.0065 * alt / (t + 0.0065 * alt + 273.15)) ** -5.257


def metrics(a, b):
    """a=自分, b=気象庁。バイアス(a-bの平均)・差の標準偏差・相関・件数。"""
    d = (a - b).dropna()
    both = pd.concat([a, b], axis=1, join="inner", sort=True).dropna()
    corr = both.corr().iloc[0, 1] if len(both) > 2 else np.nan
    return {"件数": len(d), "バイアス(自分-気象庁)": round(d.mean(), 3), "差の標準偏差": round(d.std(), 3),
            "RMSE": round(float(np.sqrt((d ** 2).mean())), 3), "相関": round(corr, 4)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv_dir", nargs="?")
    ap.add_argument("--station", help="AMeDAS地点ID（例: 44132）")
    ap.add_argument("--altitude", type=float, help="設置標高[m]（海面気圧への換算用）")
    ap.add_argument("--find", help="地点名で検索して終了")
    ap.add_argument("--out", default=str(ROOT / "data" / "compare"))
    a = ap.parse_args()

    if a.find:
        find_stations(a.find)
        return
    if not a.csv_dir or not a.station:
        ap.error("CSVディレクトリと --station が必要です")

    mine = clean(load_dir(a.csv_dir))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    jma = fetch_point(a.station, mine.index.min(), mine.index.max(), ROOT / "data" / "jma_cache" / a.station)

    # 自分の値を10分値へ（区間 (T-10分, T] の平均を T に付ける。AMeDASの10分値の時刻に揃える）
    m10 = mine[["temp_c", "humidity_pct", "pressure_hpa"]].resample("10min", closed="right", label="right").mean()
    pres = m10["pressure_hpa"]
    jma_p = jma["normalPressure"]
    p_label = "気圧（海面換算）" if a.altitude is not None else "気圧（観測値・水平比較）"
    if a.altitude is not None:
        pres = to_sea_level(pres, m10["temp_c"], a.altitude)
    else:
        jma_p = jma["pressure"] if jma["pressure"].notna().any() else jma["normalPressure"]

    pairs = {"気温[℃]": (m10["temp_c"], jma["temp"]), "湿度[%]": (m10["humidity_pct"], jma["humidity"]),
             p_label + "[hPa]": (pres, jma_p)}
    summary = {k: metrics(*v) for k, v in pairs.items()}
    res = pd.DataFrame(summary).T
    print(res.to_string())
    res.to_csv(out / "compare_summary.csv")

    # 気圧は設置標高の違いでバイアスが大きいので、バイアスを除いた比較も出す
    pm, pj = pairs[p_label + "[hPa]"]
    both = pd.concat([pm, pj], axis=1, join="inner", sort=True).dropna()  # 共通の時刻に揃えてから平均を引く
    if len(both) > 3:
        x, y = both.iloc[:, 0] - both.iloc[:, 0].mean(), both.iloc[:, 1] - both.iloc[:, 1].mean()
        rmse = float(np.sqrt(((x - y) ** 2).mean()))
        print(f"\n気圧（平均を除いた変動どうし）: RMSE {rmse:.3f} hPa / 相関 {x.corr(y):.4f}")

    # グラフ
    fig, ax = plt.subplots(4, 1, figsize=(11, 11))
    for i, (k, (x, y)) in enumerate(pairs.items()):
        ax[i].plot(x.index, x, lw=0.8, label="自分")
        ax[i].plot(y.index, y, lw=0.8, label="気象庁AMeDAS")
        ax[i].set_ylabel(k); ax[i].legend(loc="upper right"); ax[i].grid(alpha=0.3)
    d = (m10["temp_c"] - jma["temp"]).dropna()
    h = d.groupby(d.index.hour)
    ax[3].plot(h.mean().index, h.mean(), marker="o", ms=3)
    ax[3].fill_between(h.mean().index, h.mean() - h.std(), h.mean() + h.std(), alpha=0.2)
    ax[3].axhline(0, color="gray", lw=0.8)
    ax[3].set_xlabel("時"); ax[3].set_ylabel("気温差 自分-気象庁 [℃]"); ax[3].grid(alpha=0.3)
    ax[3].set_title("時刻別の気温差（日中に正なら日射・自己加熱の疑い）", fontsize=10)
    fig.suptitle("出典: 気象庁ホームページ（アメダス）を加工して作成", fontsize=9, y=0.995)
    fig.tight_layout()
    fig.savefig(out / "compare.png", dpi=120)
    print(f"\n出力: {out}")


if __name__ == "__main__":
    main()
