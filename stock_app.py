"""
주식 대시보드 - 개인정보 없는 버전
=====================================
각자 본인 종목/매수가/보유주수를 직접 입력
streamlit run stock_app.py
"""

import os
import time
import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

KOSPI200 = {
    "005930": "삼성전자",        "000660": "SK하이닉스",
    "005380": "현대차",          "000270": "기아",
    "068270": "셀트리온",        "005490": "POSCO홀딩스",
    "035420": "NAVER",           "051910": "LG화학",
    "006400": "삼성SDI",         "028260": "삼성물산",
    "012330": "현대모비스",      "066570": "LG전자",
    "003550": "LG",              "034730": "SK",
    "017670": "SK텔레콤",        "030200": "KT",
    "086790": "하나금융지주",    "105560": "KB금융",
    "055550": "신한지주",        "316140": "우리금융지주",
    "018260": "삼성에스디에스",  "009150": "삼성전기",
    "010950": "S-Oil",           "011200": "HMM",
    "096770": "SK이노베이션",    "003670": "포스코퓨처엠",
    "207940": "삼성바이오로직스","035720": "카카오",
    "259960": "크래프톤",        "323410": "카카오뱅크",
    "352820": "하이브",          "041510": "에스엠",
    "035900": "JYP엔터",         "010130": "고려아연",
    "009830": "한화솔루션",      "000100": "유한양행",
    "128940": "한미약품",        "010120": "LS ELECTRIC",
    "042660": "한화오션",        "047810": "한국항공우주",
    "012450": "한화에어로스페이스","064350": "현대로템",
    "267250": "HD현대",          "329180": "HD현대중공업",
    "009540": "HD한국조선해양",  "166090": "하나머티리얼즈",
    "036540": "SFA반도체",       "219130": "컨텍",
    "047050": "포스코인터내셔널","032830": "삼성생명",
    "024110": "기업은행",        "000880": "한화",
}

SHORT_PERIOD = 5
LONG_PERIOD  = 20
VOLUME_SURGE = 2.0

