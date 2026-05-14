#!/usr/bin/env python3
"""Investment indicators dashboard — Tailwind CSS v4."""

import argparse
import http.server
import json
import math
import os
import socket
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

KST = ZoneInfo("Asia/Seoul")
_KR_WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]

# yfinance 1.2.0은 동일 프로세스 내 download() 호출 간 ticker 컨텍스트를 공유해
# 병렬 호출 시 다른 ticker의 컬럼이 섞이는 race condition이 있다. 호출 직렬화로 회피.
_yf_lock = threading.Lock()

# ── Signal System ─────────────────────────────────────────────────────────────

SCORE_MAP = {"good": 1, "neutral": 0, "warn": -1, "bad": -2}
_KR = {"good": "매수 유리", "warn": "주의", "bad": "위험", "neutral": "중립"}
_CLS = {
    "good":    {"text": "text-good",   "bg": "bg-good/15",   "border": "border-good/30"},
    "warn":    {"text": "text-warn",   "bg": "bg-warn/15",   "border": "border-warn/30"},
    "bad":     {"text": "text-danger", "bg": "bg-danger/15", "border": "border-danger/30"},
    "neutral": {"text": "text-muted",  "bg": "bg-muted/10",  "border": "border-muted/20"},
}
_DOT = {"good": "#3fb950", "warn": "#d29922", "bad": "#f85149", "neutral": "#8b949e"}

# ── Indicator Metadata ────────────────────────────────────────────────────────
# 카드 클릭 시 모달에 표시되는 지표별 상세 정보.
# thresholds는 signal_color()의 if/elif 임계값과 일치해야 함 (별도 검증 필요).

INDICATOR_INFO = {
    "overall": {
        "title": "종합 투자 신호 (7개 컴포넌트)",
        "description": "이 대시보드의 종합 신호는 CNN Fear & Greed Index(7-component composite)와 Goldman Sachs Bull/Bear Indicator(6-component) 방법론을 참고해 7개 지표를 종합한 결과예요. 각 지표를 매수(+1)·중립(0)·주의(-1)·위험(-2) 4단계로 분류하고 합산해서 최종 점수(범위: -14 ~ +7)를 산출해요. 점수 구간에 따라 4가지 행동 권고를 보여줘요.",
        "thresholds": [
            ("≥ +4점",  "매수 유리 — 장기 투자 시작 좋은 환경", "good"),
            ("0 ~ +3점", "중립 — 관망 추천", "neutral"),
            ("-1 ~ -5점", "주의 — 신중하게 (분할 매수/관망)", "warn"),
            ("≤ -6점",  "위험 — 방어적으로 (현금 비중 ↑)", "bad"),
        ],
        "source_url": "https://github.com/gymcoding/stock-dashboard",
        "source_label": "방법론·코드 (GitHub)",
        "caveat": "이 신호는 학술적 백테스트가 아닌 휴리스틱(experience-based heuristic)이에요. 카드를 클릭해 각 컴포넌트의 현재값·임계값·검증 출처를 직접 확인하세요. 매매 결정은 본인 책임이며 다른 지표·뉴스와 함께 종합 판단해야 해요.",
    },
    "fear_greed": {
        "title": "CNN 공포 & 탐욕 지수",
        "description": "CNN이 매일 발표하는 미국 주식시장 투자자 심리 지표예요. S&P500 모멘텀, 주식 가격 강도, 풋콜 비율 등 7개 하위 지표를 0~100 점수로 종합해요. 0에 가까울수록 투자자가 겁먹어 매도세가 강하고, 100에 가까울수록 욕심을 부리며 매수세가 강한 상태예요.",
        "thresholds": [
            ("0~24",   "극도의 공포 (역사적 매수 기회)", "good"),
            ("25~44",  "공포 (매수 기회)", "good"),
            ("45~55",  "중립", "neutral"),
            ("56~74",  "탐욕 (주의)", "warn"),
            ("75~100", "극도의 탐욕 (고점 경고)", "bad"),
        ],
        "source_url": "https://edition.cnn.com/markets/fear-and-greed",
        "source_label": "CNN — Fear & Greed Index",
        "caveat": "단기 심리 지표라 추세 전환 시점을 정확히 짚지 못해요. 극단값(25 이하·75 이상)일수록 역사적 신뢰도가 높아요.",
    },
    "vix": {
        "title": "VIX 공포 지수",
        "description": "S&P500 옵션 가격으로 산출한 향후 30일 변동성 기대치예요. 시장이 평온하면 낮고, 불확실성·공포가 커지면 급등해요. '월스트리트의 공포 지표'라고도 불려요.",
        "thresholds": [
            ("< 15",   "지나치게 조용 (과신 주의)", "warn"),
            ("15~20",  "안정적인 시장", "neutral"),
            ("20~30",  "적당한 긴장 (기회 탐색)", "good"),
            ("30~40",  "공포 구간 (역발투자 기회)", "good"),
            ("> 40",   "극단적 공포 (단기 위험·장기 기회)", "warn"),
        ],
        "source_url": "https://finance.yahoo.com/quote/%5EVIX",
        "source_label": "Yahoo Finance — ^VIX",
        "caveat": "VIX 40 이상은 단기 추가 하락 위험과 장기 매수 기회가 동시에 존재하는 양면 구간이에요.",
    },
    "yield_spread": {
        "title": "10Y-3M 금리차 (장단기 금리차)",
        "description": "미국 10년물 국채 금리에서 3개월물 금리를 뺀 값이에요. 0% 아래로 역전되면 1~2년 안에 경기 침체 가능성이 높다고 봐요. 역사적으로 8번 역전 중 7번 경기침체가 뒤따랐어요.",
        "thresholds": [
            ("> 0.5%",   "정상 (경기 양호)", "neutral"),
            ("0~0.5%",   "금리차 축소 (주의)", "warn"),
            ("-0.5~0%",  "부분 역전 (침체 우려)", "warn"),
            ("< -0.5%",  "완전 역전 (침체 경고)", "bad"),
        ],
        "source_url": "https://fred.stlouisfed.org/series/T10Y3M",
        "source_label": "FRED — 10-Year minus 3-Month Treasury Spread",
        "caveat": "본 대시보드는 yfinance ^IRX(Bank Discount 방식)를 사용해요. FRED의 Constant Maturity 값과 약간 다를 수 있어요.",
    },
    "ma200": {
        "title": "S&P500 200일 이동평균 추세",
        "description": "SPY(S&P500 ETF) 현재가가 최근 200거래일 평균보다 위인지 아래인지로 큰 흐름을 판단해요. 위면 상승추세(강세장), 아래면 하락추세(약세장)로 봐요.",
        "thresholds": [
            ("MA200 위",   "상승추세 (강세장)", "good"),
            ("MA200 아래", "하락추세 (약세장)", "bad"),
        ],
        "source_url": "https://finance.yahoo.com/quote/SPY/chart",
        "source_label": "Yahoo Finance — SPY 차트",
        "caveat": "후행 지표라 추세 전환이 어느 정도 진행된 뒤에야 신호가 바뀌어요. 단독으로 매매하기보다 다른 지표와 함께 보세요.",
    },
    "cape": {
        "title": "CAPE (Shiller P/E)",
        "description": "노벨상 수상자 Robert Shiller가 만든 지표예요. 인플레이션 조정한 10년 평균 EPS로 주가 배수를 계산해서, 단기 이익 변동을 평활화해요. 장기 밸류에이션 측정에 사용해요.",
        "thresholds": [
            ("≤ 20",  "역사적 저평가", "good"),
            ("20~28", "보통 수준", "neutral"),
            ("28~38", "다소 고평가", "warn"),
            ("> 38",  "역사적 고평가", "bad"),
        ],
        "source_url": "https://www.multpl.com/shiller-pe",
        "source_label": "multpl.com — Shiller PE Ratio",
        "caveat": "AQR·IMF 연구에 따르면 단기 타이밍 신호가 아니라 10~20년 장기 수익률 예측 지표예요. 그래서 본 대시보드의 종합 신호 계산에는 포함하지 않아요.",
    },
    "sp500pe": {
        "title": "S&P500 PER (TTM)",
        "description": "최근 12개월 실제 EPS 기준으로 계산한 주가 배수예요. CAPE보다 더 빠르게 반응하지만, 단기 이익 변동성에 민감해서 위기 직후엔 왜곡될 수 있어요.",
        "thresholds": [
            ("≤ 17",  "역사 평균 이하", "good"),
            ("17~22", "적정 수준", "neutral"),
            ("22~28", "다소 고평가", "warn"),
            ("> 28",  "고평가", "bad"),
        ],
        "source_url": "https://www.multpl.com/s-p-500-pe-ratio",
        "source_label": "multpl.com — S&P 500 P/E Ratio",
        "caveat": "코로나·금융위기처럼 일시 이익 충격이 있으면 PER이 비정상적으로 튀어요. 그럴 땐 CAPE를 함께 참고하세요.",
    },
    "buffett": {
        "title": "버핏 지수 (Market Cap / GDP)",
        "description": "미국 주식 시가총액 합을 명목 GDP로 나눈 값이에요. 워렌 버핏이 시장 거품을 판단할 때 즐겨 쓴 지표라서 그의 이름이 붙었어요.",
        "thresholds": [
            ("≤ 80%",   "저평가", "good"),
            ("80~100%", "적정 수준", "neutral"),
            ("100~150%", "고평가 주의", "warn"),
            ("> 150%",  "매우 고평가 (버블 경고)", "bad"),
        ],
        "source_url": "https://www.longtermtrends.net/market-cap-to-gdp-the-buffett-indicator/",
        "source_label": "longtermtrends.net — Buffett Indicator",
        "caveat": "본 대시보드는 Wilshire 5000 지수 포인트 ÷ 하드코딩 GDP의 근사값이에요. GDP 상수는 수동 갱신이 필요해요(현재 코드 ~line 160).",
    },
    "dxy": {
        "title": "달러 강세 지수 (DXY)",
        "description": "유로·엔·파운드·캐나다달러·스웨덴크로나·스위스프랑 6개 주요 통화 대비 미국 달러의 상대 강도예요. 1973년 100을 기준점으로 시작했어요.",
        "thresholds": [
            ("< 100",   "달러 약세 (신흥국·상품 유리)", "good"),
            ("100~103", "보통", "neutral"),
            ("103~107", "달러 강세 (주의)", "warn"),
            ("> 107",   "달러 매우 강세", "bad"),
        ],
        "source_url": "https://finance.yahoo.com/quote/DX-Y.NYB",
        "source_label": "Yahoo Finance — DX-Y.NYB",
        "caveat": "달러 강세는 신흥국 주식·금·원자재에 역풍이 되고, 미국 수출기업 실적에도 부담이 돼요.",
    },
    "usdkrw": {
        "title": "원달러 환율",
        "description": "1달러를 사는 데 필요한 원화 금액이에요. 환율이 오르면 원화 가치가 떨어진 것이고, 내리면 원화가 강해진 거예요.",
        "thresholds": [
            ("≤ 1,280",     "원화 강세 (안정)", "good"),
            ("1,280~1,350", "보통", "neutral"),
            ("1,350~1,420", "원화 약세 (주의)", "warn"),
            ("> 1,420",     "원화 매우 약세", "bad"),
        ],
        "source_url": "https://finance.yahoo.com/quote/USDKRW=X",
        "source_label": "Yahoo Finance — USDKRW=X",
        "caveat": "환율 상승은 외국인 자금 유출 우려가 있지만, 한국 수출기업 실적엔 유리할 수 있어요. 단방향 해석은 위험해요.",
    },
    "rsi": {
        "title": "RSI (14일 상대강도지수)",
        "description": "최근 14거래일 동안 상승폭과 하락폭의 비율을 0~100으로 표현해요. Wilder's EMA 방식으로 계산해요. 단기 과열·과매도를 판단하는 가장 유명한 지표예요.",
        "thresholds": [
            ("≤ 30",  "과매도 — 반등 가능성", "good"),
            ("30~45", "저점 근처", "good"),
            ("45~60", "중립", "neutral"),
            ("60~70", "과열 주의", "warn"),
            ("> 70",  "과매수 — 조정 위험", "bad"),
        ],
        "source_url": "https://www.investopedia.com/terms/r/rsi.asp",
        "source_label": "Investopedia — Relative Strength Index",
        "caveat": "강한 추세장에서는 RSI가 70 이상이나 30 이하에 오래 머물 수 있어요. RSI만 보고 매매하는 건 위험해요.",
    },
    "hy_spread": {
        "title": "HY 회사채 스프레드 (신용 위험)",
        "description": "투자등급 미만 회사채(정크본드)와 미국채의 금리 차이예요. 회사채 디폴트 위험을 가격으로 반영해서, 신용 위기 가능성을 측정해요. ICE BofA US High Yield Index Option-Adjusted Spread (FRED 코드 BAMLH0A0HYM2) 기준이에요. 10Y-3M 금리차(12~24개월 전 침체 신호)보다 더 빠른 3~6개월 전 신호로 작동해요.",
        "thresholds": [
            ("< 3%",  "신용 위험 낮음 (시장 안정)", "good"),
            ("3~5%",  "정상 범위", "neutral"),
            ("5~7%",  "신용 스트레스 증가", "warn"),
            ("> 7%",  "신용 위기 (디폴트 위험 급등)", "bad"),
        ],
        "source_url": "https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
        "source_label": "FRED — ICE BofA US HY OAS",
        "caveat": "역사상 5% 이상 = 시장 우려, 7%+ = 침체/위기 (2008년 21.8%, 2020년 3월 11%까지 급등). S&P500과 강한 역상관 관계.",
    },
    "ma_cross": {
        "title": "S&P500 추세 강도 (50/200일선)",
        "description": "SPY의 50일선과 200일선의 위치 관계로 추세의 강도를 판정해요. 50일선이 200일선을 돌파해 위로 가면 '골든 크로스'(강세), 아래로 내려가면 '데드 크로스'(약세)예요. 가격까지 함께 봐서 4단계로 분류해요.",
        "thresholds": [
            ("가격 > 50선 > 200선", "강한 상승추세 (모든 신호 강세)", "good"),
            ("가격 > 200선, 50선 위", "상승추세 (단기 조정 가능)", "neutral"),
            ("가격 < 50선 또는 전환 중", "약세 신호 (전환 진행)", "warn"),
            ("가격 < 50선 < 200선", "강한 하락추세 (모든 신호 약세)", "bad"),
        ],
        "source_url": "https://finance.yahoo.com/quote/SPY/chart",
        "source_label": "Yahoo Finance — SPY 차트",
        "caveat": "200일선과 같이 후행 지표예요. 추세 전환의 확정 신호로 좋지만, 전환 직후엔 진입이 늦을 수 있어요.",
    },
    "dxy_trend": {
        "title": "달러 트렌드 (DXY MA200)",
        "description": "달러 지수(DXY)가 200일 이동평균보다 위인지 아래인지로 'risk-on/risk-off' 환경을 판정해요. 약달러(MA200 아래)는 신흥국·원자재·주식에 우호적이고, 강달러(MA200 위)는 글로벌 유동성 긴축 신호예요.",
        "thresholds": [
            ("DXY < MA200", "달러 약세 (위험자산 우호)", "good"),
            ("DXY > MA200", "달러 강세 (위험자산 역풍)", "warn"),
        ],
        "source_url": "https://finance.yahoo.com/quote/DX-Y.NYB",
        "source_label": "Yahoo Finance — DX-Y.NYB",
        "caveat": "달러 절대값(100 기준)과 함께 보면 더 정확해요. 강달러 + 상승추세 = 매우 강한 위험자산 역풍.",
    },
    "52w": {
        "title": "52주 고저 위치",
        "description": "지난 1년 최저가(0%)와 최고가(100%) 사이에서 현재가의 위치를 보여줘요. 저점 근처면 싸게 살 가능성, 고점 근처면 추격 매수 위험을 나타내요.",
        "thresholds": [
            ("≤ 30%",  "저점 근처 (저가)", "good"),
            ("30~70%", "중간 구간", "neutral"),
            ("70~85%", "고점 근처 (고가)", "warn"),
            ("> 85%",  "52주 고점 부근", "bad"),
        ],
        "source_url": "https://finance.yahoo.com/",
        "source_label": "Yahoo Finance — 종목별 차트",
        "caveat": "추세가 살아있는 종목은 52주 고점을 계속 갱신해요. 단순 진입 회피 기준으로만 쓰면 좋은 기회를 놓칠 수 있어요.",
    },
}


