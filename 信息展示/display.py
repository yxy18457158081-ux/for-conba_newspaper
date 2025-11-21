import streamlit as st
import json
import re
from datetime import datetime

# -------------------------- 配置 --------------------------
STORAGE_FILE = "email_data.json"
REFRESH_INTERVAL = 30 * 60  # 自动刷新间隔（秒）
PAGE_SIZE = 10  # 每页显示条数
CUSTOM_CSS = """
<style>
    .main-header {font-size: 2.5rem; color: #1E40AF; text-align: center; margin-bottom: 1.5rem;}
    .card {background: white; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1);}
    .card-header {display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;}
    .card-title {font-size: 1.2rem; font-weight: bold; color: #1E3A8A;}
    .card-time {font-size: 0.9rem; color: #64748B;}
    .card-content {font-size: 1rem; line-height: 1.6; color: #334155; white-space: pre-wrap;}
    
    /* 分页核心样式 */
    .pagination-container {display: flex; justify-content: center; align-items: center; margin: 2rem 0; gap: 0.8rem;}
    .page-btn {
        padding: 0.6rem 1.2rem;
        border-radius: 6px;
        border: none;
        cursor: pointer;
        font-size: 0.95rem;
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        gap: 0.3rem;
    }
    /* 上一页/下一页按钮 */
    .prev-next {
        background-color: #f1f5f9;
        color: #334155;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .prev-next:hover {
        background-color: #e2e8f0;
        transform: translateY(-1px);
    }
    .prev-next:disabled {
        background-color: #f8fafc;
        color: #94a3b8;
        cursor: not-allowed;
        transform: none;
    }
    /* 页码按钮 */
    .page-number {
        background-color: #ffffff;
        color: #334155;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        width: 2.5rem;
        height: 2.5rem;
        padding: 0;
        justify-content: center;
    }
    .page-number:hover {
        background-color: #f1f5f9;
        transform: translateY(-1px);
    }
    /* 当前页高亮 */
    .page-number.active {
        background-color: #1E40AF;
        color: white;
        box-shadow: 0 2px 5px rgba(30, 64, 175, 0.3);
    }
    .page-number.active:hover {
        background-color: #1E40AF;
        transform: none;
    }
</style>
"""
# ----------------------------------------------------------

def load_stored_data():
    """读取存储的邮件内容"""
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def extract_date_from_subject(subject):
    """从邮件标题中提取日期（格式：YYYY-MM-DD）"""
    match = re.search(r"\d{4}-\d{2}-\d{2}", subject)
    if match:
        date_str = match.group()
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return datetime(1970, 1, 1)
    return datetime(1970, 1, 1)

def main():
    st.set_page_config(page_title="康恩贝行业信息简报", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    # 初始化页码状态
    if "current_page" not in st.session_state:
        st.session_state.current_page = 1

    # 标题
    st.markdown('<h1 class="main-header">📊 康恩贝内部行业信息简报</h1>', unsafe_allow_html=True)
    st.markdown("---")
    st.write("基于标题中的日期，最新简报将优先显示👇")
    
    # 加载数据
    email_data = load_stored_data()
    if not email_data:
        st.info("暂无数据，等待邮件获取任务执行后刷新...")
        return
    
    # 排序（按标题日期倒序）
    email_data.sort(
        key=lambda x: extract_date_from_subject(x["subject"]),
        reverse=True
    )
    
    # 提取日期筛选选项
    all_dates = list({extract_date_from_subject(item["subject"]).strftime("%Y-%m-%d") 
                     for item in email_data 
                     if extract_date_from_subject(item["subject"]) != datetime(1970, 1, 1)})
    all_dates.sort(reverse=True)
    
    # 搜索和筛选
    col1, col2 = st.columns([3, 1])
    with col1:
        search_keyword = st.text_input("🔍 搜索关键词", placeholder="输入关键词...", key="search").lower()
    with col2:
        selected_date = st.selectbox("📅 筛选日期", ["全部日期"] + all_dates, key="date_filter")
    
    # 筛选数据
    filtered_data = [
        item for item in email_data
        if (selected_date == "全部日期" or 
            extract_date_from_subject(item["subject"]).strftime("%Y-%m-%d") == selected_date)
        and (not search_keyword or 
             search_keyword in item["subject"].lower() or 
             search_keyword in item["content"].lower())
    ]
    total = len(filtered_data)
    st.write(f"📌 共找到 {total} 条记录（{selected_date if selected_date != '全部日期' else '所有日期'}）")
    st.markdown("---")
    
    # 分页逻辑
    if total > 0:
        total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        current_page = st.session_state.current_page
        
        # 限制页码范围
        current_page = max(1, min(current_page, total_pages))
        st.session_state.current_page = current_page

        # 当前页数据
        start = (current_page - 1) * PAGE_SIZE
        end = min(start + PAGE_SIZE, total)
        current_data = filtered_data[start:end]

        # 显示当前页内容
        for idx, item in enumerate(current_data, start + 1):
            with st.container():
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown(f'''
                    <div class="card-header">
                        <div class="card-title">【{idx}】{item["subject"]}</div>
                        <div class="card-time">提取日期：{extract_date_from_subject(item["subject"]).strftime("%Y-%m-%d")}</div>
                    </div>
                ''', unsafe_allow_html=True)
                with st.expander("查看详情", expanded=False):
                    st.markdown(f'<div class="card-content">{item["content"].replace("\n", "<br>")}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

        # 分页状态提示
        st.caption(f"当前显示第 {start + 1}-{end} 条，共 {total} 条 | 第 {current_page}/{total_pages} 页")

        # 生成分页按钮列表（最多显示5个页码，保持简洁）
        show_pages = []
        if total_pages <= 5:
            show_pages = list(range(1, total_pages + 1))
        else:
            if current_page <= 3:
                show_pages = [1, 2, 3, 4, 5]
            elif current_page >= total_pages - 2:
                show_pages = [total_pages - 4, total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
            else:
                show_pages = [current_page - 2, current_page - 1, current_page, current_page + 1, current_page + 2]

        # 横向分页控件（用columns确保在同一行）
        st.markdown('<div class="pagination-container">', unsafe_allow_html=True)
        
        # 上一页按钮
        cols = st.columns(len(show_pages) + 2)  # +2 留位置给上一页和下一页
        with cols[0]:
            st.button(
                "← 上一页",
                on_click=lambda: setattr(st.session_state, "current_page", current_page - 1),
                disabled=current_page == 1,
                key="prev",
                use_container_width=True
            )
        
        # 页码按钮
        for i, page in enumerate(show_pages, 1):  # 从cols[1]开始放页码
            with cols[i]:
                st.button(
                    str(page),
                    on_click=lambda p=page: setattr(st.session_state, "current_page", p),
                    key=f"page_{page}",
                    use_container_width=True,
                    type="primary" if page == current_page else "secondary"
                )
        
        # 下一页按钮
        with cols[-1]:
            st.button(
                "下一页 →",
                on_click=lambda: setattr(st.session_state, "current_page", current_page + 1),
                disabled=current_page == total_pages,
                key="next",
                use_container_width=True
            )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 底部信息
    last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.caption(f"最后更新：{last_update}")
    with col_right:
        if st.button("🔄 手动刷新", key="refresh"):
            st.session_state.current_page = 1
            st.rerun()

if __name__ == "__main__":
    main()