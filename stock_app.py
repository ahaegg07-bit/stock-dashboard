"""
한국투자증권 KIS API - 웹 대시보드
====================================
streamlit run stock_app.py
"""

import os
import time
import threading
import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# 코스피200 종목
# ─────────────────────────────────────────
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

SHORT_PERIOD = 5
LONG_PERIOD  = 20
VOLUME_SURGE = 2.0

# ─────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────
st.set_page_config(
    page_title="📈 주식 자동매매 대시보드",
    page_icon="📈",
    layout="wide",
)

st.markdown("""
<style>
    .stApp { background-color: #060c1a; color: #e2e8f0; }
    h1,h2,h3 { color: #ffffff; }
    .buy  { color: #00ff88; font-weight: 800; }
    .sell { color: #ef4444; font-weight: 800; }
    .hold { color: #94a3b8; }
    .hot  { color: #ff6b35; font-weight: 800; }
    div[data-testid="stMetricValue"] { color: #4a9eff; font-weight: 800; }
    .stButton > button {
        background: linear-gradient(135deg, #4a9eff, #0066ff);
        color: white; border: none; border-radius: 8px; font-weight: 700;
    }
    .stButton > button:hover { background: linear-gradient(135deg, #3a8eef, #0055ee); color: white; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# API 함수들
# ─────────────────────────────────────────
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

def get_stock_prices(app_key, app_secret, token, is_mock, ticker, days=30):
    url = f"{get_base_url(is_mock)}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
    headers = get_headers(app_key, app_secret, token, "FHKST01010400")
    params = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker,
        "FID_ORG_ADJ_PRC": "0", "FID_PERIOD_DIV_CODE": "D",
    }
    res = requests.get(url, headers=headers, params=params, timeout=10)
    res.raise_for_status()
    data = res.json().get("output", [])
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df = df[["stck_bsop_date", "stck_clpr", "acml_vol"]].copy()
    df.columns = ["date", "close", "volume"]
    df["close"]  = df["close"].astype(int)
    df["volume"] = df["volume"].astype(int)
    df = df.sort_values("date").reset_index(drop=True)
    return df.tail(days)

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

def get_current_price(app_key, app_secret, token, is_mock, ticker):
    url = f"{get_base_url(is_mock)}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_headers(app_key, app_secret, token, "FHKST01010100")
    res = requests.get(url, headers=headers,
                       params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker},
                       timeout=10)
    res.raise_for_status()
    return int(res.json()["output"]["stck_prpr"])

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


# ─────────────────────────────────────────
# 사이드바 설정
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ API 설정")
    app_key    = st.text_input("APP KEY",    value=os.getenv("APP_KEY", ""),    type="password")
    app_secret = st.text_input("APP SECRET", value=os.getenv("APP_SECRET", ""), type="password")
    account_no = st.text_input("계좌번호",   value=os.getenv("ACCOUNT_NO", ""), placeholder="50123456-01")
    is_mock    = st.toggle("모의투자 모드", value=True)
    mode_label = "🟡 모의투자" if is_mock else "🔴 실전투자"
    st.info(mode_label)
    st.markdown("---")
    st.markdown("### 📌 사용법")
    st.markdown("1. API 키 입력\n2. 탭에서 기능 선택\n3. 버튼 클릭으로 조작")

api_ready = bool(app_key and app_secret and account_no)

# ─────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────
st.markdown("# 📈 주식 자동매매 대시보드")
st.markdown(f"**{mode_label}** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if not api_ready:
    st.warning("⚠️ 왼쪽 사이드바에서 API 키와 계좌번호를 입력하세요.")
    st.stop()

# 토큰 발급 (세션에 캐시)
if "token" not in st.session_state or st.session_state.get("is_mock") != is_mock:
    with st.spinner("🔑 토큰 발급 중..."):
        try:
            st.session_state.token   = get_access_token(app_key, app_secret, is_mock)
            st.session_state.is_mock = is_mock
            st.success("✅ 연결 성공!")
        except Exception as e:
            st.error(f"❌ 연결 실패: {e}")
            st.stop()

token = st.session_state.token
market_status = "🟢 장 중" if is_market_open() else "🔴 장 마감"
st.markdown(f"**시장 상태:** {market_status}")
st.markdown("---")

# ─────────────────────────────────────────
# 탭
# ─────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["💼 내 포트폴리오", "📡 종목 스캐너", "🤖 자동매매 현황"])

# ══════════════════════════════════════════
# 탭1: 내 포트폴리오
# ══════════════════════════════════════════
with tab1:
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.markdown("### 💼 내 보유 종목 현황")
    with col_btn:
        refresh1 = st.button("🔄 새로고침", key="r1")

    if refresh1 or "portfolio_data" not in st.session_state:
        with st.spinner("시세 조회 중..."):
            rows = []
            try:
                balance = get_balance(app_key, app_secret, token, is_mock, account_no)
                cash    = balance["cash"]
                for ticker, name in MY_STOCKS.items():
                    try:
                        df      = get_stock_prices(app_key, app_secret, token, is_mock, ticker)
                        current = get_current_price(app_key, app_secret, token, is_mock, ticker)
                        signal  = check_cross_signal(df) if not df.empty else "HOLD"
                        vol_surge = check_volume_surge(df) if not df.empty else False
                        ma5  = df["close"].rolling(SHORT_PERIOD).mean().iloc[-1] if not df.empty else 0
                        ma20 = df["close"].rolling(LONG_PERIOD).mean().iloc[-1]  if not df.empty else 0
                        holding = get_holding_qty(balance, ticker)
                        rows.append({
                            "종목명": name, "ticker": ticker,
                            "현재가": current, "MA5": round(ma5),
                            "MA20": round(ma20), "보유주수": holding,
                            "signal": signal, "vol_surge": vol_surge,
                        })
                        time.sleep(0.3)
                    except Exception as e:
                        rows.append({"종목명": name, "ticker": ticker,
                                     "현재가": 0, "MA5": 0, "MA20": 0,
                                     "보유주수": 0, "signal": "오류", "vol_surge": False})
                st.session_state.portfolio_data = rows
                st.session_state.cash = cash
            except Exception as e:
                st.error(f"잔고 조회 실패: {e}")

    if "portfolio_data" in st.session_state:
        cash = st.session_state.get("cash", 0)
        st.metric("💰 예수금", f"{cash:,}원")
        st.markdown("---")

        for row in st.session_state.portfolio_data:
            signal    = row["signal"]
            vol_surge = row["vol_surge"]

            if signal == "BUY":
                sig_label = "🟢 매수신호" + (" 📊거래량급증!" if vol_surge else "")
                sig_color = "buy"
            elif signal == "SELL":
                sig_label = "🔴 매도신호"
                sig_color = "sell"
            else:
                sig_label = "⚪ 관망"
                sig_color = "hold"

            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 3])
            c1.markdown(f"**{row['종목명']}**")
            c2.markdown(f"{row['현재가']:,}원")
            c3.markdown(f"MA5: {row['MA5']:,}")
            c4.markdown(f"보유: {row['보유주수']}주")
            c5.markdown(f"<span class='{sig_color}'>{sig_label}</span>", unsafe_allow_html=True)
            st.markdown("---")


# ══════════════════════════════════════════
# 탭2: 종목 스캐너
# ══════════════════════════════════════════
with tab2:
    st.markdown("### 📡 코스피200 골든크로스 스캐너")
    st.markdown("골든크로스 + 거래량 급증 종목을 자동으로 찾아드려요")

    col_s1, col_s2 = st.columns([4, 1])
    with col_s2:
        scan_btn = st.button("🔍 스캔 시작", key="scan")

    if scan_btn:
        buy_signals  = []
        sell_signals = []
        total = len(KOSPI200)
        prog  = st.progress(0, text="스캔 준비 중...")

        for i, (ticker, name) in enumerate(KOSPI200.items()):
            prog.progress((i + 1) / total, text=f"스캔 중... ({i+1}/{total}) {name}")
            try:
                df = get_stock_prices(app_key, app_secret, token, is_mock, ticker)
                if df.empty:
                    continue
                signal    = check_cross_signal(df)
                vol_surge = check_volume_surge(df)
                current   = df["close"].iloc[-1]
                ma5       = round(df["close"].rolling(SHORT_PERIOD).mean().iloc[-1])
                ma20      = round(df["close"].rolling(LONG_PERIOD).mean().iloc[-1])

                if signal == "BUY":
                    buy_signals.append({
                        "종목명": name, "현재가": current,
                        "MA5": ma5, "MA20": ma20,
                        "거래량급증": "🔥 YES" if vol_surge else "—",
                        "강도": "🔥 강력매수" if vol_surge else "🟢 매수",
                    })
                elif signal == "SELL":
                    sell_signals.append({
                        "종목명": name, "현재가": current,
                        "MA5": ma5, "MA20": ma20,
                    })
                time.sleep(0.3)
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

        st.markdown(f"#### 🟢 매수 신호 종목 — {len(buy_list)}개")
        if buy_list:
            # 강력매수 먼저 정렬
            buy_list_sorted = sorted(buy_list, key=lambda x: x["거래량급증"] == "🔥 YES", reverse=True)
            df_buy = pd.DataFrame(buy_list_sorted)[["강도", "종목명", "현재가", "MA5", "MA20", "거래량급증"]]
            df_buy["현재가"] = df_buy["현재가"].apply(lambda x: f"{x:,}원")
            df_buy["MA5"]   = df_buy["MA5"].apply(lambda x: f"{x:,}")
            df_buy["MA20"]  = df_buy["MA20"].apply(lambda x: f"{x:,}")
            st.dataframe(df_buy, use_container_width=True, hide_index=True)
        else:
            st.info("현재 매수 신호 종목이 없어요")

        st.markdown("---")
        st.markdown(f"#### 🔴 매도 신호 종목 — {len(sell_list)}개")
        if sell_list:
            df_sell = pd.DataFrame(sell_list)[["종목명", "현재가", "MA5", "MA20"]]
            df_sell["현재가"] = df_sell["현재가"].apply(lambda x: f"{x:,}원")
            df_sell["MA5"]   = df_sell["MA5"].apply(lambda x: f"{x:,}")
            df_sell["MA20"]  = df_sell["MA20"].apply(lambda x: f"{x:,}")
            st.dataframe(df_sell, use_container_width=True, hide_index=True)
        else:
            st.info("현재 매도 신호 종목이 없어요")

        st.caption("⚠️ 스캔 결과는 참고용입니다. 투자 결정은 본인이 판단하세요.")


# ══════════════════════════════════════════
# 탭3: 자동매매 현황
# ══════════════════════════════════════════
with tab3:
    st.markdown("### 🤖 자동매매 현황")
    st.info("자동매매는 **auto_trading.py** 를 cmd에서 실행해야 작동해요.\n\n"
            "이 탭에서는 현재 신호 상태를 실시간으로 확인할 수 있어요.")

    col_a, col_b = st.columns([4, 1])
    with col_b:
        refresh3 = st.button("🔄 새로고침", key="r3")

    if refresh3 or "auto_data" not in st.session_state:
        with st.spinner("신호 확인 중..."):
            auto_rows = []
            try:
                balance = get_balance(app_key, app_secret, token, is_mock, account_no)
                for ticker, name in MY_STOCKS.items():
                    try:
                        df      = get_stock_prices(app_key, app_secret, token, is_mock, ticker)
                        current = get_current_price(app_key, app_secret, token, is_mock, ticker)
                        signal  = check_cross_signal(df) if not df.empty else "HOLD"
                        vol     = check_volume_surge(df) if not df.empty else False
                        holding = get_holding_qty(balance, ticker)
                        ma5     = round(df["close"].rolling(SHORT_PERIOD).mean().iloc[-1]) if not df.empty else 0
                        ma20    = round(df["close"].rolling(LONG_PERIOD).mean().iloc[-1])  if not df.empty else 0

                        # 자동매매 액션 판단
                        if signal == "BUY" and holding == 0:
                            action = "🟢 매수 예정"
                        elif signal == "SELL" and holding > 0:
                            action = "🔴 매도 예정"
                        elif signal == "BUY" and holding > 0:
                            action = "✅ 보유 중 (매수신호)"
                        else:
                            action = "⚪ 대기 중"

                        auto_rows.append({
                            "종목명": name, "현재가": f"{current:,}원",
                            "MA5": f"{ma5:,}", "MA20": f"{ma20:,}",
                            "보유주수": holding, "자동매매 액션": action,
                            "거래량급증": "🔥" if vol else "—",
                        })
                        time.sleep(0.3)
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