def signal_color(label, value):
    if value is None:
        return "neutral", "데이터 없음"
    if label == "fear_greed":
        # CNN 공식 구간: 0-24 극도공포 / 25-44 공포 / 45-55 중립 / 56-74 탐욕 / 75-100 극도탐욕
        if value <= 24: return "good",    "극도의 공포 (역사적 매수 기회)"
        if value <= 44: return "good",    "공포 구간 (매수 기회)"
        if value <= 55: return "neutral", "중립"
        if value <= 74: return "warn",    "탐욕 구간 (주의)"
        return "bad", "극도의 탐욕 (고점 경고)"
    if label == "rsi":
        if value <= 30: return "good",    "과매도 — 반등 가능성"
        if value <= 45: return "good",    "저점 근처"
        if value <= 60: return "neutral", "중립"
        if value <= 70: return "warn",    "과열 주의"
        return "bad", "과매수 — 조정 위험"
    if label == "cape":
        # 역사 평균 ~17, 현대 시장 구조 고려
        if value <= 20: return "good",    "역사적 저평가"
        if value <= 28: return "neutral", "보통 수준"
        if value <= 38: return "warn",    "다소 고평가"
        return "bad", "역사적 고평가"
    if label == "buffett":
        # Buffett 기준: ~100% 적정, 200% 이상 위험
        if value <= 80:  return "good",    "저평가"
        if value <= 100: return "neutral", "적정 수준"
        if value <= 150: return "warn",    "고평가 주의"
        return "bad", "매우 고평가"
    if label == "vix":
        if value < 15:  return "warn",    "지나치게 조용함 (과신 주의)"
        if value <= 20: return "neutral", "안정적인 시장"
        if value <= 30: return "good",    "적당한 긴장 (기회 탐색)"
        if value <= 40: return "good",    "공포 구간 (역발투자 기회)"
        # VIX 40+는 역사적으로 최고의 장기 매수 기회이기도 함
        return "warn",  "극단적 공포 (장기 역발투자 기회, 단기 매우 위험)"
    if label == "dxy":
        if value < 100:  return "good",    "달러 약세 (신흥국·상품 유리)"
        if value <= 103: return "neutral", "보통"
        if value <= 107: return "warn",    "달러 강세 (주의)"
        return "bad", "달러 매우 강세"
    if label == "yield_spread":
        # 10Y-3M 스프레드
        if value > 0.5:   return "neutral", "정상 (경기 양호)"
        if value >= 0:    return "warn",    "금리차 축소 (주의)"
        if value >= -0.5: return "warn",    "부분 역전 (침체 우려)"
        return "bad", "완전 역전 (침체 경고)"
    if label == "ma200":  # bool
        return ("good", "200일선 위 (상승추세)") if value else ("bad", "200일선 아래 (하락추세)")
    if label == "52w":
        if value <= 30:  return "good",    "52주 저점 근처 (저가)"
        if value <= 70:  return "neutral", "중간 구간"
        if value <= 85:  return "warn",    "고점 근처 (고가)"
        return "bad", "52주 고점 부근"
    if label == "usdkrw":
        if value <= 1280: return "good",    "원화 강세 (안정)"
        if value <= 1350: return "neutral", "보통"
        if value <= 1420: return "warn",    "원화 약세 (주의)"
        return "bad", "원화 매우 약세"
    if label == "sp500pe":
        if value <= 17: return "good",    "역사 평균 이하"
        if value <= 22: return "neutral", "적정 수준"
        if value <= 28: return "warn",    "다소 고평가"
        return "bad", "고평가"
    if label == "hy_spread":
        # HY Credit Spread (BAMLH0A0HYM2). 단위: 퍼센트 포인트
        if value < 3:    return "good",    "신용 위험 낮음 (시장 안정)"
        if value <= 5:   return "neutral", "정상 범위"
        if value <= 7:   return "warn",    "신용 스트레스 증가"
        return "bad", "신용 위기 (디폴트 위험 급등)"
    if label == "ma_cross":
        # ma_cross: "strong_bull" / "bull" / "bear" / "strong_bear"
        if value == "strong_bull":  return "good",    "강한 상승추세 (50선·200선 모두 위)"
        if value == "bull":         return "neutral", "상승추세 (단기 조정 가능)"
        if value == "bear":         return "warn",    "약세 신호 (전환 진행)"
        if value == "strong_bear":  return "bad",     "강한 하락추세 (50선·200선 모두 아래)"
        return "neutral", "데이터 없음"
    if label == "dxy_trend":  # bool
        if value is True:   return "warn", "달러 강세 (위험자산 역풍)"
        if value is False:  return "good", "달러 약세 (위험자산 우호)"
        return "neutral", "데이터 없음"
    return "neutral", ""


