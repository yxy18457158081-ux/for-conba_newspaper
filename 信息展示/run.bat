@echo off
:: 安装依赖
pip install -r requirements.txt

:: 获取邮件数据
echo 开始获取最新邮件...
python get_emails.py

:: 启动展示页面
echo 启动信息展示页面...
streamlit run display.py