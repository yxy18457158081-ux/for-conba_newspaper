import streamlit as st
import json
import re
from datetime import datetime, timedelta
import imaplib
import email
from email.header import decode_header
import email.utils

# -------------------------- 配置参数 --------------------------
# 邮件相关配置（建议使用Streamlit Secrets存储敏感信息）
QQ_EMAIL = "2420778484@qq.com"  # 你的QQ邮箱
AUTH_CODE = "ulhzlajcvkpsebjh"   # 你的授权码（注意：公开仓库需用Secrets管理）
TARGET_SUBJECT = "康恩贝内部行业信息简报"  # 目标邮件标题前缀
STORAGE_FILE = "email_data.json"  # 数据存储文件

# 页面配置
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
    
    /* 分页样式 */
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
    .prev-next {
        background-color: #f1f5f9;
        color: #334155;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .prev-next:hover {background-color: #e2e8f0; transform: translateY(-1px);}
    .prev-next:disabled {
        background-color: #f8fafc;
        color: #94a3b8;
        cursor: not-allowed;
        transform: none;
    }
    .page-number {
        background-color: #ffffff;
        color: #334155;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        width: 2.5rem;
        height: 2.5rem;
        padding: 0;
        justify-content: center;
    }
    .page-number:hover {background-color: #f1f5f9; transform: translateY(-1px);}
    .page-number.active {
        background-color: #1E40AF;
        color: white;
        box-shadow: 0 2px 5px rgba(30, 64, 175, 0.3);
    }
</style>
"""
# ----------------------------------------------------------

# -------------------------- 邮件处理函数 --------------------------
def decode_chinese(s):
    """处理邮件中文编码（解决标题、内容乱码）"""
    if not s:
        return ""
    if isinstance(s, bytes):
        try:
            s = s.decode("utf-8")
        except UnicodeDecodeError:
            s = str(s)
    decoded = decode_header(s)
    result = []
    for part, encoding in decoded:
        if isinstance(part, bytes):
            for enc in [encoding, "utf-8", "gbk", "gb2312"]:
                if enc:
                    try:
                        result.append(part.decode(enc))
                        break
                    except UnicodeDecodeError:
                        continue
            else:
                result.append(str(part))
        else:
            result.append(str(part))
    return "".join(result)

def get_last_week_emails():
    """获取近7天的目标邮件（自动去重）"""
    today = datetime.now().date()
    start_date = today - timedelta(days=7)
    tomorrow = today + timedelta(days=1)
    st.info(f"正在获取 {start_date} 至 {today} 的目标邮件...")

    # 连接邮箱服务器
    try:
        mail = imaplib.IMAP4_SSL("imap.qq.com", 993)
        mail.login(QQ_EMAIL, AUTH_CODE)
    except Exception as e:
        st.error(f"邮箱登录失败：{str(e)}（请检查邮箱和授权码）")
        return []

    # 选择收件箱
    select_status, _ = mail.select("INBOX")
    if select_status != "OK":
        st.error("无法访问收件箱")
        mail.logout()
        return []

    # 筛选近7天邮件
    start_date_str = start_date.strftime("%d-%b-%Y")
    tomorrow_str = tomorrow.strftime("%d-%b-%Y")
    status, data = mail.search(None, f"SINCE {start_date_str} BEFORE {tomorrow_str}")
    
    if status != "OK":
        st.error("无法获取邮件列表")
        mail.close()
        mail.logout()
        return []
    email_ids = data[0].split()
    total_emails = len(email_ids)
    st.info(f"发现 {total_emails} 封符合日期范围的邮件，正在筛选目标邮件...")

    # 读取已存储的邮件ID（去重）
    existing_ids = set()
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            stored_data = json.load(f)
            existing_ids = {item["email_id"] for item in stored_data}
    except (FileNotFoundError, json.JSONDecodeError):
        stored_data = []

    new_emails = []
    # 倒序遍历（最新邮件优先）
    for i, email_id in enumerate(reversed(email_ids), 1):
        email_id_str = email_id.decode()
        if email_id_str in existing_ids:
            continue  # 跳过已处理邮件

        # 获取邮件详情
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        if status != "OK":
            continue
        msg = email.message_from_bytes(msg_data[0][1])

        # 检查标题是否匹配
        subject = decode_chinese(msg.get("Subject", ""))
        if TARGET_SUBJECT not in subject:
            continue

        # 解析正文
        content = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        content = decode_chinese(payload)
                    break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                content = decode_chinese(payload)

        # 解析发送时间
        send_time = "未知"
        date_str = msg.get("Date")
        if date_str:
            try:
                send_time = email.utils.parsedate_to_datetime(date_str).strftime("%Y-%m-%d %H:%M:%S")
            except:
                send_time = "时间格式异常"

        new_emails.append({
            "email_id": email_id_str,
            "send_time": send_time,
            "subject": subject,
            "content": content.strip()
        })

    mail.close()
    mail.logout()
    return new_emails

def save_emails_to_file(new_emails):
    """保存新邮件到本地文件"""
    if not new_emails:
        st.info("没有发现新的目标邮件")
        return

    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            all_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_data = []

    # 合并并去重
    all_data.extend(new_emails)
    all_data.sort(
        key=lambda x: x["send_time"] if x["send_time"] not in ["未知", "时间格式异常"] else "1970-01-01 00:00:00",
        reverse=True
    )
    unique_data = []
    seen_ids = set()
    for item in all_data:
        if item["email_id"] not in seen_ids:
            seen_ids.add(item["email_id"])
            unique_data.append(item)

    # 保存
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(unique_data, f, ensure_ascii=False, indent=2)
    st.success(f"已更新 {len(new_emails)} 条新邮件，累计 {len(unique_data)} 条记录")

# -------------------------- 页面展示函数 --------------------------
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

    # 第一步：获取并更新邮件数据
    new_mails = get_last_week_emails()
    save_emails_to_file(new_mails)

    # 第二步：加载数据并展示
    st.write("基于标题中的日期，最新简报将优先显示👇")
    email_data = load_stored_data()
    if not email_data:
        st.info("暂无数据，请稍后重试...")
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

        # 生成分页按钮列表
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

        # 横向分页控件
        st.markdown('<div class="pagination-container">', unsafe_allow_html=True)
        cols = st.columns(len(show_pages) + 2)
        
        # 上一页按钮
        with cols[0]:
            st.button(
                "← 上一页",
                on_click=lambda: setattr(st.session_state, "current_page", current_page - 1),
                disabled=current_page == 1,
                key="prev",
                use_container_width=True
            )
        
        # 页码按钮
        for i, page in enumerate(show_pages, 1):
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