def overall_signal(keys):
    # 7개 컴포넌트 기준: 점수 범위 -14 ~ +7
    score = sum(SCORE_MAP.get(k, 0) for k in keys)
    # 7개로 확장됨에 따라 임계값 재조정 (이전 4개: ≥+2/≥0/≥-3/<-3 → 7개: ≥+4/≥0/≥-5/<-5)
    if score >= 4:
        return "good",    "매수 유리",        "전반적으로 긍정적인 신호예요. 장기 투자를 시작하기 좋은 환경이에요."
    if score >= 0:
        return "neutral", "중립 — 관망 추천", "긍정과 부정 신호가 섞여 있어요. 급하게 움직이지 않아도 돼요."
    if score >= -5:
        return "warn",    "주의 — 신중하게",  "부정적 지표가 늘고 있어요. 분할 매수나 관망을 추천해요."
    return "bad", "위험 — 방어적으로", "전반적으로 위험 신호가 많아요. 현금 비중을 높이는 게 좋을 수 있어요."


def overall_signal_from_data(data):
    """7개 타이밍 지표 기반 종합 신호 계산. build_html과 format_kakao_summary 공용.

    구성: 심리(F&G) · 변동성(VIX) · 경기(yield spread) · 시장 추세(MA200) ·
          추세 강도(50/200 cross) · 신용(HY spread) · 통화(DXY 트렌드)

    Returns: {key, label, comment, good, warn, bad, neutral}
    """
    fg = data.get("fear_greed") or {}
    fg_score = fg.get("score") if isinstance(fg, dict) else None
    fg_sig, _ = signal_color("fear_greed", fg_score)
    vx_sig, _ = signal_color("vix", data.get("vix"))
    ys = data.get("yield_spread") or {}
    ys_val = ys.get("spread") if isinstance(ys, dict) else None
    ys_sig, _ = signal_color("yield_spread", ys_val)
    tr_sig, _ = signal_color("ma200", data.get("sp500_trend"))
    # 신규 3개
    mc_sig, _ = signal_color("ma_cross", data.get("sp500_ma_cross"))
    hy_sig, _ = signal_color("hy_spread", data.get("hy_spread"))
    dxy_data = data.get("dxy") or {}
    dxy_above_ma200 = dxy_data.get("above_ma200") if isinstance(dxy_data, dict) else None
    dxt_sig, _ = signal_color("dxy_trend", dxy_above_ma200)

    macro_keys = [fg_sig, vx_sig, ys_sig, tr_sig, mc_sig, hy_sig, dxt_sig]
    ov_key, ov_label, ov_comment = overall_signal(macro_keys)
    return {
        "key": ov_key,
        "label": ov_label,
        "comment": ov_comment,
        "good": macro_keys.count("good"),
        "warn": macro_keys.count("warn"),
        "bad": macro_keys.count("bad"),
        "neutral": macro_keys.count("neutral"),
    }


_OV_EMOJI = {"good": "🟢", "neutral": "⚪", "warn": "🟡", "bad": "🔴"}


def format_kakao_summary(data):
    """카톡 메모용 텍스트 요약. 모든 값 None 가드. 약 150자 이내."""
    sig = overall_signal_from_data(data)
    now_kst = datetime.now(KST)
    today = f"{now_kst.month}/{now_kst.day}({_KR_WEEKDAY[now_kst.weekday()]})"

    fg = data.get("fear_greed") or {}
    fg_score = fg.get("score") if isinstance(fg, dict) else None
    vix = data.get("vix")
    ys = data.get("yield_spread") or {}
    ys_val = ys.get("spread") if isinstance(ys, dict) else None
    trend = data.get("sp500_trend")
    trend_pct = data.get("sp500_trend_pct")

    fg_line = f"😨 공포탐욕 {fg_score}" if fg_score is not None else "😨 공포탐욕 N/A"
    vix_line = f"🌊 VIX {vix}" if vix is not None else "🌊 VIX N/A"
    ys_line = f"📉 금리차 {ys_val:+.2f}%p" if ys_val is not None else "📉 금리차 N/A"

    if trend is True:
        tp = trend_pct if trend_pct is not None else 0
        tr_line = f"📏 S&P500 200일선 위 (↑{abs(tp):.1f}%)"
    elif trend is False:
        tp = trend_pct if trend_pct is not None else 0
        tr_line = f"📏 S&P500 200일선 아래 (↓{abs(tp):.1f}%)"
    else:
        tr_line = "📏 S&P500 추세 N/A"

    ov_emoji = _OV_EMOJI.get(sig["key"], "⚪")
    site_url = os.environ.get("SITE_URL", "https://stock.gymcoding.co")

    return "\n".join([
        f"📊 {today} 투자 신호",
        "",
        f"{ov_emoji} 종합: {sig['label']} (긍정 {sig['good']}·주의 {sig['warn']}·위험 {sig['bad']})",
        fg_line,
        vix_line,
        ys_line,
        tr_line,
        "",
        f"👉 {site_url}",
    ])


# ── Data Fetching ─────────────────────────────────────────────────────────────

def fetch_fear_greed():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0",
            "Referer": "https://money.cnn.com/",
            "Origin": "https://money.cnn.com",
        }
        r = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers=headers, timeout=10,
        )
        d = r.json()["fear_and_greed"]
        return {"score": round(float(d["score"])), "rating": d["rating"]}
    except Exception as e:
        print(f"  ⚠️  Fear & Greed 실패: {e}")
        return {"score": None, "rating": "N/A"}


def fetch_cape():
    try:
        r = requests.get(
            "https://www.multpl.com/shiller-pe/table/by-month",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10,
        )
        tables = pd.read_html(r.text)
        val = round(float(str(tables[0].iloc[0, 1]).replace("*", "").replace("†", "").strip()), 1)
        return val if 5 < val < 100 else None
    except Exception as e:
        print(f"  ⚠️  CAPE 실패: {e}")
        return None


def fetch_sp500_pe():
    """S&P500 trailing 12-month PER from multpl.com."""
    try:
        r = requests.get(
            "https://www.multpl.com/s-p-500-pe-ratio/table/by-month",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10,
        )
        tables = pd.read_html(r.text)
        val = round(float(str(tables[0].iloc[0, 1]).replace("*", "").replace("†", "").strip()), 1)
        return val if 5 < val < 200 else None
    except Exception as e:
        print(f"  ⚠️  S&P500 PER 실패: {e}")
        return None


def fetch_buffett_indicator():
    """Wilshire 5000 index / US GDP (근사값). 방법론: 지수 포인트 기반 추정."""
    try:
        with _yf_lock:
            df = yf.download("^W5000", period="5d", progress=False, auto_adjust=True, threads=False)
        if df.empty:
            return None
        # ^W5000 포인트는 1974년 설계상 1pt ≈ $1B이나 현재는 근사 추정에만 사용
        # GDP: 최신 미국 연간 GDP 추정값 (분기별 갱신 필요)
        gdp_billions = 29_932.0  # 2024 Q4 BEA 추정
        return round(float(df["Close"].squeeze().iloc[-1]) / gdp_billions * 100, 1)
    except Exception as e:
        print(f"  ⚠️  버핏 지수 실패: {e}")
        return None


def fetch_vix():
    try:
        with _yf_lock:
            df = yf.download("^VIX", period="5d", progress=False, auto_adjust=True, threads=False)
        return round(float(df["Close"].squeeze().iloc[-1]), 1) if not df.empty else None
    except Exception as e:
        print(f"  ⚠️  VIX 실패: {e}")
        return None


def fetch_dxy():
    """DXY 현재값 + 200일선 추세. 약달러(< MA200) = risk-on / 강달러(> MA200) = risk-off."""
    try:
        with _yf_lock:
            df = yf.download("DX-Y.NYB", period="1y", interval="1d",
                             progress=False, auto_adjust=True, threads=False)
        if df.empty:
            return None
        close = df["Close"].squeeze()
        price = round(float(close.iloc[-1]), 2)
        result = {"value": price, "above_ma200": None}
        if len(close) >= 200:
            ma200 = float(close.rolling(200).mean().iloc[-1])
            result["above_ma200"] = price > ma200
            result["ma200_diff_pct"] = round((price - ma200) / ma200 * 100, 1)
        return result
    except Exception as e:
        print(f"  ⚠️  DXY 실패: {e}")
        return None


def fetch_usdkrw():
    try:
        with _yf_lock:
            df = yf.download("USDKRW=X", period="5d", progress=False, auto_adjust=True, threads=False)
        return round(float(df["Close"].squeeze().iloc[-1]), 1) if not df.empty else None
    except Exception as e:
        print(f"  ⚠️  원달러 환율 실패: {e}")
        return None


def fetch_hy_spread():
    """ICE BofA US High Yield Index Option-Adjusted Spread (FRED BAMLH0A0HYM2).

    회사채 디폴트 위험 측정. yield curve(12~24개월 전 신호)보다 빠른 3~6개월 전 신호.
    < 3%: 신용 위험 낮음(좋음), 3~5%: 정상, 5~7%: 스트레스 증가, > 7%: 위기.
    """
    try:
        # FRED 공개 CSV API — 인증 키 불필요
        r = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2",
            timeout=10,
        )
        r.raise_for_status()
        # 마지막 비어있지 않은 데이터 줄 찾기 (FRED는 최근 영업일 데이터까지)
        for line in reversed(r.text.strip().split("\n")):
            parts = line.split(",")
            if len(parts) == 2 and parts[1] not in ("", ".", "value"):
                try:
                    return round(float(parts[1]), 2)
                except ValueError:
                    continue
        return None
    except Exception as e:
        print(f"  ⚠️  HY Spread 실패: {e}")
        return None


def fetch_yield_spread():
    """10Y - 3M Treasury yield spread (^TNX - ^IRX). 참고: ^IRX는 Bank Discount 방식."""
    try:
        with _yf_lock:
            df10 = yf.download("^TNX", period="5d", progress=False, auto_adjust=True, threads=False)
            df3m = yf.download("^IRX", period="5d", progress=False, auto_adjust=True, threads=False)
        if df10.empty or df3m.empty:
            return None
        y10 = round(float(df10["Close"].squeeze().iloc[-1]), 2)
        y3m = round(float(df3m["Close"].squeeze().iloc[-1]), 2)
        return {"spread": round(y10 - y3m, 2), "y3m": y3m, "y10": y10}
    except Exception as e:
        print(f"  ⚠️  금리차 실패: {e}")
        return None


