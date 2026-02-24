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

# --- ユーティリティ: 列名の柔軟なマッチング ---
def get_flexible_col(df, target_names):
    """
    dfの列名から target_names (リスト) に含まれるか、あるいはそれに近い名前を探す
    """
    actual_cols = df.columns.tolist()
    # 1. 完全一致 (または strip後の一致)
    for target in target_names:
        if target in actual_cols:
            return target
    
    # 2. 部分一致 (targetが列名に含まれているか、列名がtargetに含まれているか)
    for target in target_names:
        for col in actual_cols:
            if target in col or col in target:
                return col
    return None

# --- Data Connection ---
def load_data():
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
                df[col] = df[col].astype(str).fillna("-")
    
    return df_songs, df_lives

# --- データ読み込みとデバッグ表示 ---
try:
    df_songs, df_lives = load_data()
    
    # 画面トップでのデバッグ表示 (KeyError解決用)
    with st.expander("🛠️ 【デバッグ】スプレッドシートの列名を確認する"):
        st.write("### 演奏曲目 シートの列名")
        st.write(df_songs.columns.tolist())
        st.write("### ライブ一覧 シートの列名")
        st.write(df_lives.columns.tolist())
        st.info("※列名が合わない場合は、以下のロジックで自動的にマッチングを試みています。")

except Exception as e:
    st.error(f"データ読み込みエラー: {e}")
    st.stop()

# --- Sidebar Navigation ---
st.sidebar.title("VSOP Live Dashboard")
menu = st.sidebar.radio("メニュー", ["🏠 楽曲一覧・分析", "📅 ライブ明細検索", "🚀 次回演奏予定"])

# --- 1. 楽曲一覧・分析 ---
if menu == "🏠 楽曲一覧・分析":
    st.title("🎵 楽曲ランキング & 分析")
    
    # 列名の柔軟な取得
    col_song = get_flexible_col(df_songs, ["楽曲名", "曲名", "Song"])
    col_time = get_flexible_col(df_songs, ["演奏時間（平均）", "平均演奏時間", "演奏時間", "Time"])
    col_vocal = get_flexible_col(df_songs, ["ボーカル", "Vocal", "唄"])
    
    if not all([col_song, col_time, col_vocal]):
        st.error(f"必須列が見つかりません。デバッグ情報を確認してください。(楽曲名:{col_song}, 演奏時間:{col_time}, ボーカル:{col_vocal})")
    else:
        # 楽曲ごとの集計
        song_stats = df_songs.groupby(col_song).agg({
            col_time: 'first',
            col_vocal: 'first',
            col_song: 'count'
        }).rename(columns={col_song: '演奏合計回数'}).reset_index()
        
        song_stats = song_stats.sort_values('演奏合計回数', ascending=False)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("総楽曲数", len(song_stats))
        
        if not song_stats.empty:
            col2.metric("最多演奏曲", song_stats.iloc[0][col_song])
            col3.metric("最大演奏回数", song_stats.iloc[0]['演奏合計回数'])
        
        st.subheader("演奏回数ランキング")
        st.dataframe(
            song_stats[[col_song, '演奏合計回数', col_time, col_vocal]],
            use_container_width=True,
            hide_index=True
        )

