import streamlit as st
import pandas as pd
import pydeck as pdk
import altair as alt
from pydeck import types as ptypes
from pathlib import Path

# ======================================
# 기본 설정
# ======================================

st.set_page_config(
    page_title="전국 상권 지도",
    layout="wide",
)

DATA_PATH = Path("2025_소상공인데이터.parquet") 


# ======================================
# 데이터 로딩 (캐시)
# ======================================

@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)

    # 최소 필요 컬럼 체크 (안전장치)
    required_cols = [
        "시도명", 
        "시군구명", 
        "행정동명", 
        "법정동명", 
        "도로명주소", 
        "대분류명", 
        "중분류명", 
        "소분류명", 
        "표준산업분류명", 
        "상호명", 
        "경도", 
        "위도"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"다음 컬럼이 데이터에 없습니다: {missing}")
        st.stop()

    # 위도/경도 숫자형 보장
    df["위도"] = pd.to_numeric(df["위도"], errors="coerce")
    df["경도"] = pd.to_numeric(df["경도"], errors="coerce")

    # 위·경도 없는 행은 미리 제거
    df = df.dropna(subset=["위도", "경도"])

    return df


df = load_data(DATA_PATH)


# ======================================
# 사이드바 필터 UI
# ======================================

st.sidebar.title("필터")

# 시도명 필터
sido_options = ["(전체)"] + sorted(df["시도명"].dropna().unique().tolist())
selected_sido = st.sidebar.selectbox("시도명", sido_options)

filtered = df.copy()
if selected_sido != "(전체)":
    filtered = filtered[filtered["시도명"] == selected_sido]

# 시군구명 필터
sigungu_options = ["(전체)"] + sorted(filtered["시군구명"].dropna().unique().tolist())
selected_sigungu = st.sidebar.selectbox("시군구명", sigungu_options)

if selected_sigungu != "(전체)":
    filtered = filtered[filtered["시군구명"] == selected_sigungu]

# 행정동 필터
hjdong_options = ["(전체)"] + sorted(filtered["행정동명"].dropna().unique().tolist())
selected_hjdong = st.sidebar.selectbox("행정동명", hjdong_options)

if selected_hjdong != "(전체)":
    filtered = filtered[filtered["행정동명"] == selected_hjdong]

# 행정동까지 분류한 df
area_df = filtered

# 상권업종 대분류
big_options = ["(전체)"] + sorted(filtered["대분류명"].dropna().unique().tolist())
selected_big = st.sidebar.selectbox("상권업종 대분류", big_options)

if selected_big != "(전체)":
    filtered = filtered[filtered["대분류명"] == selected_big]
    big_df = filtered # 대분류 df
else:
    big_df = area_df

# 상권업종 중분류
mid_options = ["(전체)"] + sorted(filtered["중분류명"].dropna().unique().tolist())
selected_mid = st.sidebar.selectbox("상권업종 중분류", mid_options)

if selected_mid != "(전체)":
    filtered = filtered[filtered["중분류명"] == selected_mid]
    middle_df = filtered # 중분류 df
else:
    middle_df = big_df

# 상권업종 소분류
small_options = ["(전체)"] + sorted(filtered["소분류명"].dropna().unique().tolist())
selected_small = st.sidebar.selectbox("상권업종 소분류", small_options)

if selected_small != "(전체)":
    filtered = filtered[filtered["소분류명"] == selected_small]


# ======================================
# 메인 영역 상단 요약
# ======================================

st.title("전국 소상공인 상권 지도 (2025년 기준)")

fcols = st.columns(7)

labels = ["시도명", "시군구명", "행정동명", "대분류", "중분류", "소분류", "데이터 개수"]
values = [selected_sido, selected_sigungu, selected_hjdong, selected_big, selected_mid, selected_small, f"{len(filtered):,} 건"]
for col, label, value in zip(fcols, labels, values):
    col.markdown(f"**{label}**<br>{value}", unsafe_allow_html=True)