def analyze_ticker(ticker, name):
    try:
        with _yf_lock:
            df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True, threads=False)
        if df.empty or len(df) < 5:
            raise ValueError("no data")
        close = df["Close"].squeeze()
        price = float(close.iloc[-1])
        prev  = float(close.iloc[-2])
        change_pct = (price - prev) / prev * 100

        # RSI — Wilder's EMA (표준 방식, alpha=1/14)
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = float((100 - 100 / (1 + gain / loss)).iloc[-1])

        # MA200 — 데이터가 200일 미만이면 None
        ma200_above = None
        ma200_diff  = None
        ma200_val = None
        if len(close) >= 200:
            ma200_val = float(close.rolling(200).mean().iloc[-1])
            ma200_above = price > ma200_val
            ma200_diff  = round((price - ma200_val) / ma200_val * 100, 1)

        # MA50 + Golden Cross (50일선이 200일선 위/아래)
        ma_cross = None  # "strong_bull" / "bull" / "bear" / "strong_bear"
        if len(close) >= 200:
            ma50_val = float(close.rolling(50).mean().iloc[-1])
            above_50 = price > ma50_val
            above_200 = price > ma200_val
            cross_up = ma50_val > ma200_val  # Golden cross 상태
            if above_50 and above_200 and cross_up:
                ma_cross = "strong_bull"   # 모든 신호 강세
            elif above_200 and cross_up:
                ma_cross = "bull"           # 장기 강세, 단기 약간 조정
            elif not above_50 and not above_200 and not cross_up:
                ma_cross = "strong_bear"   # 모든 신호 약세
            else:
                ma_cross = "bear"           # 약세 또는 전환 중

        # 52주 위치
        high = float(close.max())
        low  = float(close.min())
        pos_52w = (price - low) / (high - low) * 100 if high != low else 50.0

        is_kr = ticker in ("^KS11", "^KQ11")
        price_str = f"{price:,.2f}" if is_kr else f"${price:,.2f}"

        return {
            "name": name, "ticker": ticker, "price_str": price_str,
            "change_pct": round(change_pct, 2), "rsi": round(rsi, 1),
            "ma200_above": ma200_above, "ma200_diff_pct": ma200_diff,
            "ma_cross": ma_cross,
            "pos_52w": round(pos_52w, 1),
        }
    except Exception as e:
        print(f"  ⚠️  {name} ({ticker}) 실패: {e}")
        return {
            "name": name, "ticker": ticker, "price_str": "N/A",
            "change_pct": None, "rsi": None,
            "ma200_above": None, "ma200_diff_pct": None, "ma_cross": None,
            "pos_52w": None,
        }


# ── HTML Helpers ──────────────────────────────────────────────────────────────

# text-muted: #a0aab4 — WCAG AA 명암비 ≈ 5.1:1 (#0d1117 대비)
_STYLE = """<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.min.css" />
<style type="text/tailwindcss">
@theme {
  --color-good:    #3fb950;
  --color-warn:    #d29922;
  --color-danger:  #f85149;
  --color-surface: #161b22;
  --color-base:    #0d1117;
  --color-frame:   #21262d;
  --color-muted:   #a0aab4;
  --color-fg:      #e6edf3;
  --font-sans:     'Pretendard', -apple-system, BlinkMacSystemFont, 'Malgun Gothic', 'Noto Sans KR', sans-serif;
}
body {
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  -webkit-text-size-adjust: 100%;
}
details summary { cursor: pointer; list-style: none; }
details summary::-webkit-details-marker { display: none; }
details[open] .arrow { transform: rotate(90deg); }

/* 모바일 터치 피드백 — hover가 없는 환경(터치 디바이스) */
@media (hover: none) {
  [data-indicator]:active { background-color: rgb(33 38 45 / 0.5); }
  [role="button"]:active { transform: scale(0.99); transition: transform 0.08s; }
}

/* iOS Safari 안전 영역 — 노치 대응 */
@supports (padding: env(safe-area-inset-bottom)) {
  body { padding-bottom: env(safe-area-inset-bottom); }
}

/* 모달 바텀시트 (모바일) — 데스크탑에서는 기본 가운데 모달 */
@keyframes slide-up { from { transform: translateY(20%); } to { transform: translateY(0); } }
@media (max-width: 639px) {
  #indicator-modal { align-items: flex-end; padding: 0; }
  #modal-card {
    max-width: 100%;
    max-height: 88vh;
    max-height: 88dvh;
    border-radius: 1rem 1rem 0 0;
    border-bottom: 0;
    animation: slide-up 0.2s ease-out;
  }
}
</style>"""


def _badge(sig):
    c = _CLS.get(sig, _CLS["neutral"])
    return (f'<span class="inline-flex whitespace-nowrap {c["bg"]} {c["text"]} border {c["border"]} '
            f'rounded-full px-2.5 py-0.5 text-xs font-bold">{_KR.get(sig, "중립")}</span>')


def _macro_card(key, emoji, title, en, val_html, sig, sig_txt, hint, detail_html="", current_value=None):
    c = _CLS.get(sig, _CLS["neutral"])
    detail = f"\n  {detail_html}" if detail_html else ""
    # current_value: 명시되면 그대로 사용 (호출자 책임), None이면 val_html + sig_txt 자동 결합
    if current_value is not None:
        cur_attr = current_value
    elif sig_txt:
        cur_attr = f"{val_html} · {sig_txt}"
    else:
        cur_attr = val_html
    return f"""<div class="bg-surface border border-frame rounded-2xl p-4 sm:p-5 flex flex-col gap-3 cursor-pointer hover:border-fg/30 transition-colors" data-indicator="{key}" data-current="{cur_attr}" data-sig="{sig}" role="button" tabindex="0" aria-label="{title} 상세 보기">
  <div class="flex items-start justify-between gap-2">
    <div class="min-w-0">
      <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-0.5 truncate">{en}</div>
      <div class="font-semibold text-fg text-sm sm:text-base"><span aria-hidden="true">{emoji}</span> {title}</div>
    </div>
    {_badge(sig)}
  </div>
  <div class="text-2xl sm:text-3xl font-bold {c['text']}">{val_html}</div>{detail}
  <div class="text-xs sm:text-sm {c['text']}">{sig_txt}</div>
  <div class="mt-auto text-xs text-muted border-t border-frame pt-2 flex justify-between items-center gap-2">
    <span class="leading-relaxed">{hint}</span>
    <span class="text-fg/40 text-xs shrink-0" aria-hidden="true">ⓘ</span>
  </div>
</div>"""


def _gauge(score):
    if score is None:
        return '<div class="h-20 flex items-center justify-center text-muted text-sm">데이터 없음</div>'
    pct = max(0, min(100, score))
    rad = math.radians(180 * (1 - pct / 100))
    nx, ny = 80 + 55 * math.cos(rad), 85 - 55 * math.sin(rad)
    return (f'<svg width="160" height="95" viewBox="0 0 160 95" class="mx-auto block"'
            f' role="img" aria-label="공포탐욕지수 게이지: 현재 {score}점">'
            '<defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="0%">'
            '<stop offset="0%" stop-color="#f85149"/>'
            '<stop offset="25%" stop-color="#d29922"/>'
            '<stop offset="50%" stop-color="#8b949e"/>'
            '<stop offset="100%" stop-color="#3fb950"/>'
            '</linearGradient></defs>'
            '<path d="M10,85 A70,70 0 0,1 150,85" fill="none" stroke="#21262d" stroke-width="14" stroke-linecap="round"/>'
            '<path d="M10,85 A70,70 0 0,1 150,85" fill="none" stroke="url(#g)" stroke-width="14" stroke-linecap="round"/>'
            f'<line x1="80" y1="85" x2="{nx:.1f}" y2="{ny:.1f}" stroke="white" stroke-width="3" stroke-linecap="round"/>'
            '<circle cx="80" cy="85" r="5" fill="white"/>'
            '<text x="10" y="97" fill="#a0aab4" font-size="9" text-anchor="middle">공포</text>'
            '<text x="150" y="97" fill="#a0aab4" font-size="9" text-anchor="middle">탐욕</text>'
            '</svg>')


def _index_card(t):
    if t["price_str"] == "N/A":
        return f"""<div class="bg-surface border border-frame rounded-2xl p-4 sm:p-5">
  <div class="font-semibold text-fg mb-1">{t['name']}</div>
  <div class="text-xs text-muted mb-3">{t['ticker']}</div>
  <div class="text-muted text-sm">데이터 없음</div>
</div>"""

    chg = t["change_pct"] if t["change_pct"] is not None else 0
    chg_str = f"{'▲' if chg >= 0 else '▼'} {abs(chg):.2f}%"
    chg_cls = "text-good bg-good/10" if chg >= 0 else "text-danger bg-danger/10"

    rsi_sig, rsi_txt = signal_color("rsi", t["rsi"])
    rc = _CLS.get(rsi_sig, _CLS["neutral"])

    # MA200
    if t["ma200_above"] is not None:
        ma_sig, ma_txt = signal_color("ma200", t["ma200_above"])
        mc = _CLS.get(ma_sig, _CLS["neutral"])
        diff = t["ma200_diff_pct"] if t["ma200_diff_pct"] is not None else 0
        arrow = "↑" if diff >= 0 else "↓"
        diff_str = f"({arrow}{abs(diff):.1f}%)"
        ma_position = "200일선 위" if t["ma200_above"] else "200일선 아래"
        short_ma = "상승추세" if t["ma200_above"] else "하락추세"
        ma_current = f"{t['name']} · {ma_position} {arrow}{abs(diff):.1f}% · {short_ma}"
        ma_html = f"""<div class="flex items-center justify-between gap-2 text-xs cursor-pointer hover:bg-frame/40 rounded px-1 -mx-1 py-1 transition-colors" data-indicator="ma200" data-current="{ma_current}" data-sig="{ma_sig}" role="button" tabindex="0" aria-label="MA200 설명">
      <span class="text-muted min-w-0">MA200 <span class="font-mono">{diff_str}</span></span>
      <span class="{mc['bg']} {mc['text']} {mc['border']} border rounded-full px-2 py-0.5 font-semibold whitespace-nowrap shrink-0">{ma_txt}</span>
    </div>"""
    else:
        ma_current = f"{t['name']} · MA200 데이터 부족 (1년 미만)"
        ma_html = f'<div class="text-xs text-muted cursor-pointer hover:bg-frame/40 rounded px-1 -mx-1 transition-colors" data-indicator="ma200" data-current="{ma_current}" data-sig="neutral" role="button" tabindex="0" aria-label="MA200 설명">MA200 데이터 부족 (1년 미만)</div>'

    pos = t["pos_52w"] if t["pos_52w"] is not None else 50
    pos_col = "#3fb950" if pos <= 30 else ("#d29922" if pos <= 70 else "#f85149")
    pos_sig, pos_txt = signal_color("52w", pos)
    pos_current = f"{t['name']} · 52주 저점에서 {pos:.0f}% 위치 · {pos_txt}"
    rsi_current = f"{t['name']} · RSI {t['rsi']} · {rsi_txt}"

    return f"""<div class="bg-surface border border-frame rounded-2xl p-4 sm:p-5 flex flex-col gap-3">
  <div class="flex items-start justify-between gap-2">
    <div class="min-w-0">
      <div class="font-semibold text-fg truncate">{t['name']}</div>
      <div class="text-xs text-muted">{t['ticker']}</div>
    </div>
    <span class="text-xs {chg_cls} rounded-full px-2 py-0.5 font-bold whitespace-nowrap shrink-0">{chg_str}</span>
  </div>
  <div class="text-2xl font-bold text-fg">{t['price_str']}</div>
  <div class="border-t border-frame pt-3 flex flex-col gap-2">
    <div class="flex items-center justify-between gap-2 text-xs cursor-pointer hover:bg-frame/40 rounded px-1 -mx-1 py-1 transition-colors" data-indicator="rsi" data-current="{rsi_current}" data-sig="{rsi_sig}" role="button" tabindex="0" aria-label="RSI 설명">
      <span class="text-muted min-w-0">RSI <span class="font-mono font-bold">{t['rsi']}</span> <span class="text-muted/60 hidden sm:inline">(30↓매수·70↑주의)</span></span>
      <span class="{rc['bg']} {rc['text']} {rc['border']} border rounded-full px-2 py-0.5 font-semibold whitespace-nowrap shrink-0">{rsi_txt}</span>
    </div>
    {ma_html}
    <div class="mt-0.5 cursor-pointer hover:bg-frame/40 rounded px-1 -mx-1 py-1 transition-colors" data-indicator="52w" data-current="{pos_current}" data-sig="{pos_sig}" role="button" tabindex="0" aria-label="52주 위치 설명">
      <div class="flex justify-between text-xs text-muted mb-1">
        <span>52주 저점</span>
        <span class="font-bold" style="color:{pos_col}">{pos:.0f}%</span>
        <span>고점</span>
      </div>
      <div class="h-1.5 rounded-full bg-frame overflow-hidden">
        <div class="h-full rounded-full" style="width:{pos:.0f}%;background:{pos_col}"></div>
      </div>
    </div>
  </div>
</div>"""


