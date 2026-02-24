import streamlit as st
import pandas as pd
import datetime
import urllib.parse

# --- ユーティリティ: データ処理と防御的処理 ---
def get_flexible_col(df, target_names, default=None):
    """
    dfの列名から target_names に含まれるか、あるいはそれに近い名前を探す。
    ただし、「翻訳」という文字が含まれる列は、target自身に「翻訳」が入っていない限り避ける。
    """
    actual_cols = df.columns.tolist()
    
    # 1. 完全一致 (大文字小文字無視)
    for target in target_names:
        for col in actual_cols:
            if target.lower() == col.lower():
                return col
                
    # 2. 部分一致 (かつ「翻訳」を含まないものを優先)
    for target in target_names:
        for col in actual_cols:
            if target in col and "翻訳" not in col:
                return col
                
    # 3. それでも見つからない場合の最終手段 (「翻訳」を含んでいても良い)
    for target in target_names:
        for col in actual_cols:
            if target in col:
                return col
    return default

def ensure_col(df, target_names, fallback_val=""):
    col = get_flexible_col(df, target_names)
    if col is None:
        virtual_name = target_names[0] + " (仮想)"
        df[virtual_name] = fallback_val
        return virtual_name
    return col

def make_youtube_url(val, start_time=0):
    """
    ID単体、短縮URL、フルURLすべてを許容して正しい再生URLを構築する
    """
    if not val or val == "-" or str(val).lower() == "nan":
        return "#"
    
    val_str = str(val).strip()
    
    # すでにURL（http...）の場合は、ID部分を抽出するか、そのまま使う
    # 最も確実なのは、IDっぽい部分を正規表現等で抜くことだが、
    # 簡易的に、すでにURLならそのURLをベースにし、StartTimeを付与する
    if "youtube.com" in val_str or "youtu.be" in val_str:
        # IDを抽出
        if "v=" in val_str:
            yt_id = val_str.split("v=")[1].split("&")[0]
        elif "youtu.be/" in val_str:
            yt_id = val_str.split("youtu.be/")[1].split("?")[0]
        else:
            # それ以外はそのまま返して t= を付ける
            sep = "&" if "?" in val_str else "?"
            return f"{val_str}{sep}t={start_time}s"
    else:
        yt_id = val_str
        
    return f"https://www.youtube.com/watch?v={yt_id}&t={start_time}s"