# ======================================
# 지도용 데이터 준비
# ======================================

if filtered.empty:
    st.warning("선택된 조건에 해당하는 상가가 없습니다. 필터를 조정해 주세요.")
    st.stop()

# 지도에 사용할 최소 컬럼만 추리기
map_df = filtered[
    [
        "상호명",
        "도로명주소",
        "시도명",
        "시군구명",
        "행정동명",
        "법정동명",
        "대분류명",
        "중분류명",
        "소분류명",
        "위도",
        "경도",
    ]
].dropna(subset=["위도", "경도"]).copy()

# 너무 많으면 샘플링 (성능 보호용)
MAX_POINTS = 5000
if len(map_df) > MAX_POINTS:
    st.info(f"상가 수가 {len(map_df):,}건입니다. 지도 성능을 위해 최대 {MAX_POINTS:,}건만 무작위로 표시합니다.")
    map_df = map_df.sample(MAX_POINTS, random_state=0)

# pydeck에서 사용할 컬럼명으로 변경
map_df = map_df.rename(columns={"위도": "lat", "경도": "lon"})

# 중심 좌표 계산
center_lat = map_df["lat"].mean()
center_lon = map_df["lon"].mean()

view_state = pdk.ViewState(
    latitude=center_lat,
    longitude=center_lon,
    zoom=13,
    pitch=0,
)


# ======================================
# pydeck 레이어 정의
# ======================================

scatter_layer = pdk.Layer(
    "ScatterplotLayer",
    data=map_df,
    get_position="[lon, lat]",
    get_radius=7,  # 반지름 (m 단위 느낌)
    get_fill_color=[0, 120, 255, 160],  # RGBA
    pickable=True,
    auto_highlight=True,
)

# 텍스트 레이어 (지도위에 상호명 표시)
text_layer = pdk.Layer(
    "TextLayer",
    data=map_df,
    get_position="[lon, lat]",
    get_text="상호명",
    get_color=[0, 0, 0, 255],
    get_size=12, # 폰트 크기 (pixels 기준)
    # get_alignment_baseline="'bottom'",
    ize_units=ptypes.String("pixels"),
    size_min_pixels=10,
    size_max_pixels=20,

    characterSet=ptypes.String("auto"),  # 한글 표시 핵심 설정
    get_background_color=[255, 255, 255, 200],
    background=True,                 # 글자 뒤 흰 배경 박스

    get_text_anchor=ptypes.String("middle"),
    get_alignment_baseline=ptypes.String("top"),
    # get_pixel_offset=[0, 20], # 점 위치에서 아래쪽으로 살짝 이동
)

tooltip = {
    "html": (
        "<b>{상호명}</b><br/>"
        "{도로명주소}<br/>"
        # "{시도명} {시군구명} {법정동명}<br/>"
        # "{대분류명} / {중분류명} / {소분류명}"
        "{소분류명}"
    ),
    "style": {
        "backgroundColor": "white",
        "color": "black",
    },
}

deck = pdk.Deck(
    layers=[scatter_layer, text_layer],  # 나중에 text_layer 추가 가능
    initial_view_state=view_state,
    tooltip=tooltip,
    map_provider="carto",
    map_style="road", # "light", "dark", "road", "satellite" 등 가능
    # map_style="mapbox://styles/mapbox/light-v9",  # 기본 지도 스타일
)

# ======================================
# 지도 렌더링
# ======================================

st.markdown("### 지도")
st.pydeck_chart(deck, width="stretch", height=900, selection_mode="single-object",)


# ======================================
# 업종 비율 그래프 (현재 필터 기준)
# ======================================

st.markdown("### 업종 비율")

tab1, tab2, tab3 = st.tabs(["대분류 비율", "중분류 비율", "소분류 비율"])

