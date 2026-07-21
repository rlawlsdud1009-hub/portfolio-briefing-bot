"""
Portfolio Briefing Bot — Stage 1 (자동 실행용)
매주 실행되어 보유 종목의 가격·비중·드리프트·반도체 집중도를
마크다운 리포트로 생성해 reports/ 폴더에 저장한다.
"""
import os
import yaml
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime, timezone, timedelta

# 한국 시간 기준 날짜
KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")


def load_config(path="portfolio.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_price(ticker, source):
    """source='yf' → yfinance, 'fdr' → FinanceDataReader. 실패 시 None."""
    try:
        if source == "yf":
            data = yf.Ticker(ticker).history(period="5d")
        else:
            data = fdr.DataReader(ticker)
        if data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except Exception as e:
        print(f"  [경고] {ticker} 가격 조회 실패: {e}")
        return None


def build_tracker(config):
    fx = config["meta"]["fx_usd_krw"]
    rows = []
    for h in config["holdings"]:
        live = get_price(h["ticker"], h["source"])
        ref = h["ref_price"]
        price = live if live is not None else ref
        value_krw = h["shares"] * price * (fx if h["currency"] == "USD" else 1)
        gap = ((live - ref) / ref * 100) if live is not None else None
        rows.append({
            "name": h["name"],
            "ticker": h["ticker"],
            "asset_class": h["asset_class"],
            "theme": h["theme"],
            "shares": h["shares"],
            "ref_price": ref,
            "live_price": round(live, 2) if live is not None else "조회실패",
            "gap_%": round(gap, 1) if gap is not None else None,
            "value_krw": round(value_krw),
        })
    df = pd.DataFrame(rows)
    total = df["value_krw"].sum()
    df["weight_%"] = (df["value_krw"] / total * 100).round(1)
    return df, total


def build_report(config, df, total):
    """마크다운 리포트 문자열 생성."""
    lines = []
    lines.append(f"# 포트폴리오 주간 브리핑 — {TODAY}")
    lines.append("")
    lines.append(f"- 총평가액: **{total:,.0f} KRW**  (환율 {config['meta']['fx_usd_krw']})")
    lines.append(f"- 생성 시각: {datetime.now(KST):%Y-%m-%d %H:%M} KST")
    lines.append("")

    # 보유 종목 표
    lines.append("## 보유 종목")
    lines.append("")
    lines.append("| 종목 | 티커 | 자산군 | 테마 | 현재가 | ref대비 | 평가액(KRW) | 비중 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for _, r in df.iterrows():
        gap = f"{r['gap_%']:+.1f}%" if r["gap_%"] is not None else "-"
        lines.append(
            f"| {r['name']} | {r['ticker']} | {r['asset_class']} | {r['theme']} "
            f"| {r['live_price']} | {gap} | {r['value_krw']:,} | {r['weight_%']}% |"
        )
    lines.append("")

    # 자산군 드리프트
    lines.append("## 자산군 드리프트")
    lines.append("")
    lines.append("| 자산군 | 현재 | 목표 | 드리프트 | 신호 |")
    lines.append("|---|---|---|---|---|")
    sig = config["rebalance"]["signals"]
    for ac, t in config["targets"].items():
        cur = df.loc[df["asset_class"] == ac, "value_krw"].sum() / total * 100
        d = cur - t["weight"]
        band = t["band"]
        s = sig["hold"]
        if abs(d) > band:
            s = sig["over"] if d > 0 else sig["under"]
        lines.append(f"| {ac} | {cur:.1f}% | {t['weight']}% | {d:+.1f}p | {s} |")
    lines.append("")

    # 반도체 집중도
    cc = config["concentration_check"]
    eq_classes = ("국내주식", "해외주식")
    eq = df.loc[df["asset_class"].isin(eq_classes), "value_krw"].sum()
    semi = df.loc[
        df["theme"].isin(cc["theme_tags"]) & df["asset_class"].isin(eq_classes),
        "value_krw"
    ].sum()
    ratio = semi / eq * 100
    status = "⚠ 초과" if ratio > cc["threshold"] else "정상"
    lines.append("## 반도체 집중도 (주식 기준)")
    lines.append("")
    lines.append(f"- 집중도: **{ratio:.1f}%**  (기준 {cc['threshold']}%)  → {status}")
    lines.append("")
    lines.append("---")
    lines.append("*이 리포트는 자동 생성되었습니다. 매매 결정은 직접 판단하세요.*")

    return "\n".join(lines)


def main():
    config = load_config()
    df, total = build_tracker(config)
    report = build_report(config, df, total)

    os.makedirs("reports", exist_ok=True)
    out_path = f"reports/{TODAY}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"리포트 생성 완료: {out_path}")
    print(f"총평가액: {total:,.0f} KRW")


if __name__ == "__main__":
    main()
