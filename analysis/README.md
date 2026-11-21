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
```

実測CSV（スマホ/SDから取得した `YYYYMMDD.csv`）は `data/` 以下に置き、同じコマンドで指定する。

| スクリプト | 内容 |
|---|---|
| `make_dummy.py` | 合成データ生成。欠測・読み取り失敗・外れ値・気圧の急降下を意図的に混ぜる（乱数・実測ではない） |
| `loader.py` | CSV結合の共通処理 |
| `quality.py` | 欠測区間・取得率・読み取り失敗・範囲外・スパイク候補・重複の検出 |
| `report.py` | 日別統計（CSV）、時系列・日変化グラフ、気圧3時間変化と急降下の検出 |

## 注意

- 範囲外の値は解析前に欠損扱いにする（`quality.clean`）。
- 気圧の急降下の閾値（3時間で -3hPa）は暫定値。**医療・防災の判断には使わない**。
- 出力は `data/` 以下でgit除外（実測データを公開しない方針）。

## 今後（実測データが取れてから）

- 気象庁（最寄りのAMeDAS）との比較と補正
- 自己加熱の評価（本体を離したときとの温度差）