# --- Page Configuration ---
st.set_page_config(
    page_title="VSOP Live Dashboard",
    page_icon="🎸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Browser Translation Prevention & Custom CSS ---
st.markdown("""
<html class="notranslate" google="notranslate">
<style>
    /* ブラウザ翻訳を無効化するスタイル */
    .main, .stApp, div, span, a {
        unicode-bidi: isolate;
    }
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .song-card { background-color: #1e2130; padding: 20px; border-radius: 15px; margin-bottom: 15px; border-left: 5px solid #ff4b4b; }
    .song-title { font-size: 1.2rem; font-weight: bold; color: #ffffff; }
    .song-meta { font-size: 0.9rem; color: #a0a0a0; }
    .youtube-link { color: #ffffff !important; text-decoration: none !important; font-weight: bold; }
    .youtube-link:hover { text-decoration: underline !important; color: #ff4b4b !important; }
    h1, h2, h3 { color: #f0f2f6; }
</style>
</html>
<script>
    // ブラウザ翻訳を抑制するためのダミー属性付与
    document.documentElement.className += ' notranslate';
    document.documentElement.setAttribute('translate', 'no');
</script>
""", unsafe_allow_html=True)

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
C_TIME = ensure_col(df_songs, ["演奏時間", "演奏時間（平均）", "平均演奏時間", "Time"], fallback_val="0")
C_VOCAL = ensure_col(df_songs, ["ボーカル", "Vocal", "唄"])
C_ORDER = ensure_col(df_songs, ["演奏番号", "演奏順", "No", "順序", "Order"], fallback_val="0")
C_LIVE_LINK = ensure_col(df_songs, ["ライブ番号", "ID", "ライブ名", "Live", "公演名"]) # ライブ番号を優先
C_YT_ID = ensure_col(df_songs, ["YOUTUBE_ID", "Youtube", "VideoID", "動画ID"])
C_START = ensure_col(df_songs, ["STARTTIME", "開始時間", "Start"], fallback_val="0")
C_LAST = ensure_col(df_songs, ["ラスト", "前回", "Key"], fallback_val="-")

# 2. ライブ一覧
L_DATE = ensure_col(df_lives, ["日付", "Date", "開催日"])
L_VENUE = ensure_col(df_lives, ["会場名", "会場", "Venue", "場所"])
L_LIVE_NAME = ensure_col(df_lives, ["ライブ番号", "ID", "ライブ名", "Live", "名称"]) # ライブ番号を優先
L_LIVE_TITLE = ensure_col(df_lives, ["ライブ名", "Live", "公演名", "名称"]) # 表示用の名前
L_STATUS = ensure_col(df_lives, ["STATUS", "状態", "ステータス"], fallback_val="済")

# --- Sidebar Navigation ---
st.sidebar.title("VSOP Live Dashboard")
menu = st.sidebar.radio("メニュー", ["🏠 楽曲一覧・分析", "📅 ライブ明細検索", "🚀 次回演奏予定"])

# --- 1. 楽曲一覧・分析 ---
if menu == "🏠 楽曲一覧・分析":
    st.title("🎵 楽曲ランキング & 分析")
    
    # 楽曲ごとの集計
    try:
        # ランキングでは「演奏時間（平均）」に近いものを使うが、見つからない場合は0として扱う
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
        # 仮想列が使われている（＝演奏時間列が実質ない）場合は 0 扱いで表示
        if "(仮想)" in C_TIME:
            st.caption("※スプレッドシートに『演奏時間』列が見つからないため、時間項目は 0 として処理されています。")
            
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
        st.info(f"開催日: {selected_live[L_DATE]} | {selected_live[L_LIVE_TITLE]}")
        
        # セットリスト抽出 (ライブ番号/IDで紐付け)
        live_songs = df_songs[df_songs[C_LIVE_LINK].astype(str) == str(selected_live[L_LIVE_NAME])]
        
        # 演奏番号でソート
        if "(仮想)" not in C_ORDER:
            # 数字としてソートを試みる
            live_songs[C_ORDER] = pd.to_numeric(live_songs[C_ORDER], errors='coerce').fillna(999)
            live_songs = live_songs.sort_values(C_ORDER)
        
        if live_songs.empty:
            st.write("セットリスト情報がありません。")
        else:
            for _, row in live_songs.iterrows():
                try:
                    start = int(float(str(row[C_START]).replace("-", "0")))
                except:
                    start = 0
                yt_link = make_youtube_url(row[C_YT_ID], start)
                
                with st.container():
                    # 数値として確実に表示 (ブラウザが . を勝手に翻訳して 。 にするのを防ぐ)
                    try:
                        raw_order = float(str(row[C_ORDER]))
                        display_order = str(int(raw_order)) if not pd.isna(raw_order) and raw_order != 999 else "-"
                    except:
                        display_order = "-"
                        
                    link_html = f'<a href="{yt_link}" target="_blank" class="youtube-link notranslate" translate="no">{row[C_SONG]}</a>' if yt_link != "#" else f'<span class="notranslate" translate="no">{row[C_SONG]}</span>'
                    st.markdown(f"""
                    <div class="song-card notranslate" translate="no">
                        <div class="song-title" translate="no">
                            <span class="notranslate" translate="no">{display_order}.</span> {link_html}
                        </div>
                        <div class="song-meta notranslate" translate="no">
                            Vocal: {row[C_VOCAL]} | 演奏時間: {row[C_TIME]}
                        </div>
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
        display_cols = [c for c in [L_DATE, L_LIVE_TITLE, L_VENUE] if "(仮想)" not in c]
        st.subheader("次回ライブ予定一覧")
        st.dataframe(upcoming_lives[display_cols], use_container_width=True, hide_index=True)
        
        live_titles = upcoming_lives[L_LIVE_TITLE].tolist()
        selected_title = st.selectbox("詳細を見るライブ", live_titles)
        
        selected_live_info = upcoming_lives[upcoming_lives[L_LIVE_TITLE] == selected_title].iloc[0]
        selected_id = selected_live_info[L_LIVE_NAME]
        
        # セットリスト抽出
        next_setlist = df_songs[df_songs[C_LIVE_LINK].astype(str) == str(selected_id)]
        if "(仮想)" not in C_ORDER:
            next_setlist[C_ORDER] = pd.to_numeric(next_setlist[C_ORDER], errors='coerce').fillna(999)
            next_setlist = next_setlist.sort_values(C_ORDER)
        
        st.header(f"📝 Setlist: {selected_title}")
        
        if next_setlist.empty:
            st.write("このライブのセットリストはまだ登録されていません。")
        else:
            for _, song in next_setlist.iterrows():
                col1, col2 = st.columns([1, 1])
                with col1:
                    try:
                        raw_order = float(str(song[C_ORDER]))
                        display_order = str(int(raw_order)) if not pd.isna(raw_order) and raw_order != 999 else "-"
                    except:
                        display_order = "-"
                        
                    st.markdown(f"""
                    <div class="song-card notranslate" translate="no">
                        <div class="song-title" translate="no">
                            <span class="notranslate" translate="no">{display_order}.</span> {song[C_SONG]}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # 予習用（前回）: 今の曲の「ラスト」の値を、全体の「演奏番号」から探す
                    last_val = str(song[C_LAST])
                    if last_val and last_val not in ["nan", "-", "0", ""]:
                        # 検索！ 楽曲シートの「演奏番号」列が、今の曲の「ラスト」と一致するものを探す
                        # (自分自身の今回のライブ ID は除外)
                        past_perf = df_songs[
                            (df_songs[C_ORDER].astype(str) == last_val) & 
                            (df_songs[C_LIVE_LINK].astype(str) != str(selected_id))
                        ].head(1)
                        
                        if not past_perf.empty:
                            p_row = past_perf.iloc[0]
                            try:
                                p_start = int(float(str(p_row[C_START]).replace("-", "0")))
                            except:
                                p_start = 0
                            p_url = make_youtube_url(p_row[C_YT_ID], p_start)
                            st.markdown(f"**📚 前回演奏時**")
                            if p_url != "#":
                                st.markdown(f"[{p_row[C_LIVE_LINK]} の映像]({p_url})")
                            else:
                                st.write(f"{p_row[C_LIVE_LINK]} (映像なし)")
                        else:
                            st.write("前回演奏データなし")
                    else:
                        st.write("-")

st.sidebar.divider()
st.sidebar.caption("© 2024 VSOP Live Support System")
