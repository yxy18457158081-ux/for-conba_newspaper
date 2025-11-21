import imaplib
import email
from email.header import decode_header
import json
from datetime import datetime, timedelta
import email.utils

# -------------------------- 请填写你的信息 --------------------------
QQ_EMAIL = "2420778484@qq.com"  # 你的QQ邮箱
AUTH_CODE = "ulhzlajcvkpsebjh"      # 你的授权码
TARGET_SUBJECT = "康恩贝内部行业信息简报"  # 固定前缀
STORAGE_FILE = "email_data.json"  # 存储文件
# ----------------------------------------------------------------------

def decode_chinese(s):
    """处理邮件中文编码（解决标题、内容乱码）"""
    if not s:
        return ""
    # 确保输入是字符串（如果是字节，先尝试解码）
    if isinstance(s, bytes):
        try:
            s = s.decode("utf-8")  # 先尝试utf-8解码
        except UnicodeDecodeError:
            s = str(s)  # 解码失败则转为字符串
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
    """获取近7天的邮件（包含今天），标题包含固定前缀的内容（自动去重）"""
    # 计算日期范围：当前日期 - 7天 到 今天（包含今天）
    today = datetime.now().date()
    start_date = today - timedelta(days=7)
    tomorrow = today + timedelta(days=1)  # 用于BEFORE条件，确保包含今天
    print(f"📅 开始获取 {start_date} 至 {today}（含当天）的目标邮件...")

    # 连接QQ邮箱IMAP服务器
    try:
        mail = imaplib.IMAP4_SSL("imap.qq.com", 993)
        mail.login(QQ_EMAIL, AUTH_CODE)
    except Exception as e:
        print(f"❌ 登录失败：{str(e)}（请检查邮箱和授权码是否正确）")
        return []

    # 选择收件箱
    select_status, _ = mail.select("INBOX")
    if select_status != "OK":
        print("❌ 无法选择收件箱")
        mail.logout()
        return []
    print("✅ 已选择收件箱，开始筛选近7天的邮件...")

    # IMAP筛选：包含起始日至今天（含今天）的邮件
    # SINCE包含起始日，BEFORE明天则包含今天
    start_date_str = start_date.strftime("%d-%b-%Y")  # IMAP要求格式：日-月-年（英文缩写）
    tomorrow_str = tomorrow.strftime("%d-%b-%Y")
    status, data = mail.search(None, f"SINCE {start_date_str} BEFORE {tomorrow_str}")
    
    if status != "OK":
        print("❌ 无法获取近7天的邮件列表")
        mail.close()
        mail.logout()
        return []
    email_ids = data[0].split()
    total_emails = len(email_ids)
    print(f"ℹ️ 共发现 {total_emails} 封符合日期范围的邮件，开始检查标题是否包含'{TARGET_SUBJECT}'...")

    # 读取已存储的邮件ID（避免重复处理）
    existing_ids = set()
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            stored_data = json.load(f)
            existing_ids = {item["email_id"] for item in stored_data}
    except (FileNotFoundError, json.JSONDecodeError):
        stored_data = []
    print(f"ℹ️ 已处理过的邮件数量：{len(existing_ids)} 封")

    new_emails = []

    # 遍历邮件：倒序遍历（最新的邮件先处理）
    for i, email_id in enumerate(reversed(email_ids), 1):
        print(f"\n🔍 正在检查第 {i}/{total_emails} 封邮件...")
        email_id_str = email_id.decode()
        
        # 跳过已处理的邮件
        if email_id_str in existing_ids:
            print(f"⏭️ 第 {i} 封邮件已处理过（ID：{email_id_str}），跳过")
            continue

        # 获取邮件详情
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        if status != "OK":
            print(f"❌ 无法读取第 {i} 封邮件（ID：{email_id_str}），跳过")
            continue
        msg = email.message_from_bytes(msg_data[0][1])

        # 检查标题是否包含固定前缀
        subject = decode_chinese(msg.get("Subject", ""))
        if TARGET_SUBJECT not in subject:
            print(f"⏭️ 第 {i} 封邮件标题不匹配（标题：{subject}），跳过")
            continue

        # 解析邮件正文（确保传给decode_chinese的是字符串）
        content = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)  # 字节类型
                    if payload:
                        # 先将字节转为字符串，再处理中文
                        content = decode_chinese(payload)
                    break
        else:
            payload = msg.get_payload(decode=True)  # 字节类型
            if payload:
                content = decode_chinese(payload)

        # 收集邮件信息（发送时间仅展示）
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
        print(f"✅ 第 {i} 封邮件匹配成功！标题：{subject}（发送时间：{send_time}）")

    # 关闭连接
    mail.close()
    mail.logout()
    return new_emails

def save_emails_to_file(new_emails):
    if not new_emails:
        print(f"\nℹ️ 近7天（含今天）的邮件中，没有标题包含'{TARGET_SUBJECT}'的新邮件")
        return

    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            all_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_data = []

    # 合并新邮件并按发送时间排序（最新在前）
    all_data.extend(new_emails)
    all_data.sort(
        key=lambda x: x["send_time"] if x["send_time"] not in ["未知", "时间格式异常"] else "1970-01-01 00:00:00",
        reverse=True
    )

    # 去重（避免极端情况下的重复，双重保障）
    unique_data = []
    seen_ids = set()
    for item in all_data:
        if item["email_id"] not in seen_ids:
            seen_ids.add(item["email_id"])
            unique_data.append(item)

    # 保存到文件
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(unique_data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存 {len(new_emails)} 条新匹配的内容，累计 {len(unique_data)} 条不重复记录")

if __name__ == "__main__":
    print("="*50)
    print("📌 康恩贝行业信息简报 - 邮件获取工具（近7天，含今天）")
    print("="*50)
    new_mails = get_last_week_emails()
    save_emails_to_file(new_mails)
    print("\n📌 任务完成！")