def _guide(term, short, detail):
    return f"""<details class="border border-frame rounded-xl overflow-hidden">
  <summary class="flex items-center gap-3 p-3 sm:p-4 hover:bg-frame/50 transition-colors min-h-[48px]">
    <span class="font-semibold text-fg text-sm shrink-0"><span aria-hidden="true">{term.split()[0]}</span> {' '.join(term.split()[1:])}</span>
    <span class="text-muted text-xs flex-1 hidden sm:inline truncate">{short}</span>
    <span class="arrow text-muted text-xs transition-transform duration-200 ml-auto sm:ml-0 shrink-0" aria-hidden="true">▶</span>
  </summary>
  <div class="px-3 sm:px-4 pb-3 sm:pb-4 pt-3 text-sm text-muted leading-relaxed border-t border-frame">{detail}</div>
</details>"""


# ── build_html ────────────────────────────────────────────────────────────────

def build_html(data, serve_mode=True):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    indicator_info_json = json.dumps(INDICATOR_INFO, ensure_ascii=False)
    refresh_block = (
        '<button id="refresh-btn" type="button" class="mt-0 sm:mt-2 inline-flex items-center gap-1.5 bg-frame hover:bg-frame/70 border border-frame text-fg text-sm rounded-full px-3 py-2 transition-colors disabled:opacity-50 disabled:cursor-wait min-h-[36px]" aria-label="데이터 새로고침">'
        '<span id="refresh-icon" aria-hidden="true">🔄</span><span id="refresh-text">새로고침</span></button>'
        if serve_mode
        else '<div class="text-xs text-muted mt-1.5">터미널에서 <code class="bg-frame px-1 rounded font-mono">python3 dashboard.py</code> 실행 시 갱신</div>'
    )

    fg       = data["fear_greed"]
    fg_sig,  fg_txt  = signal_color("fear_greed",   fg["score"])
    ca_sig,  ca_txt  = signal_color("cape",          data["cape"])
    pe_sig,  pe_txt  = signal_color("sp500pe",       data["sp500pe"])
    bu_sig,  bu_txt  = signal_color("buffett",       data["buffett"])
    vx_sig,  vx_txt  = signal_color("vix",           data["vix"])
    dxy_data = data.get("dxy") or {}
    dxy_val = dxy_data.get("value") if isinstance(dxy_data, dict) else None
    dxy_above_ma200 = dxy_data.get("above_ma200") if isinstance(dxy_data, dict) else None
    dxy_diff_pct = dxy_data.get("ma200_diff_pct") if isinstance(dxy_data, dict) else None
    dx_sig,  dx_txt  = signal_color("dxy",           dxy_val)
    dxt_sig, dxt_txt = signal_color("dxy_trend",     dxy_above_ma200)
    kr_sig,  kr_txt  = signal_color("usdkrw",        data["usdkrw"])
    ys       = data["yield_spread"]
    ys_val   = ys["spread"] if ys else None
    ys_sig,  ys_txt  = signal_color("yield_spread",  ys_val)
    tr_sig,  tr_txt  = signal_color("ma200",          data.get("sp500_trend"))

    # 종합 신호: overall_signal_from_data로 추출 (M3) — format_kakao_summary와 공용
    _sig = overall_signal_from_data(data)
    ov_key, ov_label, ov_comment = _sig["key"], _sig["label"], _sig["comment"]
    good_n, warn_n, bad_n, neutral_n = _sig["good"], _sig["warn"], _sig["bad"], _sig["neutral"]

    ov_c   = _CLS.get(ov_key, _CLS["neutral"])
    ov_dot = _DOT.get(ov_key, "#8b949e")

    # ── Fear & Greed 카드 ──
    fg_str = str(fg["score"]) if fg["score"] is not None else "N/A"
    fg_current = f"{fg_str} / 100 · {fg_txt}"
    fear_card = f"""<div class="bg-surface border border-frame rounded-2xl p-4 sm:p-5 flex flex-col gap-3 cursor-pointer hover:border-fg/30 transition-colors" data-indicator="fear_greed" data-current="{fg_current}" data-sig="{fg_sig}" role="button" tabindex="0" aria-label="공포 탐욕 지수 상세 보기">
  <div class="flex items-start justify-between gap-2">
    <div class="min-w-0">
      <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-0.5 truncate">CNN Fear &amp; Greed</div>
      <div class="font-semibold text-fg text-sm sm:text-base"><span aria-hidden="true">😨</span> 공포 &amp; 탐욕 지수</div>
    </div>
    {_badge(fg_sig)}
  </div>
  {_gauge(fg["score"])}
  <div class="text-center text-2xl sm:text-3xl font-bold {_CLS[fg_sig]['text']}">{fg_str} <span class="text-base font-normal text-muted">/ 100</span></div>
  <div class="text-xs sm:text-sm {_CLS[fg_sig]['text']} text-center">{fg_txt}</div>
  <div class="mt-auto text-xs text-muted border-t border-frame pt-2 flex justify-between items-center gap-2">
    <span class="leading-relaxed">0에 가까울수록 투자자들이 겁먹은 상태예요. 겁먹었을 때가 사기 좋은 타이밍이에요.</span>
    <span class="text-fg/40 text-xs shrink-0" aria-hidden="true">ⓘ</span>
  </div>
</div>"""

    vix_card = _macro_card("vix", "🌊", "VIX 공포 지수", "CBOE Volatility Index",
        f"{data['vix']}" if data["vix"] else "N/A", vx_sig, vx_txt,
        "앞으로 주가가 얼마나 흔들릴지 예측해요. 20 이상이면 불안한 시장, 30~40이면 역발투자 기회 구간이에요.")

    dxy_card = _macro_card("dxy", "💵", "달러 강세 지수", "US Dollar Index (DXY)",
        f"{dxy_val}" if dxy_val else "N/A", dx_sig, dx_txt,
        "달러가 강하면 한국 주식·금·원유에 부담이 돼요. 100이 기준선이에요.")

    kr_val = f"₩{data['usdkrw']:,.0f}" if data["usdkrw"] else "N/A"
    kr_card = _macro_card("usdkrw", "🇰🇷", "원달러 환율", "USD/KRW",
        kr_val, kr_sig, kr_txt,
        "환율이 오르면 원화 가치가 떨어진 거예요. 외국인 자금이 빠져나가는 신호일 수 있어요.")

    # CAPE 카드: 현재값 기준 역사 평균과 비교 표시
    cape_val = data["cape"]
    cape_html = f"{cape_val}" if cape_val else "N/A"
    cape_card = _macro_card("cape", "📊", "CAPE (Shiller PE)", "Shiller P/E Ratio",
        cape_html, ca_sig, ca_txt,
        "10년 평균 이익 기준 주가 배수예요. 역사 평균 약 17, 20 이하면 저평가, 38 이상이면 역사적 고평가예요.")

    # S&P500 PER 카드
    pe_val = data["sp500pe"]
    pe_html = f"{pe_val}" if pe_val else "N/A"
    pe_card = _macro_card("sp500pe", "📈", "S&P500 PER", "S&P 500 Trailing P/E",
        pe_html, pe_sig, pe_txt,
        "최근 12개월 실적 기준 주가 배수예요. 역사 평균 약 16~17, 25 이상이면 고평가 신호예요.")

    buff_card = _macro_card("buffett", "🏦", "버핏 지수", "Buffett Indicator (근사값)",
        f"{data['buffett']}%" if data["buffett"] else "N/A", bu_sig, bu_txt,
        "시장 시가총액 ÷ GDP예요. Buffett 기준: 100%=적정, 200%=위험. 현재값은 Wilshire 5000 기반 추정치예요.")

    # 금리차 카드: 주요 수치와 세부 정보 분리
    if ys:
        ys_main = f"{ys_val:+.2f}%p"
        ys_sub = f"단기(3M) {ys['y3m']}% · 장기(10Y) {ys['y10']}%"
    else:
        ys_main, ys_sub = "N/A", ""
    ys_detail = f'<div class="text-xs text-muted">{ys_sub}</div>' if ys_sub else ""
    ys_current = f"{ys_main} · {ys_txt}"
    ys_html = f"""<div class="bg-surface border border-frame rounded-2xl p-4 sm:p-5 flex flex-col gap-3 cursor-pointer hover:border-fg/30 transition-colors" data-indicator="yield_spread" data-current="{ys_current}" data-sig="{ys_sig}" role="button" tabindex="0" aria-label="금리차 상세 보기">
  <div class="flex items-start justify-between gap-2">
    <div class="min-w-0">
      <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-0.5 truncate">10Y-3M Yield Spread</div>
      <div class="font-semibold text-fg text-sm sm:text-base"><span aria-hidden="true">📉</span> 금리차 (경기침체 신호)</div>
    </div>
    {_badge(ys_sig)}
  </div>
  <div class="text-2xl sm:text-3xl font-bold {_CLS[ys_sig]['text']}">{ys_main}</div>
  {ys_detail}
  <div class="text-xs sm:text-sm {_CLS[ys_sig]['text']}">{ys_txt}</div>
  <div class="mt-auto text-xs text-muted border-t border-frame pt-2 flex justify-between items-center gap-2">
    <span class="leading-relaxed">장기금리 - 단기금리예요. 0% 아래로 내려가면 경기침체 경고등이에요.</span>
    <span class="text-fg/40 text-xs shrink-0" aria-hidden="true">ⓘ</span>
  </div>
</div>"""

    # S&P500 MA200 추세 카드 (타이밍 신호 4번째 구성 요소)
    if data.get("sp500_trend") is True:
        tr_val_html = "200일선 위"
    elif data.get("sp500_trend") is False:
        tr_val_html = "200일선 아래"
    else:
        tr_val_html = "N/A"
    tr_detail = ""
    # 짧은 라벨 — tr_txt("200일선 위 (상승추세)")는 val_html과 중복돼서 풀 라벨 대신 사용
    short_trend = "상승추세" if data.get("sp500_trend") else "하락추세" if data.get("sp500_trend") is False else "데이터 없음"
    tr_current = f"{tr_val_html} · {short_trend}"
    if data.get("sp500_trend_pct") is not None:
        pct = data["sp500_trend_pct"]
        arrow = "↑" if pct >= 0 else "↓"
        tr_detail = f'<div class="text-xs text-muted">MA200 대비 {arrow}{abs(pct):.1f}%</div>'
        tr_current = f"{tr_val_html} ({arrow}{abs(pct):.1f}%) · {short_trend}"
    trend_card = _macro_card(
        "ma200", "📏", "S&P500 추세", "SPY vs 200-day MA",
        tr_val_html, tr_sig, tr_txt,
        "S&P 500이 200일 이동평균보다 높으면 상승추세(강세장), 낮으면 하락추세(약세장)예요.",
        tr_detail,
        current_value=tr_current,
    )

    # HY Credit Spread 카드 (신규 — 신용 위험 지표)
    hy_val = data.get("hy_spread")
    hy_sig, hy_txt = signal_color("hy_spread", hy_val)
    hy_val_html = f"{hy_val}%p" if hy_val is not None else "N/A"
    hy_card = _macro_card(
        "hy_spread", "🏦", "HY 회사채 스프레드", "ICE BofA US HY OAS",
        hy_val_html, hy_sig, hy_txt,
        "회사채 디폴트 위험을 가격으로 측정해요. 3% 미만은 시장 안정, 7%+ 는 신용 위기 신호예요.",
    )

    # MA50/200 Golden Cross 카드 (신규 — 추세 강도)
    mc_val = data.get("sp500_ma_cross")
    mc_sig, mc_txt = signal_color("ma_cross", mc_val)
    mc_display = {
        "strong_bull": "강한 상승",
        "bull":        "상승",
        "bear":        "약세 전환",
        "strong_bear": "강한 하락",
        None:          "N/A",
    }
    mc_val_html = mc_display.get(mc_val, "N/A")
    cross_card = _macro_card(
        "ma_cross", "⚡", "추세 강도 (50/200)", "SPY 50/200-day MA cross",
        mc_val_html, mc_sig, mc_txt,
        "가격이 50일·200일 이동평균 둘 다 위면 강한 강세장, 둘 다 아래면 강한 약세장이에요.",
    )

    # DXY 트렌드 카드 (신규 — risk-on/off)
    dxt_val_html = "MA200 위" if dxy_above_ma200 is True else "MA200 아래" if dxy_above_ma200 is False else "N/A"
    dxt_detail = ""
    dxt_current = f"{dxt_val_html} · {dxt_txt}"
    if dxy_diff_pct is not None:
        arrow = "↑" if dxy_diff_pct >= 0 else "↓"
        dxt_detail = f'<div class="text-xs text-muted">MA200 대비 {arrow}{abs(dxy_diff_pct):.1f}%</div>'
        dxt_current = f"{dxt_val_html} ({arrow}{abs(dxy_diff_pct):.1f}%) · {dxt_txt}"
    dxy_trend_card = _macro_card(
        "dxy_trend", "🌍", "달러 트렌드", "DXY vs 200-day MA",
        dxt_val_html, dxt_sig, dxt_txt,
        "달러가 200일선 아래면 위험자산(주식·신흥국·원자재)에 우호적이에요. 위면 글로벌 긴축 신호예요.",
        dxt_detail,
        current_value=dxt_current,
    )

    # ── 종합 신호 컴포넌트 배지 — 7개 ──
    # 각 배지는 카드와 동일한 신호 색깔 + 현재값 표시. 클릭 시 해당 컴포넌트 모달.
    fg_score_str = fg_str  # fear_card에서 만든 값
    vix_str = f"{data.get('vix')}" if data.get("vix") is not None else "N/A"
    component_specs = [
        ("fear_greed",  "😨", "F&G",   fg_score_str,                       fg_current,  fg_sig),
        ("vix",         "🌊", "VIX",   vix_str,                            f"{vix_str} · {vx_txt}", vx_sig),
        ("yield_spread","📉", "금리차", ys_main,                            ys_current,  ys_sig),
        ("ma200",       "📏", "추세",   tr_val_html,                        tr_current,  tr_sig),
        ("ma_cross",    "⚡", "강도",   mc_display.get(mc_val, "N/A"),       f"{mc_display.get(mc_val, 'N/A')} · {mc_txt}", mc_sig),
        ("hy_spread",   "🏦", "HY",    hy_val_html,                        f"{hy_val_html} · {hy_txt}", hy_sig),
        ("dxy_trend",   "🌍", "달러",   dxt_val_html,                       dxt_current, dxt_sig),
    ]
    component_badges = "".join(
        f'<button type="button" data-indicator="{key}" data-current="{cur}" data-sig="{sg}" '
        f'class="inline-flex items-center gap-1.5 {_CLS.get(sg, _CLS["neutral"])["text"]} '
        f'{_CLS.get(sg, _CLS["neutral"])["bg"]} {_CLS.get(sg, _CLS["neutral"])["border"]} '
        f'border rounded-full px-3 py-1.5 text-xs hover:opacity-80 transition-opacity cursor-pointer min-h-[32px]">'
        f'<span aria-hidden="true">{emoji}</span><span>{label}</span>'
        f'<span class="font-mono font-bold">{val}</span></button>'
        for key, emoji, label, val, cur, sg in component_specs
    )

    # ── 지수 카드 ──
    idx_html = "\n".join(_index_card(t) for t in data["tickers"])

    # ── 가이드 ──
    guide_html = "\n".join([
        _guide("🎯 타이밍 신호란?", "종합 신호를 구성하는 7개 지표 소개",
            "이 대시보드의 종합 신호는 CNN Fear &amp; Greed(7-component composite)와 Goldman Sachs Bull/Bear Indicator(6-component) "
            "방법론을 참고해 7개 지표로 구성했어요: "
            "① 심리(CNN F&amp;G) ② 변동성(VIX) ③ 경기(10Y-3M 금리차) ④ 시장 추세(S&amp;P500 MA200) "
            "⑤ 추세 강도(50/200 cross) ⑥ 신용(HY 회사채 스프레드) ⑦ 통화(DXY 트렌드). "
            "각 지표를 매수/중립/주의/위험 4단계로 분류하고 합산해서 종합 신호를 만들어요. "
            "학술 연구(AQR, IMF)에 따라 CAPE 같은 밸류에이션 지표는 10~20년 장기 예측에 적합해서 "
            "종합 신호에서 제외하고 참고 지표로만 표시해요."),
        _guide("😨 공포 & 탐욕 지수", "투자자 심리를 0~100으로 표시",
            "0에 가까울수록 사람들이 무서워서 내다 팔고, 100에 가까우면 욕심을 부리며 사고 있는 상태예요. "
            "워렌 버핏은 '남들이 탐욕스러울 때 두려워하고, 두려울 때 탐욕스러워져라'라고 했어요. "
            "25 이하 극도의 공포 구간은 역사적으로 이후 수익률이 높게 나타나는 경향이 있어요."),
        _guide("🌊 VIX (공포 지수)", "시장이 얼마나 출렁일지 예측",
            "다음 30일간 주가 변동을 옵션 시장에서 예측해요. 15 이하면 너무 조용한 시장(과신 주의), "
            "20~30이면 적당한 긴장, 30~40이면 공포 구간이에요. "
            "역설적으로 VIX 30~40 구간은 역발투자 관점에서 좋은 매수 기회인 경우가 많아요."),
        _guide("📉 금리차 (10Y-3M)", "경기침체 조기 경보",
            "미국 10년 국채금리에서 3개월 국채금리를 뺀 값이에요. "
            "이게 0 아래로 뒤집어지면(역전) 1~2년 안에 경기침체가 올 수 있어요. "
            "과거에 8번 역전 중 7번 경기침체가 왔어요."),
        _guide("📏 S&P500 추세 (MA200)", "지금 강세장인지 약세장인지",
            "S&P 500 ETF(SPY)가 200일 이동평균선보다 높으면 상승추세(강세장), 낮으면 하락추세(약세장)예요. "
            "단기 등락이 아닌 큰 흐름을 보여주는 지표로, CNN·OECD 등 주요 복합 지수가 공통으로 포함하는 '모멘텀' 카테고리예요."),
        _guide("⚡ 추세 강도 (50/200 cross)", "추세가 얼마나 강하고 가속 중인지",
            "200일선만 보면 강세장·약세장 이진 판단만 가능해요. 50일선까지 함께 보면 "
            "강한 상승(가격>50선>200선) / 상승(50선 위·200선 아래 또는 그 반대) / 약세 / 강한 하락 4단계로 더 세밀하게 판정할 수 있어요. "
            "50선이 200선을 위로 돌파하는 'Golden Cross'는 강한 상승 전환 신호로 유명해요."),
        _guide("🏦 HY 회사채 스프레드", "신용 위기 조기 경보 (가장 빠른 침체 신호)",
            "투자등급 미만 회사채(정크본드)와 미국채의 금리 차이예요. 회사들이 디폴트 위험을 시장에서 어떻게 평가하는지 보여줘요. "
            "10Y-3M 금리차가 12~24개월 전 침체 신호라면, HY 스프레드는 3~6개월 전 신호로 더 빠르고 정확해요. "
            "역사상 2008년 21.8%, 2020년 3월 11%까지 급등했어요. S&P500과 강한 역상관 관계예요."),
        _guide("🌍 달러 트렌드 (DXY MA200)", "위험자산 환경 판정",
            "달러 지수(DXY)가 200일선 아래면 약달러 추세 = 위험자산(주식·신흥국·원자재) 우호적 환경이에요. "
            "위면 강달러 = 글로벌 유동성 긴축 신호로, 미국 외 주식·금·원자재에 역풍이에요. "
            "달러 절대값이 아닌 추세 방향이 중요해요."),
        _guide("📊 CAPE (Shiller PE)", "주식이 역사적으로 비싼지 확인 (장기 맥락용)",
            "10년 평균 이익 기준으로 주가 수준을 봐요. 역사 평균이 약 17이에요. "
            "38을 넘으면 역사적으로 매우 비싼 수준이에요. 단, 현대 시장은 저금리 시대를 거쳐 구조적으로 높아졌어요. "
            "이 지표는 10~20년 장기 수익률 예측에 유용하지만, 단기 타이밍 신호로는 적합하지 않아요."),
        _guide("📈 S&P500 PER", "지금 당장의 실적 대비 주가 수준 (장기 맥락용)",
            "최근 12개월 실제 이익 기준으로 주가가 얼마나 비싼지 봐요. CAPE보다 더 빠르게 반응해요. "
            "역사 평균은 약 16~17이고, 25 이상이면 고평가 신호예요."),
        _guide("🏦 버핏 지수", "전체 시장의 거품 확인 (장기 맥락용)",
            "시장 시가총액을 GDP로 나눈 값이에요. 워렌 버핏이 즐겨 쓰는 지표예요. "
            "100%가 적정 수준, 150%를 넘으면 고평가 주의, 200%를 넘으면 버블 경고예요. "
            "※ 이 대시보드는 Wilshire 5000 지수 기반 근사값이에요."),
        _guide("💵 달러 강세 지수 (DXY)", "달러 강도가 투자에 미치는 영향",
            "달러가 강하면 원화가 약해지고 외국인이 한국 주식을 팔기도 해요. "
            "금·원유 가격도 달러와 반대로 움직이는 경우가 많아요. 100이 기준선이에요."),
        _guide("🇰🇷 원달러 환율", "원화 가치와 한국 시장 영향",
            "환율이 오르면 원화 가치가 떨어진 거예요. 1,350원 이상이면 외국인 자금 이탈 우려가 커져요. "
            "해외 주식 투자 시 환율이 오르면 달러 자산 가치가 원화 기준으로 올라가 유리하기도 해요."),
        _guide("📈 RSI", "지금 너무 오른 건지 너무 떨어진 건지",
            "최근 14일간 오른 폭과 떨어진 폭을 비교해요. 30 이하면 너무 많이 떨어진 상태(반등 가능성), "
            "70 이상이면 너무 오른 상태(조정 가능성)예요. 단, RSI만 보고 바로 매매하는 건 위험해요."),
        _guide("📏 MA200 (200일 이동평균)", "개별 종목의 추세 확인",
            "최근 200일 평균 주가예요. 현재가가 이 선 위면 상승추세, 아래면 하락추세로 봐요. "
            "후행 지표라 하락이 많이 진행된 뒤에야 신호가 나와요. 다른 지표와 함께 참고하세요."),
        _guide("📍 52주 고저 위치", "1년 기준으로 지금 가격이 저렴한지",
            "지난 1년 최저가(0%)와 최고가(100%) 사이에서 현재가 위치예요. "
            "30% 이하면 저점 근처(싸게 살 가능성), 80% 이상이면 고점 근처(비싸게 사는 위험)예요."),
    ])

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>투자 지표 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
{_STYLE}
</head>
<body class="bg-base text-fg min-h-screen">
<div class="max-w-6xl mx-auto px-3 sm:px-4 py-5 sm:py-8">

  <!-- 헤더 — 모바일: 세로 스택, 데스크탑: 좌우 정렬 -->
  <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-6 sm:mb-8">
    <div class="min-w-0">
      <h1 class="text-xl sm:text-2xl font-bold text-fg"><span aria-hidden="true">📊</span> 투자 지표 대시보드</h1>
      <p class="text-xs sm:text-sm text-muted mt-1">주식 초보자를 위한 투자 타이밍 신호등</p>
    </div>
    <div class="flex items-center gap-2 flex-wrap sm:flex-col sm:items-end sm:gap-0 sm:text-right shrink-0">
      <div class="hidden sm:block text-xs text-muted mb-0.5">마지막 업데이트</div>
      <div class="inline-flex items-center gap-1.5 bg-frame border border-frame rounded-full px-2.5 py-1">
        <span class="w-1.5 h-1.5 rounded-full bg-good shrink-0" aria-hidden="true"></span>
        <span class="text-xs sm:text-sm font-mono text-fg">{now}</span>
      </div>
      {refresh_block}
    </div>
  </div>

  <!-- 종합 신호등 (클릭 시 종합 모달, 배지 클릭 시 해당 컴포넌트 모달) -->
  <div class="bg-surface border border-frame rounded-2xl p-4 sm:p-6 mb-6 sm:mb-8 cursor-pointer hover:border-fg/30 transition-colors"
       data-indicator="overall"
       data-current="긍정 {good_n} · 중립 {neutral_n} · 주의 {warn_n} · 위험 {bad_n} → {ov_label}"
       data-sig="{ov_key}"
       role="button" tabindex="0" aria-label="종합 신호 판단 근거 보기">
    <div class="flex items-center gap-3 sm:gap-5 flex-wrap">
      <div class="w-12 h-12 sm:w-16 sm:h-16 rounded-full flex items-center justify-center shrink-0"
           style="background:{ov_dot}1a; border:2px solid {ov_dot}">
        <div class="w-5 h-5 sm:w-6 sm:h-6 rounded-full" style="background:{ov_dot}; box-shadow:0 0 14px {ov_dot}99"></div>
      </div>
      <div class="flex-1 min-w-0">
        <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-1 flex items-center gap-1.5">
          <span>종합 투자 신호 <span class="hidden sm:inline">(7개 타이밍 지표 기반)</span></span>
          <span class="text-fg/40" aria-hidden="true">ⓘ</span>
        </div>
        <div class="text-lg sm:text-xl font-bold {ov_c['text']}">{ov_label}</div>
        <div class="text-xs sm:text-sm text-muted mt-1 leading-relaxed">{ov_comment}</div>
      </div>
      <div class="grid grid-cols-4 gap-2 sm:gap-5 text-center shrink-0 w-full sm:w-auto">
        <div><div class="text-good font-bold text-lg sm:text-xl">{good_n}</div><div class="text-muted text-[10px] sm:text-xs mt-0.5">긍정</div></div>
        <div><div class="text-muted font-bold text-lg sm:text-xl">{neutral_n}</div><div class="text-muted text-[10px] sm:text-xs mt-0.5">중립</div></div>
        <div><div class="text-warn font-bold text-lg sm:text-xl">{warn_n}</div><div class="text-muted text-[10px] sm:text-xs mt-0.5">주의</div></div>
        <div><div class="text-danger font-bold text-lg sm:text-xl">{bad_n}</div><div class="text-muted text-[10px] sm:text-xs mt-0.5">위험</div></div>
      </div>
    </div>
    <!-- 7개 컴포넌트 배지 — 각 클릭 시 해당 컴포넌트 모달 -->
    <div class="mt-4 sm:mt-5 pt-4 sm:pt-5 border-t border-frame">
      <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-3">판단 근거 — 7개 컴포넌트</div>
      <div class="flex flex-wrap gap-2">
        {component_badges}
      </div>
      <div class="text-[11px] sm:text-xs text-muted mt-3 leading-relaxed">계산: 각 매수 +1·중립 0·주의 -1·위험 -2 합산 → 임계값 비교. 카드 빈 공간 클릭 시 방법론 상세.</div>
    </div>
  </div>

  <!-- 타이밍 신호 (종합 신호 구성 7개 지표) -->
  <h2 class="text-xs font-semibold text-muted uppercase tracking-widest mb-3"><span aria-hidden="true">🎯</span> 타이밍 신호 <span class="normal-case font-normal opacity-60 hidden sm:inline">(종합 신호 구성 7개 지표 — CNN F&amp;G·Goldman 모델 참고)</span></h2>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
    {fear_card}
    {vix_card}
    {ys_html}
    {trend_card}
    {hy_card}
    {cross_card}
    {dxy_trend_card}
  </div>

  <!-- 밸류에이션 & 참고 지표 -->
  <div class="bg-frame/30 border border-frame/50 rounded-xl px-3 sm:px-4 py-3 mb-3 flex items-start gap-2">
    <span class="text-sm shrink-0" aria-hidden="true">💡</span>
    <p class="text-xs text-muted leading-relaxed">아래 지표는 <strong class="text-fg">장기 투자 맥락</strong>을 보여줘요. 주식이 역사적으로 비싼지 싼지 가늠하는 용도예요. 오늘 바로 사고팔 타이밍을 알려주는 신호가 아니라서 종합 신호 계산에는 포함하지 않아요.</p>
  </div>
  <h2 class="text-xs font-semibold text-muted uppercase tracking-widest mb-3"><span aria-hidden="true">💰</span> 밸류에이션 &amp; 참고 지표 <span class="normal-case font-normal opacity-60">(장기 맥락용)</span></h2>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 mb-6 sm:mb-8">
    {cape_card}
    {pe_card}
    {buff_card}
    {dxy_card}
    {kr_card}
  </div>

  <!-- 지수 & ETF -->
  <h2 class="text-xs font-semibold text-muted uppercase tracking-widest mb-3"><span aria-hidden="true">📈</span> 지수 &amp; ETF 현황</h2>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 mb-6 sm:mb-8">
    {idx_html}
  </div>

  <!-- 초보자 가이드 -->
  <h2 class="text-xs font-semibold text-muted uppercase tracking-widest mb-3"><span aria-hidden="true">📖</span> 초보자 용어 가이드</h2>
  <div class="flex flex-col gap-2 mb-6 sm:mb-8">
    {guide_html}
  </div>

  <!-- 푸터 -->
  <div class="text-center text-xs text-muted border-t border-frame pt-6 leading-relaxed">
    <p>데이터 출처: CNN · multpl.com · Yahoo Finance · US Treasury</p>
    <p class="mt-1">이 대시보드는 참고용이며 투자 권유가 아닙니다. 투자 판단은 본인 책임이에요.</p>
  </div>

