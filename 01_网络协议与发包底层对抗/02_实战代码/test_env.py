import os
# 导入加载模块
from dotenv import load_dotenv

# 1. 自动向上寻找项目根目录的 .env 文件并加载它
load_dotenv()

# 2. 像取字典一样，安全地把密码和 Cookie 提取到变量里
my_proxy_url = os.getenv("PROXY_API_URL")
my_secret_cookie = os.getenv("VIP_COOKIE")

# 3. 打印出来测试一下有没有读到
print("====== 隐私数据读取测试 ======")
print(f" 成功读取代理地址: {my_proxy_url}")
print(f" 成功读取私密Cookie: {my_secret_cookie}")

# 4. 在实战中，你就可以这样把它们塞进请求里，代码里毫无隐私痕迹！
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Cookie": my_secret_cookie  # 直接传变量
}
# response = requests.get("https://目标网站.com", headers=headers)