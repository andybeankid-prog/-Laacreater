import os
import time
import re
import streamlit as st
import pandas as pd
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.exceptions import FacebookRequestError

# --- App Configuration ---
st.set_page_config(
    page_title="FB 批量建立類似受眾工具",
    page_icon="🎯",
    layout="wide",
)

# --- CSS for custom styling ---
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .st-emotion-cache-1r6slb0 {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem !important;
        background-color: #fafafa;
    }
    .stButton>button {
        border-radius: 10px;
        border: 2px solid #1c8dff;
        color: #1c8dff;
        background-color: white;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        border-color: #007bff;
        color: white;
        background-color: #007bff;
    }
</style>
""", unsafe_allow_html=True)


# --- Helper Functions ---
def initialize_api(access_token):
    """初始化 Facebook Marketing API"""
    try:
        FacebookAdsApi.init(access_token=access_token)
        return True
    except Exception as e:
        st.error(f"API 初始化失敗: {e}")
        return False


@st.cache_data(ttl=600)
def get_custom_audiences(_ad_account_id):
    """獲取指定廣告帳戶下的所有自訂受眾"""
    audiences_data = []
    try:
        account = AdAccount(f'act_{_ad_account_id}')
        params = {
            'fields': [
                'id', 'name', 'description',
                'approximate_count_lower_bound',
                'audience_subtype', 'time_updated'
            ],
            'limit': 500
        }
        audiences = account.get_custom_audiences(params=params)

        for audience in audiences:
            audiences_data.append({
                "id": audience.get('id'),
                "name": audience.get('name'),
                "size": audience.get('approximate_count_lower_bound', 'N/A'),
                "subtype": audience.get('audience_subtype'),
                "updated_time": pd.to_datetime(audience.get('time_updated')).strftime('%Y-%m-%d %H:%M')
            })

        audiences_data.sort(key=lambda x: x['updated_time'], reverse=True)
        return audiences_data, None
    except FacebookRequestError as e:
        return [], f"獲取受眾失敗 (API 錯誤): {e.api_error_message()}"
    except Exception as e:
        return [], f"獲取受眾失敗 (未知錯誤): {e}"


def create_lookalike_audience(ad_account_id, source_audience_id, source_audience_name, country, ratio, conflict_strategy):
    """建立單一的類似廣告受眾"""
    percentage = int(float(ratio) * 100)
    lookalike_name = f"{country.upper()}-{percentage}%-{source_audience_name}"

    try:
        lookalike_spec = {
            'origin_audience_id': source_audience_id,
            'starting_ratio': float(ratio) - 0.01 if float(ratio) > 0.01 else 0,
            'ratio': float(ratio),
            'location_spec': {
                'countries': [country]
            }
        }

        audience = AdAccount(f'act_{ad_account_id}').create_custom_audience(
            params={
                'name': lookalike_name,
                'subtype': 'LOOKALIKE',
                'origin_audience_id': source_audience_id,
                'lookalike_spec': lookalike_spec
            }
        )
        return {"status": "success", "name": lookalike_name, "id": audience['id']}

    except FacebookRequestError as e:
        error_message = e.api_error_message()
        if "name is already used" in error_message and conflict_strategy == "skip":
            return {"status": "skipped", "name": lookalike_name, "reason": "同名受眾已存在"}
        return {"status": "failed", "name": lookalike_name, "reason": error_message}
    except Exception as e:
        return {"status": "failed", "name": lookalike_name, "reason": str(e)}


# --- Sidebar for Inputs ---
with st.sidebar:
    st.subheader("🔑 Facebook Access Token")
    input_token = st.text_input("輸入 Access Token", value="", type="password")
    remember_token = st.checkbox("記住 Token（寫入 .streamlit/secrets.toml）", value=False)

    if remember_token and input_token:
        st.session_state["saved_token"] = input_token
        st.success("✅ Token 已暫存，直到本次 Session 結束")

    # 如果有暫存就自動讀取
    access_token = st.session_state.get("saved_token", input_token)

    st.header("⚙️ 參數設定")
    ad_account_id = st.text_input("廣告帳號 ID (不含 act_)", help="例如：924798139306112")
    countries_input = st.text_input("國家代碼 (逗號分隔)", "TW,US,JP")
    countries = [c.strip().upper() for c in countries_input.split(',') if c.strip()]
    ratios_input = st.text_input("類似受眾比例 (逗號分隔)", "0.01,0.02")
    ratios = [r.strip() for r in ratios_input.split(',') if r.strip()]

    conflict_strategy = st.radio(
        "命名重複處理策略",
        ('同名則略過', '嚴格模式 (同名則報錯)'),
        index=0
    )
    strategy_map = {'同名則略過': 'skip', '嚴格模式 (同名則報錯)': 'strict'}
    selected_strategy = strategy_map[conflict_strategy]


# --- Main Content ---
st.title("🎯 FB Lookalike Audience 批量建立工具")
st.markdown("一個幫助您快速、大量建立 Facebook 類似受眾的省時工具。")
st.markdown("---")

if not access_token or not ad_account_id:
    st.info("👋 歡迎使用！請在左側完成設定以開始。")
else:
    if initialize_api(access_token):
        st.header("1️⃣ 選擇來源受眾")

        with st.spinner('正在載入自訂受眾...'):
            audiences, error = get_custom_audiences(ad_account_id)

        if error:
            st.error(error)
        elif not audiences:
            st.warning("沒有找到自訂受眾。")
        else:
            df_audiences = pd.DataFrame(audiences)

            search_term = st.text_input("🔍 搜尋受眾名稱", placeholder="輸入關鍵字以篩選...")
            if search_term:
                df_display = df_audiences[df_audiences['name'].str.contains(search_term, case=False, na=False)]
            else:
                df_display = df_audiences

            audience_names_to_display = [
                f"{row['name']} (Size: {row['size']:,} | ID: ...{row['id'][-6:]})"
                for _, row in df_display.iterrows()
            ]

            selected_audience_display_names = st.multiselect(
                "請選擇來源受眾",
                options=audience_names_to_display
            )

            selected_audiences = []
            if selected_audience_display_names:
                for display_name in selected_audience_display_names:
                    match = re.search(r"ID: \.\.\.(\w{6})", display_name)
                    if match:
                        suffix = match.group(1)
                        original = df_display[df_display['id'].str.endswith(suffix)].iloc[0]
                        selected_audiences.append({
                            "id": original['id'],
                            "name": original['name']
                        })

            st.markdown("---")
            st.header("2️⃣ 執行與結果")

            if not selected_audiences or not countries or not ratios:
                st.info("請完成所有設定。")
            else:
                total_tasks = len(selected_audiences) * len(countries) * len(ratios)
                st.write(f"**📝 預計建立 {total_tasks} 個類似受眾**")

                if st.button(f"🚀 開始建立"):
                    progress_bar = st.progress(0, text="準備中...")
                    success_list, skipped_list, failed_list = [], [], []
                    tasks_done = 0

                    with st.expander("詳細執行日誌", expanded=True):
                        for source in selected_audiences:
                            for country in countries:
                                for ratio in ratios:
                                    progress_text = f"建立: {country.upper()}-{int(float(ratio)*100)}% ({tasks_done+1}/{total_tasks})"
                                    progress_bar.progress((tasks_done+1)/total_tasks, text=progress_text)

                                    result = create_lookalike_audience(
                                        ad_account_id,
                                        source['id'],
                                        source['name'],
                                        country,
                                        ratio,
                                        selected_strategy
                                    )
                                    tasks_done += 1

                                    if result['status'] == 'success':
                                        success_list.append(result['name'])
                                    elif result['status'] == 'skipped':
                                        skipped_list.append(result['name'])
                                    else:
                                        failed_list.append(f"{result['name']} → {result['reason']}")

                                    time.sleep(1)

                    progress_bar.progress(1.0, text="完成！")
                    st.balloons()
                    st.success(f"完成 ✅ 成功 {len(success_list)}，略過 {len(skipped_list)}，失敗 {len(failed_list)}")