</div>

<!-- 지표 상세 모달 -->
<div id="indicator-modal" class="fixed inset-0 bg-black/80 z-50 hidden items-center justify-center p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="modal-title">
  <div class="bg-surface border border-frame rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl" id="modal-card">
    <div class="sticky top-0 bg-surface flex items-center justify-between p-4 sm:p-5 border-b border-frame z-10">
      <h2 id="modal-title" class="text-base sm:text-xl font-bold text-fg pr-2 min-w-0"></h2>
      <button id="modal-close" type="button" class="text-muted hover:text-fg text-2xl leading-none w-10 h-10 flex items-center justify-center rounded-full hover:bg-frame transition-colors shrink-0" aria-label="닫기">×</button>
    </div>
    <div class="p-4 sm:p-5 flex flex-col gap-4 sm:gap-5">
      <div id="modal-current-wrap" class="bg-frame/30 rounded-xl p-3 sm:p-4 border border-frame">
        <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-1">현재 수치</div>
        <div id="modal-current" class="text-base sm:text-xl font-bold break-words"></div>
      </div>
      <div>
        <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-2">이 지표가 뭔가요?</div>
        <p id="modal-description" class="text-sm text-fg leading-relaxed"></p>
      </div>
      <div>
        <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-2">어떻게 읽나요?</div>
        <table class="w-full text-sm">
          <tbody id="modal-thresholds"></tbody>
        </table>
      </div>
      <div>
        <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-2">⚠️ 주의사항</div>
        <p id="modal-caveat" class="text-sm text-muted leading-relaxed"></p>
      </div>
      <div class="pt-3 border-t border-frame">
        <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-2">검증 / 원본 데이터</div>
        <a id="modal-source" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2 text-sm text-good hover:underline break-all min-h-[36px]">
          <span id="modal-source-label"></span>
          <span class="text-xs shrink-0" aria-hidden="true">↗</span>
        </a>
      </div>
    </div>
  </div>
