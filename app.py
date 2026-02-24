import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import datetime

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

# --- Data Connection ---
def load_data():
    # Secrets の [connections.gsheets] から自動的に認証情報と
    # スプレッドシートのURL(spreadsheet = "...")を読み込みます
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # スプレッドシート内の各シートを読み込み
    df_songs = conn.read(worksheet="演奏曲目")
    df_lives = conn.read(worksheet="ライブ一覧")
    
    # 型変換などの前処理
    if 'STARTTIME' in df_songs.columns:
        df_songs['STARTTIME'] = pd.to_numeric(df_songs['STARTTIME'], errors='coerce').fillna(0).astype(int)
    
    return df_songs, df_lives

try:
    df_songs, df_lives = load_data()
except Exception as e:
    st.error(f"データ読み込みエラー: {e}")
    st.info("st.secrets に Google Cloud サービスアカウント情報とスプレッドシートの接続情報が正しく設定されているか確認してください。")
    st.stop()

# --- Sidebar Navigation ---
st.sidebar.title("VSOP Live Dashboard")
menu = st.sidebar.radio("メニュー", ["🏠 楽曲一覧・分析", "📅 ライブ明細検索", "🚀 次回演奏予定"])

# --- 1. 楽曲一覧・分析 ---
if menu == "🏠 楽曲一覧・分析":
    st.title("🎵 楽曲ランキング & 分析")
    
    # 楽曲ごとの集計
    song_stats = df_songs.groupby('楽曲名').agg({
        '演奏時間（平均）': 'first',
        'ボーカル': 'first',
        '楽曲名': 'count'
    }).rename(columns={'楽曲名': '演奏合計回数'}).reset_index()
    
    song_stats = song_stats.sort_values('演奏合計回数', ascending=False)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("総楽曲数", len(song_stats))
    col2.metric("最多演奏曲", song_stats.iloc[0]['楽曲名'])
    col3.metric("最大演奏回数", song_stats.iloc[0]['演奏合計回数'])
    
    st.subheader("演奏回数ランキング")
    st.dataframe(
        song_stats[['楽曲名', '演奏合計回数', '演奏時間（平均）', 'ボーカル']],
        use_container_width=True,
        hide_index=True
    )

# --- 2. ライブ明細検索 ---
elif menu == "📅 ライブ明細検索":
    st.title("📅 過去のライブを探す")
    
    # 検索フィルター
    search_query = st.text_input("会場名や年月で検索 (部分一致)")
    
    filtered_lives = df_lives.copy()
    if search_query:
        # 日付を文字列として検索対象に含める
        filtered_lives['search_text'] = filtered_lives.apply(lambda x: f"{x['日付']} {x['会場名']}", axis=1)
        filtered_lives = filtered_lives[filtered_lives['search_text'].str.contains(search_query, case=False, na=False)]
    
    if filtered_lives.empty:
        st.warning("条件に一致するライブが見つかりません。")
    else:
        # ライブ選択
        live_options = filtered_lives.apply(lambda x: f"{x['日付']} @ {x['会場名']}", axis=1).tolist()
        selected_live_str = st.selectbox("ライブを選択してください", live_options)
        
        # 選択されたライブの情報を特定
        selected_live_idx = live_options.index(selected_live_str)
        selected_live = filtered_lives.iloc[selected_live_idx]
        
        st.divider()
        st.header(f"🎸 {selected_live['会場名']}")
        st.info(f"開催日: {selected_live['日付']}")
        
        # 該当ライブのセットリストを抽出
        # ライブ名またはIDで紐付け（ここでは仮に「ライブ名」で紐付け）
        live_songs = df_songs[df_songs['ライブ名'] == selected_live['ライブ名']].sort_values('演奏順')
        
        if live_songs.empty:
            st.write("セットリスト情報がありません。")
        else:
            for _, row in live_songs.iterrows():
                youtube_id = row.get('YOUTUBE_ID', '') # YOUTUBE_ID列がある想定
                starttime = row.get('STARTTIME', 0)
                yt_link = f"https://youtu.be/{youtube_id}?t={starttime}" if youtube_id else "#"
                
                with st.container():
                    st.markdown(f"""
                    <div class="song-card">
                        <div class="song-title">{row['演奏順']}. {row['楽曲名']}</div>
                        <div class="song-meta">Vocal: {row['ボーカル']} | 演奏時間: {row.get('演奏時間', '不明')}</div>
                        <a href="{yt_link}" target="_blank" class="youtube-link">▶️ YouTubeで再生 ({starttime}秒から)</a>
                    </div>
                    """, unsafe_allow_html=True)

# --- 3. 次回演奏予定 ---
elif menu == "🚀 次回演奏予定":
    st.title("🚀 Next Performance Info")
    
    # STATUSが「未」のものを抽出
    upcoming_lives = df_lives[df_lives['STATUS'] == '未'].sort_values('日付')
    
    if upcoming_lives.empty:
        st.success("現在、予定されているライブはありません。")
    else:
        st.subheader("次回ライブ予定一覧")
        st.dataframe(
            upcoming_lives[['日付', 'ライブ名', '会場名']],
            use_container_width=True,
            hide_index=True
        )
        
        selected_next = st.selectbox("詳細を見るライブ", upcoming_lives['ライブ名'].tolist())
        
        # 次回ライブのセットリスト
        next_setlist = df_songs[df_songs['ライブ名'] == selected_next].sort_values('演奏順')
        
        st.header(f"📝 Setlist: {selected_next}")
        
        for _, song in next_setlist.iterrows():
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown(f"""
                <div class="song-card">
                    <div class="song-title">{song['演奏順']}. {song['楽曲名']}</div>
                    <div class="song-meta">Vocal: {song['ボーカル']}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                # 予習用動画の検索
                last_key = str(song.get('ラスト', ''))
                if last_key and last_key != 'nan':
                    # 同一シート（df_songs）内の過去の同じ演奏番号を検索
                    # 自分自身（今回のライブ）を除外
                    past_perf = df_songs[
                        (df_songs['ラスト'].astype(str) == last_key) & 
                        (df_songs['ライブ名'] != selected_next)
                    ].iloc[:1] # 最初に見つかった1件
                    
                    if not past_perf.empty:
                        past_row = past_perf.iloc[0]
                        past_yt_id = past_row.get('YOUTUBE_ID', '')
                        past_start = past_row.get('STARTTIME', 0)
                        past_yt_url = f"https://youtu.be/{past_yt_id}?t={past_start}"
                        
                        st.markdown(f"**📚 前回演奏時 (予習用)**")
                        st.markdown(f"[{past_row['ライブ名']} の映像]({past_yt_url})")
                    else:
                        st.write("前回演奏データなし")
                else:
                    st.write("-")

st.sidebar.divider()
st.sidebar.caption("© 2024 VSOP Live Support System")
