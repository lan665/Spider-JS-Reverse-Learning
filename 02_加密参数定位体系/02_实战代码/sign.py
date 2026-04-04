import hashlib
import json
from typing import Dict, Any


def generate_u_sign(url: str, payload_data: Dict[str, Any]) -> str:
    """
    U-Sign 签名 (目前仅覆盖纯 POST Payload 分支)

    :param url: 请求的完整 URL 或 Path (如 '/search/colleges/collegeList')
    :param payload_data: 请求体字典
    :return: 32位小写 MD5 签名字符串
    """
    # 1. 内部固定的盐值 (Salt)
    # 声明：盐值出于安全合规考虑已脱敏
    salt = "YOUR_SALT_HERE_***"

    # 注意：原 JS 逻辑中包含对 url.split("?") 的处理。
    # 若后续需要处理带查询参数的 GET 请求，需在此处补充 url 解析分支。
    if "?" in url:
        raise NotImplementedError("当前脚本暂未实现带 URL 查询参数的签名逻辑，请参考 JS 源码补充。")

    # 2. 判断 Payload 是否为空并转换为 JSON 字符串
    # 对应 JS: Object.keys(a).length > 0 ? JSON.stringify(a) : ""
    if payload_data and len(payload_data) > 0:
        # separators=(',', ':') 消除多余空格，严格对齐 JS 的 JSON.stringify
        json_str = json.dumps(payload_data, separators=(',', ':'))
    else:
        json_str = ""

    # 3. 按照 JS 的逻辑进行拼接：JSON串 + "&" + 盐值
    raw_string = f"{json_str}&{salt}"

    # 4. 全局转为小写，并计算 MD5
    lower_string = raw_string.lower()
    u_sign = hashlib.md5(lower_string.encode('utf-8')).hexdigest()

    return u_sign


# --- 测试运行 ---
if __name__ == "__main__":
    # 目标请求 URL
    target_url = "/search/colleges/collegeList"

    # 抓包获取的真实请求体参数
    test_payload = {
        "keyword": "",
        "provinceNames": [],
        "natureTypes": [],
        "eduLevel": "",
        "categories": [],
        "features": [],
        "pageIndex": 2,
        "pageSize": 20,
        "sort": 11
    }

    # 严格按照 JS 传参顺序传入 url 和 payload
    sign = generate_u_sign(target_url, test_payload)
    print(f"生成的 U-Sign: {sign}")