# ========================
# 탭 1: 업종 대분류 비율
# ========================
with tab1:
    biz_big = (
        area_df["대분류명"]
        .value_counts(normalize=True)
        .rename("비율")
        .reset_index()
    )
    biz_big.rename(columns={"index": "대분류명"}, inplace=True)

    bars_big = (
        alt.Chart(biz_big)
        .mark_bar()
        .encode(
            x=alt.X("대분류명:N", sort="-y", title="상권업종 대분류"),
            y=alt.Y("비율:Q", axis=alt.Axis(format="%", title="비율")),
            tooltip=[
                alt.Tooltip("대분류명:N", title="업종"),
                alt.Tooltip("비율:Q", title="비율", format=".1%"),
            ],
        )
    )

    text_big = (
        alt.Chart(biz_big)
        .mark_text(dy=-5)
        .encode(
            x="대분류명:N",
            y="비율:Q",
            text=alt.Text("비율:Q", format=".1%"),
        )
    )

    st.altair_chart((bars_big + text_big).properties(height=300), width="stretch")

# ========================
# 탭 2: 업종 중분류 비율
# ========================
with tab2:
    biz_small = (
        big_df["중분류명"]
        .value_counts(normalize=True)
        .rename("비율")
        .reset_index()
    )
    biz_small.rename(columns={"index": "중분류명"}, inplace=True)

    # 중분류가 너무 많으면 상위 N개만 표시 (옵션)
    MAX_MID = 20
    if len(biz_small) > MAX_MID:
        biz_small = biz_small.head(MAX_MID)

    bars_small = (
        alt.Chart(biz_small)
        .mark_bar()
        .encode(
            x=alt.X("중분류명:N", sort="-y", title="상권업종 중분류"),
            y=alt.Y("비율:Q", axis=alt.Axis(format="%", title="비율")),
            tooltip=[
                alt.Tooltip("중분류명:N", title="업종"),
                alt.Tooltip("비율:Q", title="비율", format=".1%"),
            ],
        )
    )

    text_small = (
        alt.Chart(biz_small)
        .mark_text(dy=-5)
        .encode(
            x="중분류명:N",
            y="비율:Q",
            text=alt.Text("비율:Q", format=".1%"),
        )
    )

    st.altair_chart((bars_small + text_small).properties(height=300), width="stretch")


# ========================
# 탭 3: 업종 소분류 비율
# ========================
with tab3:
    biz_small = (
        middle_df["소분류명"]
        .value_counts(normalize=True)
        .rename("비율")
        .reset_index()
    )
    biz_small.rename(columns={"index": "소분류명"}, inplace=True)

    # 소분류가 너무 많으면 상위 N개만 표시 (옵션)
    MAX_MID = 20
    if len(biz_small) > MAX_MID:
        biz_small = biz_small.head(MAX_MID)

    bars_small = (
        alt.Chart(biz_small)
        .mark_bar()
        .encode(
            x=alt.X("소분류명:N", sort="-y", title="상권업종 소분류"),
            y=alt.Y("비율:Q", axis=alt.Axis(format="%", title="비율")),
            tooltip=[
                alt.Tooltip("소분류명:N", title="업종"),
                alt.Tooltip("비율:Q", title="비율", format=".1%"),
            ],
        )
    )

    text_small = (
        alt.Chart(biz_small)
        .mark_text(dy=-5)
        .encode(
            x="소분류명:N",
            y="비율:Q",
            text=alt.Text("비율:Q", format=".1%"),
        )
    )

    st.altair_chart((bars_small + text_small).properties(height=300), width="stretch")

# ======================================
# 하단에 표도 같이 보여주고 싶으면
# ======================================

with st.expander("필터링된 상가 목록 보기"):
    st.dataframe(
        map_df[
            [
                "상호명",
                "도로명주소",
                "시도명",
                "시군구명",
                "행정동명",
                "법정동명",
                "대분류명",
                "중분류명",
                "소분류명",
                # "lat",
                # "lon",
            ]
        ].reset_index(drop=True)
    )
