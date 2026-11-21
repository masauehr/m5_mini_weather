# analysis

取得したCSV（[データ仕様](../docs/data_format.md)）の解析スクリプト。実機が無くてもダミーデータで試せる。

> 状態: ダミーデータでの動作確認のみ。**実測データでは未検証**。

## 準備

```bash
python3 -m venv ../.venv && ../.venv/bin/pip install -r requirements.txt
```

## 使い方（リポジトリ直下から）

```bash
.venv/bin/python analysis/make_dummy.py              # ダミー7日分 → data/dummy/（git除外）
.venv/bin/python analysis/quality.py data/dummy      # 品質チェック
.venv/bin/python analysis/report.py data/dummy       # 日別統計・グラフ → data/report/

# 気象庁AMeDASとの比較
.venv/bin/python analysis/compare_jma.py --find 地点名                      # 地点IDを検索
.venv/bin/python analysis/compare_jma.py data/実測 --station 地点ID --altitude 設置標高m   # 比較 → data/compare/
```

実測CSV（スマホ/SDから取得した `YYYYMMDD.csv`）は `data/` 以下に置き、同じコマンドで指定する。

| スクリプト | 内容 |
|---|---|
| `make_dummy.py` | 合成データ生成。欠測・読み取り失敗・外れ値・気圧の急降下を意図的に混ぜる（乱数・実測ではない） |
| `loader.py` | CSV結合の共通処理 |
| `quality.py` | 欠測区間・取得率・読み取り失敗・範囲外・スパイク候補・重複の検出 |
| `compare_jma.py` | 最寄りのAMeDAS（10分値）と突き合わせる。気温・湿度・気圧のバイアス/差の標準偏差/RMSE/相関と、時刻別の気温差（日射・自己加熱の確認）をグラフ化 |
| `report.py` | 日別統計（CSV）、時系列・日変化グラフ、気圧3時間変化と急降下の検出 |

## 注意

- 範囲外の値は解析前に欠損扱いにする（`quality.clean`）。
- 気圧の急降下の閾値（3時間で -3hPa）は暫定値。**医療・防災の判断には使わない**。
- 出力は `data/` 以下でgit除外（実測データを公開しない方針）。

## 気象庁との比較の注意

- **AMeDASの過去データは約1週間強しか取れません**（2026-11-21時点で11/15は取得可・11/10は不可）。実測を比較するなら、**期間内に `compare_jma.py` を実行**して `data/jma_cache/` に保存しておく（以後はキャッシュを使う）。
- 地点ID・設置標高は**引数で渡し、リポジトリに書かない**（設置場所が推定できるため）。
- 気圧は観測地点の値で、標高差の影響が大きい。`--altitude` で海面気圧に換算して比較する。標高が不明なら、平均を除いた変動どうしの比較（出力の最終行）を見る。
- 品質フラグが正常（0）の値だけを使う。10分値の時刻に合わせ、自分の値は直前10分の平均にしている。
- 検証: AMeDAS自身から作ったCSVを比較させ、バイアス0・相関1になることを確認済み（時刻合わせ・結合の確認）。ダミーデータとの比較は処理確認のみで意味のある数値ではない。
- 出典: 気象庁ホームページ（アメダス）。グラフに出典を表示している。

## 今後（実測データが取れてから）

- 比較結果に基づく補正（バイアス・日射の影響）
- 自己加熱の評価（本体を離したときとの温度差）
