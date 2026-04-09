import time
import random
import hashlib
import json
from typing import Dict


class BizQSigner:
    """
    某商业数据平台 (Q) 请求头动态签名生成器
    """

    def __init__(self):
        # 1. 内部固定的盐值 (Salt)
        # 🛡️ 声明：盐值出于安全合规考虑已脱敏，请通过学习 README 中的逆向思路自行提取
        self.salt = "YOUR_SALT_HERE_***"

        # 请求来源标识
        self.req_from = "qcc-tender-web"

    def generate_headers(self) -> Dict[str, str]:
        """
        生成包含防篡改校验的核心请求头字典
        """
        # 1. 动态生成 13 位毫秒级时间戳
        req_time = str(int(time.time() * 1000))

        # 2. 生成类似 UUID 的随机 ID (原 JS: [Zx()(1e7, 99999999), ...].join("-"))
        p1 = random.randint(10000000, 99999999)
        p2 = random.randint(1000, 9999)
        p3 = random.randint(1000, 9999)
        p4 = random.randint(100000000000, 999999999999)
        req_id = f"{p1}-{p2}-{p3}-{p4}"

        # 3. 按照 JS 的逻辑进行明文拼接：salt:from:time:id
        plain_text = f"{self.salt}:{self.req_from}:{req_time}:{req_id}"

        # 4. 计算标准 MD5 并转为大写
        md5_hash = hashlib.md5(plain_text.encode('utf-8')).hexdigest().upper()

        # 5. 返回构造好的 Headers 字典
        return {
            "X-Kzz-Request-From": self.req_from,
            "X-Kzz-Request-Id": req_id,
            "X-Kzz-Request-Time": req_time,
            "X-Kzz-Request-Key": md5_hash
        }


# --- 测试运行 ---
if __name__ == "__main__":
    # 1. 实例化签名生成器
    signer = BizQSigner()

    # 2. 生成加密请求头
    headers_extension = signer.generate_headers()

    print("====== 生成的动态请求头 ======")
    for k, v in headers_extension.items():
        print(f"{k}: {v}")

    print("\n💡 实战发包提示：")
    print("1. 请使用 headers.update(headers_extension) 将上述字段合并到基础 Headers 中。")
    print("2. 组装 Payload 时，务必使用 json.dumps(payload, separators=(',', ':'))")
    print("   消除默认的空格，防止触发后端 Body Hash 严格校验拦截。")
    print("3. 别忘了携带你的业务/风控 Cookie。")