# --- 2. ライブ明細検索 ---
elif menu == "📅 ライブ明細検索":
    st.title("📅 過去のライブを探す")
    
    col_date = get_flexible_col(df_lives, ["日付", "Date", "開催日"])
    col_venue = get_flexible_col(df_lives, ["会場名", "会場", "Venue", "場所"])
    col_live_name = get_flexible_col(df_lives, ["ライブ名", "Live", "名称"])
    
    if not all([col_date, col_venue, col_live_name]):
        st.error(f"『ライブ一覧』に必要な列が見つかりません。(日付:{col_date}, 会場:{col_venue}, ライブ名:{col_live_name})")
    else:
        search_query = st.text_input("会場名や年月で検索 (部分一致)")
        
        filtered_lives = df_lives.copy()
        if search_query:
            mask = (
                filtered_lives[col_venue].astype(str).str.contains(search_query, case=False, na=False) |
                filtered_lives[col_date].astype(str).str.contains(search_query, case=False, na=False)
            )
            filtered_lives = filtered_lives[mask]
        
        if filtered_lives.empty:
            st.warning("条件に一致するライブが見つかりません。")
        else:
            filtered_lives['label'] = filtered_lives[col_date].astype(str) + " @ " + filtered_lives[col_venue].astype(str)
            live_options = filtered_lives['label'].tolist()
            selected_live_str = st.selectbox("ライブを選択してください", live_options)
            
            selected_live = filtered_lives[filtered_lives['label'] == selected_live_str].iloc[0]
            
            st.divider()
            st.header(f"🎸 {selected_live[col_venue]}")
            st.info(f"開催日: {selected_live[col_date]}")
            
            # セットリスト表示用の列
            col_song_s = get_flexible_col(df_songs, ["楽曲名", "曲名"])
            col_order = get_flexible_col(df_songs, ["演奏順", "No", "順序"])
            col_live_link = get_flexible_col(df_songs, ["ライブ名", "Live"])
            
            live_songs = df_songs[df_songs[col_live_link] == selected_live[col_live_name]]
            if col_order:
                live_songs = live_songs.sort_values(col_order)
            
            if live_songs.empty:
                st.write("セットリスト情報がありません。")
            else:
                for _, row in live_songs.iterrows():
                    yt_id = row.get('YOUTUBE_ID', '')
                    start = row.get('STARTTIME', 0)
                    try:
                        start = int(float(start))
                    except:
                        start = 0
                    yt_link = f"https://youtu.be/{yt_id}?t={start}" if yt_id else "#"
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="song-card">
                            <div class="song-title">{row.get(col_order, '')}. {row[col_song_s]}</div>
                            <div class="song-meta">Vocal: {row.get('ボーカル', '-')}</div>
                            <a href="{yt_link}" target="_blank" class="youtube-link">▶️ YouTubeで再生 ({start}秒から)</a>
                        </div>
                        """, unsafe_allow_html=True)

# --- 3. 次回演奏予定 ---
elif menu == "🚀 次回演奏予定":
    st.title("🚀 Next Performance Info")
    
    col_status = get_flexible_col(df_lives, ["STATUS", "状態", "ステータス"])
    col_date = get_flexible_col(df_lives, ["日付", "Date"])
    col_live_name = get_flexible_col(df_lives, ["ライブ名", "Live"])
    col_venue = get_flexible_col(df_lives, ["会場名", "Venue"])
    
    if not col_status:
        st.error("『STATUS』列が見つかりません。")
    else:
        upcoming_lives = df_lives[df_lives[col_status].astype(str).str.contains('未', na=False)]
        if col_date:
            upcoming_lives = upcoming_lives.sort_values(col_date)
        
        if upcoming_lives.empty:
            st.success("現在、予定されているライブはありません。")
        else:
            display_cols = [c for c in [col_date, col_live_name, col_venue] if c]
            st.subheader("次回ライブ予定一覧")
            st.dataframe(upcoming_lives[display_cols], use_container_width=True, hide_index=True)
            
            selected_next = st.selectbox("詳細を見るライブ", upcoming_lives[col_live_name].tolist())
            
            col_live_link = get_flexible_col(df_songs, ["ライブ名", "Live"])
            col_order = get_flexible_col(df_songs, ["演奏順", "No"])
            col_song_name = get_flexible_col(df_songs, ["楽曲名", "曲名"])
            col_last = get_flexible_col(df_songs, ["ラスト", "演奏番号", "Key"])
            
            next_setlist = df_songs[df_songs[col_live_link] == selected_next]
            if col_order:
                next_setlist = next_setlist.sort_values(col_order)
            
            st.header(f"📝 Setlist: {selected_next}")
            
            for _, song in next_setlist.iterrows():
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.markdown(f"""
                    <div class="song-card">
                        <div class="song-title">{song.get(col_order, '')}. {song[col_song_name]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    last_val = str(song.get(col_last, ''))
                    if col_last and last_val and last_val != 'nan' and last_val != '-':
                        past_perf = df_songs[
                            (df_songs[col_last].astype(str) == last_val) & 
                            (df_songs[col_live_link] != selected_next)
                        ].head(1)
                        
                        if not past_perf.empty:
                            p_row = past_perf.iloc[0]
                            p_yt = p_row.get('YOUTUBE_ID', '')
                            p_start = p_row.get('STARTTIME', 0)
                            p_url = f"https://youtu.be/{p_yt}?t={p_start}"
                            st.markdown(f"**📚 前回演奏時**")
                            st.markdown(f"[{p_row[col_live_link]} の映像]({p_url})")
                        else:
                            st.write("前回演奏データなし")
                    else:
                        st.write("-")

st.sidebar.divider()
st.sidebar.caption("© 2024 VSOP Live Support System")