</div>

<!-- 토스트 -->
<div id="toast" class="fixed bottom-4 right-4 z-50 hidden bg-surface border border-danger/40 text-danger text-sm rounded-lg px-4 py-3 shadow-2xl max-w-sm"></div>

<script>
const INDICATOR_INFO = {indicator_info_json};
const SIG_TEXT = {{good: 'text-good', warn: 'text-warn', bad: 'text-danger', neutral: 'text-muted'}};
const modal = document.getElementById('indicator-modal');

function openModal(key, currentText, sigKey) {{
  const info = INDICATOR_INFO[key];
  if (!info) return;
  document.getElementById('modal-title').textContent = info.title;
  const cur = document.getElementById('modal-current');
  cur.textContent = currentText || '데이터 없음';
  cur.className = 'text-base sm:text-xl font-bold break-words ' + (SIG_TEXT[sigKey] || 'text-muted');
  document.getElementById('modal-description').textContent = info.description;
  document.getElementById('modal-caveat').textContent = info.caveat;
  const src = document.getElementById('modal-source');
  src.href = info.source_url;
  document.getElementById('modal-source-label').textContent = info.source_label;
  const tbody = document.getElementById('modal-thresholds');
  tbody.innerHTML = info.thresholds.map(([range, label, sig]) => {{
    const cls = SIG_TEXT[sig] || 'text-muted';
    return `<tr class="border-b border-frame last:border-0">
      <td class="font-mono text-xs py-2 pr-3 whitespace-nowrap ${{cls}}">${{range}}</td>
      <td class="text-sm py-2 ${{cls}}">${{label}}</td>
    </tr>`;
  }}).join('');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  document.body.style.overflow = 'hidden';
  document.getElementById('modal-close').focus();
}}

