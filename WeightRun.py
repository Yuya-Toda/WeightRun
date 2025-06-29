import streamlit as st
import pandas as pd
from datetime import date
import altair as alt
import os

st.set_page_config(page_title="WeightRun", layout="wide")

st.title("🏃‍♀️ 体重とランニング記録")

CSV_FILE = "records.csv"
GOAL_FILE = "goal_weight.txt"
GOAL_MONTHLY_FILE = "monthly_goals.csv"

# データ読み込み
@st.cache_data
def load_data():
    try:
        df = pd.read_csv(CSV_FILE)
        df["日付"] = pd.to_datetime(df["日付"], errors="coerce")
        return df
    except:
        return pd.DataFrame(columns=["日付", "体重", "距離", "カロリー"])

df = load_data()

# ゴール体重読み込み
@st.cache_data
def load_goal_weight():
    if os.path.exists(GOAL_FILE):
        with open(GOAL_FILE, "r") as f:
            try:
                return float(f.read())
            except:
                return 60.0
    return 60.0

goal_weight_default = load_goal_weight()

# --- 日別インプット ---
st.subheader("📝 日別データ入力")

with st.form("daily_input_form", clear_on_submit=False):
    input_date = st.date_input("日付", date.today())
    weight = st.number_input("体重 (kg)", min_value=0.0, step=0.1)
    distance = st.number_input("ランニング距離 (km)", min_value=0.0, step=0.1)
    submitted = st.form_submit_button("記録を保存")

    if submitted:
        calorie = round(distance * 60, 2)  # 消費カロリー計算（仮）
        new_row = pd.DataFrame({
            "日付": [input_date],
            "体重": [weight],
            "距離": [distance],
            "カロリー": [calorie]
        })
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)
        st.success("記録を保存しました！")

# --- 日別推移グラフ（体重とカロリー） ---
st.subheader("📈 日別推移グラフ")
df_plot = df.sort_values("日付")

weight_line = alt.Chart(df_plot).mark_line(color='#1f77b4').encode(
    x=alt.X('日付:T', title='日付'),
    y=alt.Y('体重:Q', title='体重 (kg)', scale=alt.Scale(domain=[60, 80]), axis=alt.Axis(format='.1f'))
)

weight_points = alt.Chart(df_plot).mark_point(color='#1f77b4', filled=True).encode(
    x='日付:T',
    y='体重:Q'
)

calorie_bar = alt.Chart(df_plot).mark_bar(color='#ff7f0e', size=10).encode(
    x=alt.X('日付:T', title='日付'),
    y=alt.Y('カロリー:Q', title='消費カロリー', scale=alt.Scale(zero=True))
)

st.altair_chart((weight_line + weight_points).properties(height=300), use_container_width=True)
st.altair_chart(calorie_bar.properties(height=300), use_container_width=True)


# 月別目標読み込み（2025年6月〜12月）
def load_monthly_goals():
    months = pd.date_range("2025-06-01", "2025-12-01", freq='MS').strftime("%Y-%m")

    if os.path.exists(GOAL_MONTHLY_FILE):
        df = pd.read_csv(GOAL_MONTHLY_FILE)

        # 年月列が存在しない場合に対応
        if '年月' not in df.columns:
            df = df.reset_index()
        if 'index' in df.columns and '年月' not in df.columns:
            df.rename(columns={'index': '年月'}, inplace=True)

        # 最終チェック
        if '年月' not in df.columns:
            raise KeyError("CSVファイルに '年月' 列が存在しません。列名を確認してください。")

        # 年月フィルタ＆整形
        df = df[df["年月"].isin(months)]
        df = df.set_index("年月").reindex(months).reset_index()
        df.fillna({"体重目標": 60.0, "カロリー目標": 0.0}, inplace=True)
        return df

    # ファイルが存在しない場合：初期値を返す
    return pd.DataFrame({
        "年月": months,
        "体重目標": [60.0] * len(months),
        "カロリー目標": [0.0] * len(months)
    })

goals_df = load_monthly_goals()

