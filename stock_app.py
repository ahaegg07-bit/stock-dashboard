"""
주식 대시보드 - API 키 없이도 시세조회 가능
=============================================
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

MY_STOCKS = {
    "005930": "삼성전자",
    "010120": "LS ELECTRIC",
    "166090": "하나머티리얼즈",
    "036540": "SFA반도체",
    "219130": "컨텍",
}

MY_BUY_PRICE = {
    "005930": 186000,
    "010120": 239500,
    "166090": 71850,
    "036540": 9467,
    "219130": 22680,
}

MY_SHARES = {
    "005930": 11,
    "010120": 5,
    "166090": 18,
    "036540": 45,
    "219130": 25,
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
        ticker = ticker_code + ".KS"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=60d"
        res = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        data = res.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes  = result["indicators"]["quote"][0]["close"]
        volumes = result["indicators"]["quote"][0]["volume"]
        df = pd.DataFrame({
            "date":   [datetime.fromtimestamp(t).strftime("%Y%m%d") for t in timestamps],
            "close":  [int(c) if c else None for c in closes],
            "volume": [int(v) if v else 0 for v in volumes],
        }).dropna().tail(days)
        return df
    except Exception:
        return pd.DataFrame()

def get_yahoo_current_price(ticker_code):
    try:
        ticker = ticker_code + ".KS"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=2d"
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

def get_base_url(is_mock):
    return ("https://openapivts.koreainvestment.com:29443" if is_mock
            else "https://openapi.koreainvestment.com:9443")

def get_access_token(app_key, app_secret, is_mock):
    url = f"{get_base_url(is_mock)}/oauth2/tokenP"
    res = requests.post(url, json={
        "grant_type": "client_credentials",
        "appkey": app_key, "appsecret": app_secret,
    }, timeout=10)
    res.raise_for_status()
    return res.json().get("access_token")

def get_headers(app_key, app_secret, token, tr_id):
    return {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key, "appsecret": app_secret,
        "tr_id": tr_id, "custtype": "P",
    }

def get_balance(app_key, app_secret, token, is_mock, account_no):
    url = f"{get_base_url(is_mock)}/uapi/domestic-stock/v1/trading/inquire-balance"
    tr_id = "VTTC8434R" if is_mock else "TTTC8434R"
    headers = get_headers(app_key, app_secret, token, tr_id)
    acc = account_no.split("-")
    params = {
        "CANO": acc[0], "ACNT_PRDT_CD": acc[1],
        "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02",
        "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01",
        "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
    }
    res = requests.get(url, headers=headers, params=params, timeout=10)
    res.raise_for_status()
    result = res.json()
    return {
        "cash": int(result["output2"][0]["dnca_tot_amt"]),
        "stocks": result["output1"],
    }

def get_holding_qty(balance, ticker):
    for s in balance["stocks"]:
        if s["pdno"] == ticker:
            return int(s["hldg_qty"])
    return 0

def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return now.replace(hour=9, minute=0, second=0) <= now <= now.replace(hour=15, minute=30, second=0)

with st.sidebar:
    st.markdown("## ⚙️ 설정")
    st.markdown("#### 📊 시세 조회")
    st.success("✅ API 키 없이 사용 가능!")
    st.markdown("---")
    st.markdown("#### 🤖 자동매매 (선택)")
    st.caption("자동매매 기능은 KIS API 키 필요")
    app_key    = st.text_input("APP KEY",    value=os.getenv("APP_KEY", ""),    type="password")
    app_secret = st.text_input("APP SECRET", value=os.getenv("APP_SECRET", ""), type="password")
    account_no = st.text_input("계좌번호",   value=os.getenv("ACCOUNT_NO", ""), placeholder="50123456-01")
    is_mock    = st.toggle("모의투자 모드", value=True)
    mode_label = "🟡 모의투자" if is_mock else "🔴 실전투자"
    st.info(mode_label)

api_ready = bool(app_key and app_secret and account_no)

if api_ready:
    if "token" not in st.session_state or st.session_state.get("is_mock") != is_mock:
        try:
            st.session_state.token   = get_access_token(app_key, app_secret, is_mock)
            st.session_state.is_mock = is_mock
        except Exception as e:
            st.sidebar.error(f"KIS 연결 실패: {e}")
            api_ready = False

st.markdown("# 📈 주식 대시보드")
market_status = "🟢 장 중" if is_market_open() else "🔴 장 마감"
kis_status    = "✅ KIS 연결됨" if api_ready else "⚪ KIS 미연결 (시세조회만 가능)"
st.markdown(f"**시장:** {market_status} &nbsp;|&nbsp; **{kis_status}**")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["💼 내 포트폴리오", "📡 종목 스캐너", "🤖 자동매매 현황"])

with tab1:
    col_t, col_r = st.columns([5, 1])
    with col_t:
        st.markdown("### 💼 내 보유 종목")
    with col_r:
        if st.button("🔄 새로고침", key="r1"):
            st.cache_data.clear()

    with st.spinner("Yahoo Finance에서 시세 조회 중..."):
        total_invested = 0
        total_current  = 0
        rows = []
        for ticker, name in MY_STOCKS.items():
            try:
                df      = get_yahoo_prices(ticker)
                current = get_yahoo_current_price(ticker)
                if current == 0 and not df.empty:
                    current = int(df["close"].iloc[-1])
                signal    = check_cross_signal(df) if not df.empty else "HOLD"
                vol_surge = check_volume_surge(df)  if not df.empty else False
                ma5       = round(df["close"].rolling(SHORT_PERIOD).mean().iloc[-1]) if not df.empty else 0
                ma20      = round(df["close"].rolling(LONG_PERIOD).mean().iloc[-1])  if not df.empty else 0
                buy_price = MY_BUY_PRICE.get(ticker, current)
                shares    = MY_SHARES.get(ticker, 0)
                pnl_pct   = (current - buy_price) / buy_price * 100 if buy_price else 0
                pnl_amt   = (current - buy_price) * shares
                total_invested += buy_price * shares
                total_current  += current * shares
                rows.append({
                    "종목명": name, "현재가": current, "매수가": buy_price,
                    "보유주수": shares, "MA5": ma5, "MA20": ma20,
                    "수익률": pnl_pct, "손익": pnl_amt,
                    "signal": signal, "vol_surge": vol_surge,
                })
            except Exception:
                rows.append({
                    "종목명": name, "현재가": 0, "매수가": MY_BUY_PRICE.get(ticker, 0),
                    "보유주수": MY_SHARES.get(ticker, 0), "MA5": 0, "MA20": 0,
                    "수익률": 0, "손익": 0, "signal": "오류", "vol_surge": False,
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
    st.caption("📡 Yahoo Finance 시세 (15분 지연) · API 키 없이 사용 가능")

with tab2:
    st.markdown("### 📡 코스피200 골든크로스 스캐너")
    st.markdown("골든크로스 + 거래량 급증 종목 자동 탐색 · API 키 불필요")
    if st.button("🔍 스캔 시작", key="scan"):
        buy_signals, sell_signals = [], []
        prog = st.progress(0, text="스캔 준비 중...")
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
                    buy_signals.append({"강도": "🔥 강력매수" if vol_surge else "🟢 매수",
                        "종목명": name, "현재가": current, "MA5": ma5, "MA20": ma20,
                        "거래량급증": "🔥 YES" if vol_surge else "—"})
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

with tab3:
    st.markdown("### 🤖 자동매매 현황")
    if not api_ready:
        st.warning("⚠️ 자동매매 현황은 왼쪽 사이드바에서 KIS API 키를 입력해야 사용 가능해요.")
        st.info("💡 시세조회와 스캐너는 API 키 없이도 사용 가능해요!")
    else:
        if st.button("🔄 새로고침", key="r3"):
            if "auto_data" in st.session_state:
                del st.session_state.auto_data
        if "auto_data" not in st.session_state:
            with st.spinner("신호 확인 중..."):
                auto_rows = []
                try:
                    token   = st.session_state.token
                    balance = get_balance(app_key, app_secret, token, is_mock, account_no)
                    st.metric("💰 예수금", f"{balance['cash']:,}원")
                    for ticker, name in MY_STOCKS.items():
                        try:
                            df      = get_yahoo_prices(ticker)
                            current = get_yahoo_current_price(ticker)
                            signal  = check_cross_signal(df) if not df.empty else "HOLD"
                            vol     = check_volume_surge(df)  if not df.empty else False
                            holding = get_holding_qty(balance, ticker)
                            ma5     = round(df["close"].rolling(SHORT_PERIOD).mean().iloc[-1]) if not df.empty else 0
                            ma20    = round(df["close"].rolling(LONG_PERIOD).mean().iloc[-1])  if not df.empty else 0
                            if signal == "BUY" and holding == 0:
                                action = "🟢 매수 예정"
                            elif signal == "SELL" and holding > 0:
                                action = "🔴 매도 예정"
                            elif signal == "BUY" and holding > 0:
                                action = "✅ 보유 중 (매수신호)"
                            else:
                                action = "⚪ 대기 중"
                            auto_rows.append({"종목명": name, "현재가": f"{current:,}원",
                                "MA5": f"{ma5:,}", "MA20": f"{ma20:,}",
                                "보유주수": holding, "자동매매 액션": action,
                                "거래량급증": "🔥" if vol else "—"})
                        except Exception:
                            continue
                    st.session_state.auto_data = auto_rows
                except Exception as e:
                    st.error(f"조회 실패: {e}")
        if "auto_data" in st.session_state:
            df_auto = pd.DataFrame(st.session_state.auto_data)
            if not df_auto.empty:
                st.dataframe(df_auto, use_container_width=True, hide_index=True)
    st.markdown("---")
    st.markdown("#### ▶ cmd에서 자동매매 실행하는 법")
    st.code("python auto_trading.py", language="bash")
    st.caption("자동매매는 골든크로스 감지 시 자동으로 매수/매도 주문을 실행해요.")