function closeModal() {{
  modal.classList.add('hidden');
  modal.classList.remove('flex');
  document.body.style.overflow = '';
}}

// 카드 클릭 이벤트 위임
document.addEventListener('click', (e) => {{
  const el = e.target.closest('[data-indicator]');
  if (el) {{
    e.preventDefault();
    openModal(el.dataset.indicator, el.dataset.current || '', el.dataset.sig || 'neutral');
  }}
}});

// 키보드 접근성: Enter/Space로 카드 열기
document.addEventListener('keydown', (e) => {{
  if (e.key === 'Escape' && !modal.classList.contains('hidden')) {{
    closeModal();
    return;
  }}
  const el = document.activeElement;
  if ((e.key === 'Enter' || e.key === ' ') && el?.dataset?.indicator) {{
    e.preventDefault();
    openModal(el.dataset.indicator, el.dataset.current || '', el.dataset.sig || 'neutral');
  }}
}});

// 오버레이 클릭 → 닫기 (카드 내부 클릭은 제외)
modal.addEventListener('click', (e) => {{
  if (e.target === modal) closeModal();
}});
document.getElementById('modal-close').addEventListener('click', closeModal);

// 토스트
function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  setTimeout(() => t.classList.add('hidden'), 4000);
}}

// 새로고침 버튼 (serve_mode에서만 존재)
const refreshBtn = document.getElementById('refresh-btn');
if (refreshBtn) {{
  refreshBtn.addEventListener('click', async () => {{
    refreshBtn.disabled = true;
    document.getElementById('refresh-icon').textContent = '⏳';
    document.getElementById('refresh-text').textContent = '갱신 중…';
    try {{
      const res = await fetch('/api/refresh', {{method: 'POST'}});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const json = await res.json();
      if (!json.ok) throw new Error(json.error || '알 수 없는 오류');
      location.reload();
    }} catch (err) {{
      refreshBtn.disabled = false;
      document.getElementById('refresh-icon').textContent = '🔄';
      document.getElementById('refresh-text').textContent = '새로고침';
      showToast('새로고침 실패: ' + err.message);
    }}
  }});
}}
</script>

</body>
</html>"""


# ── Data Collection ───────────────────────────────────────────────────────────

def collect_data():
    """모든 지표 데이터를 병렬로 수집하여 dict로 반환. 서버·정적 모드에서 공용."""
    print("📡 데이터 수집 중 (병렬 fetch)...")
    t0 = datetime.now()

    watchlist = [
        ("SPY",   "S&P 500 ETF"),
        ("QQQ",   "나스닥 100 ETF"),
        ("^KS11", "KOSPI"),
        ("^KQ11", "KOSDAQ"),
        ("TLT",   "미국 장기채 ETF"),
        ("GLD",   "금 ETF"),
    ]

    macro_jobs = [
        ("fear_greed",   "Fear & Greed",  fetch_fear_greed),
        ("cape",         "CAPE",           fetch_cape),
        ("sp500pe",      "S&P500 PER",     fetch_sp500_pe),
        ("buffett",      "버핏 지수",       fetch_buffett_indicator),
        ("vix",          "VIX",            fetch_vix),
        ("dxy",          "DXY (+추세)",     fetch_dxy),
        ("usdkrw",       "원달러 환율",     fetch_usdkrw),
        ("yield_spread", "금리차",          fetch_yield_spread),
        ("hy_spread",    "HY 회사채 스프레드", fetch_hy_spread),
    ]

    macro_data = {}
    tickers = []
    with ThreadPoolExecutor(max_workers=14) as ex:
        macro_futs = {key: (label, ex.submit(fn)) for key, label, fn in macro_jobs}
        ticker_futs = [(t, n, ex.submit(analyze_ticker, t, n)) for t, n in watchlist]

        for key, (label, fut) in macro_futs.items():
            val = fut.result()
            macro_data[key] = val
            ok = val is not None and val != {"score": None, "rating": "N/A"}
            print(f"  {'✓' if ok else '⚠️ '} {label}")

        for t, n, fut in ticker_futs:
            res = fut.result()
            tickers.append(res)
            ok = res["price_str"] != "N/A"
            print(f"  {'✓' if ok else '⚠️ '} {n} ({t})")

    spy_data = next((t for t in tickers if t["ticker"] == "SPY"), None)
    elapsed = (datetime.now() - t0).total_seconds()
    print(f"  ⏱  총 {elapsed:.1f}초")

    return {
        **macro_data,
        "tickers": tickers,
        "sp500_trend": spy_data["ma200_above"] if spy_data else None,
        "sp500_trend_pct": spy_data["ma200_diff_pct"] if spy_data else None,
        "sp500_ma_cross": spy_data.get("ma_cross") if spy_data else None,
    }


# ── HTTP Server ───────────────────────────────────────────────────────────────

_refresh_lock = threading.Lock()
_html_cache = ""  # 마지막 빌드된 HTML (서버 모드에서 GET / 응답에 사용)


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        # 기본 access log 억제 (필요 시 print로 재활성)
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = _html_cache.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/api/refresh":
            self.send_response(404)
            self.end_headers()
            return
        if not _refresh_lock.acquire(blocking=False):
            self._send_json(429, {"ok": False, "error": "이미 새로고침 진행 중"})
            return
        try:
            global _html_cache
            data = collect_data()
            _html_cache = build_html(data, serve_mode=True)
            self._send_json(200, {"ok": True})
        except Exception as e:
            print(f"⚠️  /api/refresh 실패: {e}")
            self._send_json(500, {"ok": False, "error": str(e)})
        finally:
            _refresh_lock.release()

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(port=8765):
    """로컬 HTTP 서버 시작. 포트 충돌 시 +1, +2 순으로 자동 재시도."""
    global _html_cache

    data = collect_data()
    _html_cache = build_html(data, serve_mode=True)

    server = None
    chosen_port = None
    for p in range(port, port + 3):
        try:
            server = http.server.HTTPServer(("127.0.0.1", p), DashboardHandler)
            chosen_port = p
            break
        except OSError as e:
            if e.errno in (socket.errno.EADDRINUSE, 48):  # 48 = macOS EADDRINUSE
                print(f"  ⚠️  포트 {p} 사용 중, 다음 포트 시도")
                continue
            raise

    if server is None:
        print(f"\n❌ 포트 {port}~{port + 2} 모두 사용 중. --port 옵션으로 다른 포트 지정하세요.")
        return

    url = f"http://localhost:{chosen_port}/"
    print(f"\n✅ 서버 시작: {url}")
    print(f"   브라우저에서 열리지 않으면 위 주소를 직접 열어 주세요.")
    print(f"   종료: Ctrl+C")
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 서버 종료")
        server.shutdown()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """기본은 서버 모드, --static 시 정적 HTML 파일 생성."""
    parser = argparse.ArgumentParser(description="투자 지표 대시보드")
    parser.add_argument("--static", action="store_true",
                        help="정적 HTML 파일 생성 모드 (서버 없이)")
    parser.add_argument("--out", type=str, default=None,
                        help="HTML 출력 경로 (--static 모드, 기본: ./index.html)")
    parser.add_argument("--no-open", action="store_true",
                        help="브라우저 자동 오픈 비활성 (CI용)")
    parser.add_argument("--port", type=int, default=8765,
                        help="서버 포트 (기본 8765)")
    args = parser.parse_args()

    if args.static:
        data = collect_data()
        html = build_html(data, serve_mode=False)
        # B1: 기본 출력은 index.html (Pages 루트 진입 호환)
        if args.out:
            out = os.path.abspath(args.out)
        else:
            out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✅ 대시보드 생성 완료: {out}")
        if not args.no_open and not os.environ.get("CI"):
            webbrowser.open(f"file://{out}")
    else:
        serve(port=args.port)


if __name__ == "__main__":
    main()