st.set_page_config(page_title="📈 주식 대시보드", page_icon="📈", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #060c1a; color: #e2e8f0; }
    h1,h2,h3 { color: #ffffff; }
    .buy  { color: #00ff88; font-weight: 800; }
    .sell { color: #ef4444; font-weight: 800; }
    .hold { color: #94a3b8; }
    .pos  { color: #00ff88; font-weight: 700; }
    .neg  { color: #ef4444; font-weight: 700; }
    div[data-testid="stMetricValue"] { color: #4a9eff; font-weight: 800; }
    .stButton > button {
        background: linear-gradient(135deg, #4a9eff, #0066ff);
        color: white; border: none; border-radius: 8px; font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def get_yahoo_prices(ticker_code, days=30):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_code}.KS?interval=1d&range=60d"
        res = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        result = res.json()["chart"]["result"][0]
        df = pd.DataFrame({
            "date":   [datetime.fromtimestamp(t).strftime("%Y%m%d") for t in result["timestamp"]],
            "close":  [int(c) if c else None for c in result["indicators"]["quote"][0]["close"]],
            "volume": [int(v) if v else 0   for v in result["indicators"]["quote"][0]["volume"]],
        }).dropna().tail(days)
        return df
    except Exception:
        return pd.DataFrame()

def get_yahoo_current_price(ticker_code):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_code}.KS?interval=1d&range=2d"
        res = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        meta = res.json()["chart"]["result"][0]["meta"]
        return int(meta.get("regularMarketPrice", 0))
    except Exception:
        return 0

def check_cross_signal(df):
    if len(df) < LONG_PERIOD + 1:
        return "HOLD"
    df = df.copy()
    df["ma_short"] = df["close"].rolling(SHORT_PERIOD).mean()
    df["ma_long"]  = df["close"].rolling(LONG_PERIOD).mean()
    today, yesterday = df.iloc[-1], df.iloc[-2]
    if yesterday["ma_short"] <= yesterday["ma_long"] and today["ma_short"] > today["ma_long"]:
        return "BUY"
    if yesterday["ma_short"] >= yesterday["ma_long"] and today["ma_short"] < today["ma_long"]:
        return "SELL"
    return "HOLD"

def check_volume_surge(df):
    if len(df) < 6:
        return False
    return df["volume"].iloc[-1] >= df["volume"].iloc[:-1].mean() * VOLUME_SURGE

def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return now.replace(hour=9, minute=0, second=0) <= now <= now.replace(hour=15, minute=30, second=0)


st.markdown("# 📈 주식 대시보드")
market_status = "🟢 장 중" if is_market_open() else "🔴 장 마감"
st.markdown(f"**시장:** {market_status} &nbsp;|&nbsp; 📡 Yahoo Finance (15분 지연)")
st.markdown("---")

tab1, tab2 = st.tabs(["💼 내 포트폴리오", "📡 종목 스캐너"])

with tab1:
    st.markdown("### 💼 내 보유 종목")
    st.info("📌 본인 종목을 직접 입력하세요. 입력한 정보는 이 브라우저에서만 보이고 서버에 저장되지 않아요.")

    if "my_stocks" not in st.session_state:
        st.session_state.my_stocks = []

    with st.expander("➕ 종목 추가하기", expanded=len(st.session_state.my_stocks) == 0):
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
        with c1:
            input_ticker = st.text_input("종목코드", placeholder="예: 005930", key="input_ticker")
        with c2:
            input_buy = st.number_input("매수가 (원)", min_value=0, value=0, key="input_buy")
        with c3:
            input_shares = st.number_input("보유수량 (주)", min_value=0, value=0, key="input_shares")
        with c4:
            st.markdown("<br>", unsafe_allow_html=True)
            add_btn = st.button("추가", key="add_stock")

        if add_btn:
            if input_ticker.strip() == "":
                st.error("종목코드를 입력해주세요")
            elif input_buy <= 0:
                st.error("매수가를 입력해주세요")
            elif input_shares <= 0:
                st.error("보유수량을 입력해주세요")
            else:
                ticker = input_ticker.strip().zfill(6)
                name = KOSPI200.get(ticker, ticker)
                existing = [s for s in st.session_state.my_stocks if s["ticker"] == ticker]
                if existing:
                    st.warning(f"{name} 은 이미 추가되어 있어요!")
                else:
                    st.session_state.my_stocks.append({
                        "ticker": ticker, "name": name,
                        "buy_price": input_buy, "shares": input_shares,
                    })
                    st.success(f"✅ {name} 추가됐어요!")
                    st.rerun()

    if st.session_state.my_stocks:
        cols = st.columns(len(st.session_state.my_stocks))
        for i, stock in enumerate(st.session_state.my_stocks):
            with cols[i]:
                if st.button(f"❌ {stock['name']} 삭제", key=f"del_{i}"):
                    st.session_state.my_stocks.pop(i)
                    st.rerun()

    st.markdown("---")

    if not st.session_state.my_stocks:
        st.markdown("<div style='text-align:center;padding:40px;color:#64748b'>위에서 종목을 추가해주세요 👆</div>", unsafe_allow_html=True)
    else:
        col_t, col_r = st.columns([5, 1])
        with col_r:
            if st.button("🔄 새로고침", key="r1"):
                st.cache_data.clear()

        with st.spinner("시세 조회 중..."):
            total_invested = 0
            total_current  = 0
            rows = []

            for stock in st.session_state.my_stocks:
                try:
                    df      = get_yahoo_prices(stock["ticker"])
                    current = get_yahoo_current_price(stock["ticker"])
                    if current == 0 and not df.empty:
                        current = int(df["close"].iloc[-1])
                    signal    = check_cross_signal(df) if not df.empty else "HOLD"
                    vol_surge = check_volume_surge(df)  if not df.empty else False
                    ma5       = round(df["close"].rolling(SHORT_PERIOD).mean().iloc[-1]) if not df.empty else 0
                    ma20      = round(df["close"].rolling(LONG_PERIOD).mean().iloc[-1])  if not df.empty else 0
                    pnl_pct   = (current - stock["buy_price"]) / stock["buy_price"] * 100 if stock["buy_price"] else 0
                    pnl_amt   = (current - stock["buy_price"]) * stock["shares"]
                    total_invested += stock["buy_price"] * stock["shares"]
                    total_current  += current * stock["shares"]
                    rows.append({
                        "종목명": stock["name"], "현재가": current,
                        "매수가": stock["buy_price"], "보유주수": stock["shares"],
                        "MA5": ma5, "MA20": ma20,
                        "수익률": pnl_pct, "손익": pnl_amt,
                        "signal": signal, "vol_surge": vol_surge,
                    })
                except Exception:
                    rows.append({
                        "종목명": stock["name"], "현재가": 0,
                        "매수가": stock["buy_price"], "보유주수": stock["shares"],
                        "MA5": 0, "MA20": 0, "수익률": 0, "손익": 0,
                        "signal": "오류", "vol_surge": False,
                    })

        total_pnl     = total_current - total_invested
        total_pnl_pct = total_pnl / total_invested * 100 if total_invested else 0
        pnl_sign      = "+" if total_pnl >= 0 else ""
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 총 투자금액", f"{total_invested:,}원")
        c2.metric("📊 평가금액",   f"{total_current:,}원")
        c3.metric("📈 총 손익",    f"{pnl_sign}{total_pnl:,.0f}원", f"{pnl_sign}{total_pnl_pct:.2f}%")
        st.markdown("---")

        for row in rows:
            signal    = row["signal"]
            vol_surge = row["vol_surge"]
            pnl_pct   = row["수익률"]
            pnl_amt   = row["손익"]
            sign      = "+" if pnl_pct >= 0 else ""
            color     = "pos" if pnl_pct >= 0 else "neg"
            if signal == "BUY":
                sig_label = "🟢 매수신호" + (" 📊거래량급증!" if vol_surge else "")
                sig_color = "buy"
            elif signal == "SELL":
                sig_label = "🔴 매도신호"
                sig_color = "sell"
            else:
                sig_label = "⚪ 관망"
                sig_color = "hold"
            c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 2, 3])
            c1.markdown(f"**{row['종목명']}**  \n<small style='color:#64748b'>{row['보유주수']}주 · 매수가 {row['매수가']:,}원</small>", unsafe_allow_html=True)
            c2.markdown(f"**{row['현재가']:,}원**")
            c3.markdown(f"<span class='{color}'>{sign}{pnl_pct:.2f}%</span>", unsafe_allow_html=True)
            c4.markdown(f"<span class='{color}'>{sign}{pnl_amt:,.0f}원</span>", unsafe_allow_html=True)
            c5.markdown(f"MA5: {row['MA5']:,}")
            c6.markdown(f"<span class='{sig_color}'>{sig_label}</span>", unsafe_allow_html=True)
            st.markdown("---")

        st.caption("📡 Yahoo Finance (15분 지연) · 입력 정보는 서버에 저장되지 않아요")

with tab2:
    st.markdown("### 📡 코스피200 골든크로스 스캐너")
    st.markdown("골든크로스 + 거래량 급증 종목 자동 탐색 · API 키 불필요")

    if st.button("🔍 스캔 시작", key="scan"):
        buy_signals, sell_signals = [], []
        prog  = st.progress(0, text="스캔 준비 중...")
        total = len(KOSPI200)
        for i, (ticker, name) in enumerate(KOSPI200.items()):
            prog.progress((i + 1) / total, text=f"스캔 중... ({i+1}/{total}) {name}")
            try:
                df = get_yahoo_prices(ticker)
                if df.empty:
                    continue
                signal    = check_cross_signal(df)
                vol_surge = check_volume_surge(df)
                current   = int(df["close"].iloc[-1])
                ma5       = round(df["close"].rolling(SHORT_PERIOD).mean().iloc[-1])
                ma20      = round(df["close"].rolling(LONG_PERIOD).mean().iloc[-1])
                if signal == "BUY":
                    buy_signals.append({
                        "강도": "🔥 강력매수" if vol_surge else "🟢 매수",
                        "종목명": name, "현재가": current,
                        "MA5": ma5, "MA20": ma20,
                        "거래량급증": "🔥 YES" if vol_surge else "—",
                    })
                elif signal == "SELL":
                    sell_signals.append({"종목명": name, "현재가": current, "MA5": ma5, "MA20": ma20})
                time.sleep(0.2)
            except Exception:
                continue
        prog.empty()
        st.session_state.scan_buy  = buy_signals
        st.session_state.scan_sell = sell_signals
        st.session_state.scan_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    if "scan_buy" in st.session_state:
        st.markdown(f"**스캔 시각:** {st.session_state.scan_time}")
        st.markdown("---")
        buy_list  = st.session_state.scan_buy
        sell_list = st.session_state.scan_sell
        st.markdown(f"#### 🟢 매수 신호 — {len(buy_list)}개")
        if buy_list:
            df_buy = pd.DataFrame(sorted(buy_list, key=lambda x: x["거래량급증"] == "🔥 YES", reverse=True))
            df_buy["현재가"] = df_buy["현재가"].apply(lambda x: f"{x:,}원")
            df_buy["MA5"]   = df_buy["MA5"].apply(lambda x: f"{x:,}")
            df_buy["MA20"]  = df_buy["MA20"].apply(lambda x: f"{x:,}")
            st.dataframe(df_buy, use_container_width=True, hide_index=True)
        else:
            st.info("현재 매수 신호 종목이 없어요")
        st.markdown(f"#### 🔴 매도 신호 — {len(sell_list)}개")
        if sell_list:
            df_sell = pd.DataFrame(sell_list)
            df_sell["현재가"] = df_sell["현재가"].apply(lambda x: f"{x:,}원")
            df_sell["MA5"]   = df_sell["MA5"].apply(lambda x: f"{x:,}")
            df_sell["MA20"]  = df_sell["MA20"].apply(lambda x: f"{x:,}")
            st.dataframe(df_sell, use_container_width=True, hide_index=True)
        else:
            st.info("현재 매도 신호 종목이 없어요")
        st.caption("⚠️ 스캔 결과는 참고용입니다. 투자 결정은 본인이 판단하세요.")
