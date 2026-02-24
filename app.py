import streamlit as st
import pandas as pd
import datetime
import urllib.parse

# --- Page Configuration ---
st.set_page_config(
    page_title="VSOP Live Dashboard",
    page_icon="🎸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS for Premium Design ---
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .song-card {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 15px;
        border-left: 5px solid #ff4b4b;
    }
    .song-title {
        font-size: 1.2rem;
        font-weight: bold;
        color: #ffffff;
    }
    .song-meta {
        font-size: 0.9rem;
        color: #a0a0a0;
    }
    .youtube-link {
        color: #ff4b4b;
        text-decoration: none;
        font-weight: bold;
    }
    .youtube-link:hover {
        text-decoration: underline;
    }
    h1, h2, h3 {
        color: #f0f2f6;
    }
</style>
""", unsafe_allow_html=True)

# --- ユーティリティ: 列名の柔軟なマッチングと防御的処理 ---
def get_flexible_col(df, target_names, default=None):
    """
    dfの列名から target_names に含まれるか、あるいはそれに近い名前を探す。
    見つからなかった場合は default を返す。
    """
    actual_cols = df.columns.tolist()
    # 1. 完全一致 (または大文字小文字無視の一致)
    for target in target_names:
        for col in actual_cols:
            if target.lower() == col.lower():
                return col
    
    # 2. 部分一致 (targetが列名に含まれているか)
    for target in target_names:
        for col in actual_cols:
            if target in col:
                return col
    return default

def ensure_col(df, target_names, fallback_val=""):
    """
    列が見つからない場合、fallback_val で満たされた仮想列を作成して名前を返す。
    """
    col = get_flexible_col(df, target_names)
    if col is None:
        virtual_name = target_names[0] + " (仮想)"
        df[virtual_name] = fallback_val
        return virtual_name
    return col

# --- Data Connection ---
def load_data():
    try:
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        if "/d/" in raw_url:
            spreadsheet_id = raw_url.split("/d/")[1].split("/")[0]
        else:
            spreadsheet_id = raw_url
        
        base_csv_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet="
        
        def get_sheet(sheet_name):
            encoded_name = urllib.parse.quote(sheet_name)
            url = base_csv_url + encoded_name
            return pd.read_csv(url, encoding='utf-8')

        df_songs = get_sheet("演奏曲目")
        df_lives = get_sheet("ライブ一覧")
        
        # 列名のクリーニング
        df_songs.columns = [c.strip() for c in df_songs.columns]
        df_lives.columns = [c.strip() for c in df_lives.columns]
        
        # 全データに対して強制的に文字列変換
        for df in [df_songs, df_lives]:
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).replace(['nan', 'None'], "-").fillna("-")
        
        return df_songs, df_lives
    except Exception as e:
        st.error(f"データの読み込み中にエラーが発生しました: {e}")
        st.stop()

# --- データ読み込みとマッピング ---
df_songs_raw, df_lives_raw = load_data()

# コピーを作成して破壊的変更を防ぐ
df_songs = df_songs_raw.copy()
df_lives = df_lives_raw.copy()

# 画面トップでのデバッグ表示 (デフォルトは閉じておく)
with st.expander("🛠️ スプレッドシート列名デバッグ"):
    st.write("### 演奏曲目 シートの列名", df_songs.columns.tolist())
    st.write("### ライブ一覧 シートの列名", df_lives.columns.tolist())

# 必須列のマッピングと欠損補完
# 1. 演奏曲目
C_SONG = ensure_col(df_songs, ["楽曲名", "曲名", "Song"])
C_TIME = ensure_col(df_songs, ["演奏時間（平均）", "平均演奏時間", "演奏時間", "Time"], fallback_val="0")
C_VOCAL = ensure_col(df_songs, ["ボーカル", "Vocal", "唄"])
C_ORDER = ensure_col(df_songs, ["演奏順", "No", "順序", "Order"], fallback_val="0")
C_LIVE_LINK = ensure_col(df_songs, ["ライブ名", "Live", "公演名"])
C_YT_ID = ensure_col(df_songs, ["YOUTUBE_ID", "Youtube", "VideoID"])
C_START = ensure_col(df_songs, ["STARTTIME", "開始時間", "Start"], fallback_val="0")
C_LAST = ensure_col(df_songs, ["ラスト", "演奏番号", "Key", "前回"], fallback_val="-")

# 2. ライブ一覧
L_DATE = ensure_col(df_lives, ["日付", "Date", "開催日"])
L_VENUE = ensure_col(df_lives, ["会場名", "会場", "Venue", "場所"])
L_LIVE_NAME = ensure_col(df_lives, ["ライブ名", "Live", "名称"])
L_STATUS = ensure_col(df_lives, ["STATUS", "状態", "ステータス"], fallback_val="済")

# --- Sidebar Navigation ---
st.sidebar.title("VSOP Live Dashboard")
menu = st.sidebar.radio("メニュー", ["🏠 楽曲一覧・分析", "📅 ライブ明細検索", "🚀 次回演奏予定"])

# --- 1. 楽曲一覧・分析 ---
if menu == "🏠 楽曲一覧・分析":
    st.title("🎵 楽曲ランキング & 分析")
    
    # 楽曲ごとの集計
    try:
        song_stats = df_songs.groupby(C_SONG).agg({
            C_TIME: 'first',
            C_VOCAL: 'first',
            C_SONG: 'count'
        }).rename(columns={C_SONG: '演奏合計回数'}).reset_index()
        
        song_stats = song_stats.sort_values('演奏合計回数', ascending=False)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("総楽曲数", len(song_stats))
        
        if not song_stats.empty:
            col2.metric("最多演奏曲", song_stats.iloc[0][C_SONG])
            col3.metric("最大演奏回数", song_stats.iloc[0]['演奏合計回数'])
        
        st.subheader("演奏回数ランキング")
        # 仮想列が使われている場合は注釈を入れる
        if "(仮想)" in C_TIME:
            st.caption("※スプレッドシートに『演奏時間』列が見つからないため、現在は表示していません。")
            
        st.dataframe(
            song_stats[[C_SONG, '演奏合計回数', C_TIME, C_VOCAL]],
            use_container_width=True,
            hide_index=True
        )
    except Exception as e:
        st.error(f"分析表示エラー: {e}")

# --- 2. ライブ明細検索 ---
elif menu == "📅 ライブ明細検索":
    st.title("📅 過去のライブを探す")
    
    search_query = st.text_input("会場名や年月で検索 (部分一致)")
    
    filtered_lives = df_lives.copy()
    if search_query:
        mask = (
            filtered_lives[L_VENUE].astype(str).str.contains(search_query, case=False, na=False) |
            filtered_lives[L_DATE].astype(str).str.contains(search_query, case=False, na=False)
        )
        filtered_lives = filtered_lives[mask]
    
    if filtered_lives.empty:
        st.warning("条件に一致するライブが見つかりません。")
    else:
        filtered_lives['label'] = filtered_lives[L_DATE].astype(str) + " @ " + filtered_lives[L_VENUE].astype(str)
        live_options = filtered_lives['label'].tolist()
        selected_live_str = st.selectbox("ライブを選択してください", live_options)
        
        selected_live = filtered_lives[filtered_lives['label'] == selected_live_str].iloc[0]
        
        st.divider()
        st.header(f"🎸 {selected_live[L_VENUE]}")
        st.info(f"開催日: {selected_live[L_DATE]}")
        
        # セットリスト抽出
        live_songs = df_songs[df_songs[C_LIVE_LINK] == selected_live[L_LIVE_NAME]]
        if "(仮想)" not in C_ORDER:
            live_songs = live_songs.sort_values(C_ORDER)
        
        if live_songs.empty:
            st.write("セットリスト情報がありません。")
        else:
            for _, row in live_songs.iterrows():
                yt_id = row[C_YT_ID] if row[C_YT_ID] != "-" else ""
                try:
                    start = int(float(str(row[C_START]).replace("-", "0")))
                except:
                    start = 0
                yt_link = f"https://youtu.be/{yt_id}?t={start}" if yt_id else "#"
                
                with st.container():
                    prefix = f"{row[C_ORDER]}. " if "(仮想)" not in C_ORDER else ""
                    st.markdown(f"""
                    <div class="song-card">
                        <div class="song-title">{prefix}{row[C_SONG]}</div>
                        <div class="song-meta">Vocal: {row[C_VOCAL]}</div>
                        <a href="{yt_link}" target="_blank" class="youtube-link">▶️ YouTubeで再生 ({start}秒から)</a>
                    </div>
                    """, unsafe_allow_html=True)

# --- 3. 次回演奏予定 ---
elif menu == "🚀 次回演奏予定":
    st.title("🚀 Next Performance Info")
    
    upcoming_lives = df_lives[df_lives[L_STATUS].astype(str).str.contains('未', na=False)]
    if "(仮想)" not in L_DATE:
        upcoming_lives = upcoming_lives.sort_values(L_DATE)
    
    if upcoming_lives.empty:
        st.success("現在、予定されているライブはありません。")
    else:
        display_cols = [c for c in [L_DATE, L_LIVE_NAME, L_VENUE] if "(仮想)" not in c]
        st.subheader("次回ライブ予定一覧")
        st.dataframe(upcoming_lives[display_cols], use_container_width=True, hide_index=True)
        
        selected_next = st.selectbox("詳細を見るライブ", upcoming_lives[L_LIVE_NAME].tolist())
        
        next_setlist = df_songs[df_songs[C_LIVE_LINK] == selected_next]
        if "(仮想)" not in C_ORDER:
            next_setlist = next_setlist.sort_values(C_ORDER)
        
        st.header(f"📝 Setlist: {selected_next}")
        
        if next_setlist.empty:
            st.write("このライブのセットリストはまだ登録されていません。")
        else:
            for _, song in next_setlist.iterrows():
                col1, col2 = st.columns([1, 1])
                with col1:
                    prefix = f"{song[C_ORDER]}. " if "(仮想)" not in C_ORDER else ""
                    st.markdown(f"""
                    <div class="song-card">
                        <div class="song-title">{prefix}{song[C_SONG]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    last_val = str(song[C_LAST])
                    if last_val and last_val not in ["nan", "-", "0", ""]:
                        past_perf = df_songs[
                            (df_songs[C_LAST].astype(str) == last_val) & 
                            (df_songs[C_LIVE_LINK] != selected_next)
                        ].head(1)
                        
                        if not past_perf.empty:
                            p_row = past_perf.iloc[0]
                            p_yt = p_row[C_YT_ID] if p_row[C_YT_ID] != "-" else ""
                            try:
                                p_start = int(float(str(p_row[C_START]).replace("-", "0")))
                            except:
                                p_start = 0
                            p_url = f"https://youtu.be/{p_yt}?t={p_start}"
                            st.markdown(f"**📚 前回演奏時**")
                            st.markdown(f"[{p_row[C_LIVE_LINK]} の映像]({p_url})")
                        else:
                            st.write("前回演奏データなし")
                    else:
                        st.write("-")

st.sidebar.divider()
st.sidebar.caption("© 2024 VSOP Live Support System")