# 月別目標入力
st.header("🎯 2025年6月〜12月の月別目標")
for i, row in goals_df.iterrows():
    ym = row.get("年月", f"2025-{6+i:02d}")
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        st.markdown(f"**{ym}**")
    with col2:
        weight_val = float(row.get("体重目標", 60.0))
        weight_val = weight_val if weight_val >= 30 else 60.0
        goals_df.loc[i, "体重目標"] = st.number_input(
            f"体重 ({ym})", min_value=30.0, max_value=150.0, step=0.1,
            key=f"体重{i}", value=weight_val
        )
    with col3:
        calorie_val = float(row.get("カロリー目標", 0.0))
        goals_df.loc[i, "カロリー目標"] = st.number_input(
            f"カロリー ({ym})", min_value=0.0, step=100.0,
            key=f"カロリー{i}", value=calorie_val
        )

if st.button("💾 月別目標を保存"):
    goals_df.to_csv(GOAL_MONTHLY_FILE, index=False)
    st.success("目標を保存しました")

# --- 月別体重・カロリー推移 ---
st.subheader("📈 月別体重・カロリー推移")
df["年月"] = df["日付"].dt.to_period("M")
monthly_summary = df.groupby("年月").agg({"体重": "mean", "カロリー": "sum"}).reset_index()
monthly_summary["年月"] = monthly_summary["年月"].astype(str)


goals_df = goals_df.copy()
goals_df.reset_index(inplace=True, drop=True)
if 'index' in goals_df.columns and '年月' not in goals_df.columns:
    goals_df.rename(columns={'index': '年月'}, inplace=True)
goals_df['年月'] = goals_df['年月'].astype(str)

merged = pd.merge(monthly_summary, goals_df, on="年月", how="outer").sort_values("年月")

# meltして体重データを統一
merged["体重_実績"] = merged["体重"]
merged["体重_目標"] = merged["体重目標"]
df_weight_long = pd.melt(merged[["年月", "体重_実績", "体重_目標"]], id_vars="年月", var_name="種別", value_name="体重")

weight_line = alt.Chart(df_weight_long).mark_line().encode(



    x=alt.X('年月:N', title='年月'),
    y=alt.Y('体重:Q', title='体重 (kg)', axis=alt.Axis(titleColor='#1f77b4')),
    color=alt.Color('種別:N', scale=alt.Scale(domain=['体重_実績', '体重_目標'], range=['#1f77b4', '#00BFFF']),
                    legend=alt.Legend(title="体重種別", orient="bottom"))
)

weight_point = alt.Chart(df_weight_long).mark_point().encode(
    x='年月:N',
    y='体重:Q',
    color=alt.Color('種別:N', scale=alt.Scale(domain=['体重_実績', '体重_目標'], range=['#1f77b4', '#00BFFF']),
                    legend=alt.Legend(title="体重種別", orient="bottom"))
)


# カロリー棒グラフの整形

df_cal = merged[['年月', 'カロリー', 'カロリー目標']].copy()
df_cal_long = pd.melt(df_cal, id_vars='年月', var_name='種別', value_name='値')

# 🔶 カラースケールを目標=オレンジ, 実績=赤に固定
color_scale = alt.Scale(
    domain=['カロリー', 'カロリー目標'],
    range=['#FF0000', '#FFA500']
)

calorie_bar = alt.Chart(df_cal_long).mark_bar().encode(
    x=alt.X('年月:N', title='年月'),
    y=alt.Y('値:Q', title='消費カロリー', axis=alt.Axis(titleColor='orange')),
    color=alt.Color('種別:N', scale=color_scale, legend=alt.Legend(title="カロリー種別", orient="bottom"))
).properties(height=400)

combined = alt.layer(
    calorie_bar,
    weight_line,
    weight_point
).resolve_scale(y='independent')

st.altair_chart(combined, use_container_width=True)

# --- 年間目標体重 ---
st.header("🎯 年間目標体重")
goal_weight = st.number_input("最終目標体重 (kg)", min_value=30.0, max_value=150.0, step=0.1, value=goal_weight_default)
if goal_weight:
    try:
        with open(GOAL_FILE, "w") as f:
            f.write(str(goal_weight))
        recent_weight = df.sort_values("日付")["体重"].iloc[-1]
        diff = recent_weight - goal_weight
        st.metric("📌 残り減量目標", f"{diff:.2f} kg")
    except:
        st.warning("記録が必要です")
