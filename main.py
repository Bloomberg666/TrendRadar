
import requests
import schedule
import time
from datetime import datetime
from newsapi import NewsApiClient
from pytrends.request import TrendReq
from openai import OpenAI  # 使用官方 OpenAI 库

# ================= 配置区域 =================

# 1. API Keys 配置
NEWS_API_KEY = 'ea92df5f6f05457a9b6129d843db28f4'      # 必填: 用于搜索新闻
DEEPSEEK_API_KEY = 'sk-ebf8312aa11c4b91a417924a4f48cd61'   # 必填: DeepSeek Key

# 2. Webhook URL (以钉钉为例)
WEBHOOK_URL = 'https://oapi.dingtalk.com/robot/send?access_token=29e03da3de211f2b3dfab17de7de78a3a9bc1d492673b6b7fa6f608fd5e2799b'

# 3. 定时设置
SCHEDULE_TIME = "12:40"

# ===========================================

class NewsBot:
    def __init__(self):
        # 初始化 NewsAPI
        self.newsapi = NewsApiClient(api_key=NEWS_API_KEY)
        
        # 初始化 DeepSeek 客户端 (复用 OpenAI SDK)
        self.ai_client = OpenAI(
            api_key=DEEPSEEK_API_KEY, 
            base_url="https://api.deepseek.com"  # 关键：指向 DeepSeek 地址
        )

    def get_hot_topics(self):
        """获取热点关键词"""
        print("🔍 正在抓取热点趋势...")
        try:
            # 这里使用 Google Trends，如果国内网络不通，建议换成百度热搜爬虫
            pytrends = TrendReq(hl='en-US', tz=360)
            trends = pytrends.trending_searches(pn='united_states') 
            return trends[0].head(3).tolist()
        except Exception as e:
            print(f"⚠️ 获取热点失败: {e}")
            # 返回备用关键词，防止程序崩溃
            return ["Artificial Intelligence", "Space Exploration", "Global Markets"]

    def ai_summarize(self, text):
        """使用 DeepSeek 生成中文摘要"""
        try:
            response = self.ai_client.chat.completions.create(
                model="deepseek-chat",  # DeepSeek 模型名称
                messages=[
                    {"role": "system", "content": "你是一个专业的新闻编辑。请将用户输入的新闻内容总结为一句简练的中文摘要（50字以内），重点突出核心事实。"},
                    {"role": "user", "content": text}
                ],
                stream=False
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ DeepSeek 调用失败: {e}")
            return f"❌ DeepSeek 调用失败: {e}"

    def fetch_and_process_news(self, keyword):
        """搜索新闻 -> 获取内容 -> AI摘要"""
        try:
            # 搜索相关性最高的新闻
            response = self.newsapi.get_everything(
                q=keyword, 
                sort_by='relevancy', 
                language='en', # 如果搜中文热点，改成 'zh'
                page_size=1
            )
            
            if not response['articles']:
                return None
            
            article = response['articles'][0]
            title = article['title']
            url = article['url']
            # 优先用 content，如果没有则用 description
            content = article.get('content') or article.get('description') or ""

            print(f"🤖 正在让 DeepSeek 阅读: {title[:20]}...")
            summary = self.ai_summarize(content)
            
            # 组装 Markdown 格式
            return f"### 🔥 {keyword}\n**{title}**\n> 💡 {summary}\n[查看原文]({url})\n"
            
        except Exception as e:
            print(f"Error processing {keyword}: {e}")
            return None

    def generate_report(self):
        topics = self.get_hot_topics()
        report_content = [f"# 📰 每日 DeepSeek 热点早报 ({datetime.now().strftime('%m-%d')})"]
        
        for topic in topics:
            item = self.fetch_and_process_news(topic)
            if item:
                report_content.append(item)
                
        report_content.append(f"\n_Powered by DeepSeek API_")
        return "\n".join(report_content)

    def send_webhook(self, content):
        """发送到 Webhook (钉钉 Markdown 格式)"""
        if not WEBHOOK_URL or "YOUR_TOKEN" in WEBHOOK_URL:
            print("⚠️ 未配置 Webhook，跳过发送。")
            print("--- 本地预览 ---")
            print(content)
            return

        headers = {'Content-Type': 'application/json'}
        
        # 钉钉 Payload
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": "DeepSeek 热点早报",
                "text": content
            }
        }

        try:
            resp = requests.post(WEBHOOK_URL, json=payload, headers=headers)
            if resp.json().get('errcode') == 0:
                print("✅ 推送成功！")
            else:
                print(f"❌ 推送失败: {resp.text}")
        except Exception as e:
            print(f"❌ 网络错误: {e}")

    def run_job(self):
        print(f"\n⏰ 开始执行任务: {datetime.now()}")
        report = self.generate_report()
        self.send_webhook(report)

# ================= 主程序 =================
if __name__ == "__main__":
    bot = NewsBot()
    
    # --- 调试模式：取消下面这行的注释可以立即运行一次 ---
    bot.run_job()
    
    # --- 定时模式 ---
    print(f"🚀 服务已启动，等待每天 {SCHEDULE_TIME} 执行...")
    schedule.every().day.at(SCHEDULE_TIME).do(bot.run_job)

    while True:
        schedule.run_pending()
        time.sleep(60)
