from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import base64
import cv2
import numpy as np
import requests
import requests
import random
import json
import re
import string
import random

def get_random_str(length=16):
    # 云片通常使用字母+数字的组合
    library = string.ascii_letters + string.digits
    return ''.join(random.choice(library) for _ in range(length))


class LocalSliderSolver:
    def __init__(self):
        # 不再需要初始化 ddddocr
        pass

    def get_distance(self, bg_url, front_url):
        """
        使用 OpenCV 边缘检测 (Canny) 高精度识别云片滑块缺口
        """
        print("正在从内存下载图片并使用 OpenCV 边缘检测识别...")

        # 1. 内存中请求图片
        bg_bytes = requests.get(bg_url).content
        front_bytes = requests.get(front_url).content

        # 2. 将 bytes 转换为 numpy 数组供 cv2 读取
        bg_array = np.frombuffer(bg_bytes, np.uint8)
        front_array = np.frombuffer(front_bytes, np.uint8)

        # 3. 以灰度模式读取背景图
        bg_img = cv2.imdecode(bg_array, cv2.IMREAD_GRAYSCALE)
        # ⚠️ 关键：以保留 Alpha 通道 (透明度) 的模式读取滑块图
        front_img = cv2.imdecode(front_array, cv2.IMREAD_UNCHANGED)

        # 4. 提取滑块的轮廓图
        if front_img.shape[2] == 4:  # 如果有透明通道
            # 提取透明通道中的有效形状
            front_gray = cv2.cvtColor(front_img, cv2.COLOR_BGRA2GRAY)
        else:
            front_gray = cv2.imdecode(front_array, cv2.IMREAD_GRAYSCALE)

        # 5. Canny 边缘检测：将图片变成只有白线条的“简笔画” (无视颜色干扰)
        bg_edge = cv2.Canny(bg_img, 100, 200)
        front_edge = cv2.Canny(front_gray, 100, 200)

        # 6. 使用 TM_CCOEFF_NORMED (归一化相关系数匹配法) 进行比对
        res = cv2.matchTemplate(bg_edge, front_edge, cv2.TM_CCOEFF_NORMED)

        # 7. 获取匹配度最高的位置
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        # max_loc[0] 就是我们要的 X 轴距离
        distance_x = max_loc[0]

        print(f"🎯 OpenCV 边缘检测成功！缺口 X 轴距离为: {distance_x}")
        return distance_x



def generate_tracks(base_track, target_move):
    """
    真机轨迹等比缩放
    :param base_track: 浏览器抓取的真人轨迹数组
    :param target_move: 本次验证需要滑动的实际像素 (330宽下的位移)
    """
    if not base_track or len(base_track) < 2:
        return base_track

    # 1. 计算这条真实轨迹原本滑了多少像素
    start_x = base_track[0][0]
    original_move = base_track[-1][0] - start_x

    # 2. 计算拉伸/压缩比例
    scale = target_move / original_move

    new_track = []

    # 3. 遍历原轨迹，进行降维重组
    for point in base_track:
        x, y, t = point

        # 仅对 X 轴的相对位移进行等比缩放！
        # 重点：Y 轴和 时间 t 绝对不能改，这是骗过 AI 的生物学特征！
        relative_x = x - start_x
        new_relative_x = int(round(relative_x * scale))

        new_track.append([start_x + new_relative_x, y, t])

    # 4. 强制兜底校验：确保最后一个点分毫不差
    expected_end_x = start_x + int(round(target_move))
    if new_track[-1][0] != expected_end_x:
        new_track[-1][0] = expected_end_x

    return new_track

def get_k_value(aes_key, aes_iv, public_key_str):
    """
    使用 RSA 公钥加密 AES的 Key和IV 的拼接字符串
    """
    # 1. 拼接 e + n
    concat_str = aes_key + aes_iv

    # 2. 导入公钥并使用 PKCS1_v1_5 模式加密
    rsa_key = RSA.import_key(public_key_str)
    cipher = PKCS1_v1_5.new(rsa_key)

    # 3. 加密并转为 Base64
    encrypted_bytes = cipher.encrypt(concat_str.encode('utf-8'))
    k_value = base64.b64encode(encrypted_bytes).decode('utf-8')
    return k_value


def encrypt_data(plaintext_dict, aes_key, aes_iv, public_key_str):
    """
    通用加密：既可以加密 get 的指纹，也可以加密 verify 的轨迹
    """
    # 1. AES 加密 (生成 i)
    t_text = json.dumps(plaintext_dict, separators=(',', ':'))
    cipher = AES.new(aes_key.encode('utf-8'), AES.MODE_CBC, aes_iv.encode('utf-8'))
    padded_text = pad(t_text.encode('utf-8'), AES.block_size)
    i_value = base64.b64encode(cipher.encrypt(padded_text)).decode('utf-8')

    # 2. RSA 加密 (生成 k)
    k_value = get_k_value(aes_key, aes_iv, public_key_str)

    return i_value, k_value






if __name__ == "__main__":

    header = ""
    cookie = ""
    aes_key = get_random_str(16)
    aes_iv = get_random_str(16)
    public_key_str = (
        ""
    )#抓取的固定值

    # --- 步骤 1: 获取 Token 与图片 ---
    get_raw = {
        "browserInfo": [],#抓取的固定值
        "fp": "**********",#抓取的固定值
        "yp_riddler_id": "*********"#抓取的固定值
    }
    i_get, k_get = encrypt_data(get_raw, aes_key, aes_iv, public_key_str)

    CAPTCHA_ID = '' #抓取的固定值

    get_params = {
        'cb': get_random_str(11).lower(),
        'i': i_get,
        'k': k_get,
        'captchaId': CAPTCHA_ID
    }

    resp_text = requests.get('https://captcha.yunpian.com//v1/jsonp/captcha/get', params=get_params, headers=header).text
    json_data = json.loads(re.search(r'\((.*)\)', resp_text).group(1))

    token = json_data['data']['token']
    bg_url = json_data['data']['bg']
    front_url = json_data['data']['front']
    print(f"✅ 获取 Token 成功: {token}")

    # hook的人工轨迹数据
    BASE_REAL_TRACK = [[270, 1748, 57], [271, 1748, 66], [274, 1748, 75], [279, 1748, 85], [282, 1748, 90],
                       [285, 1748, 97], [291, 1748, 100], [294, 1748, 104], [297, 1748, 106], [300, 1748, 113],
                       [307, 1748, 117], [310, 1748, 119], [314, 1748, 123], [331, 1748, 139], [337, 1748, 143],
                       [341, 1748, 147], [345, 1748, 150], [348, 1748, 152], [352, 1748, 156], [357, 1748, 160],
                       [360, 1748, 163], [364, 1748, 165], [368, 1748, 168], [372, 1747, 172], [376, 1747, 176],
                       [380, 1747, 179], [383, 1747, 181], [387, 1747, 185], [391, 1747, 189], [394, 1747, 191],
                       [398, 1747, 194], [401, 1747, 198], [404, 1747, 202], [407, 1747, 205], [409, 1746, 207],
                       [414, 1746, 212], [417, 1746, 215], [422, 1746, 222], [425, 1746, 226], [429, 1746, 231],
                       [432, 1746, 236], [435, 1746, 239], [438, 1746, 243], [441, 1746, 248], [444, 1745, 252],
                       [447, 1745, 257], [450, 1745, 262], [453, 1745, 270], [456, 1745, 279], [459, 1744, 327],
                       [462, 1744, 344], [465, 1744, 354], [468, 1744, 363], [471, 1744, 373], [474, 1744, 394],
                       [476, 1743, 475], [479, 1742, 538], [482, 1742, 608], [485, 1742, 690], [488, 1741, 797]]


    # --- 步骤 2: 计算距离与轨迹 ---
    solver = LocalSliderSolver()
    pixel_distance = solver.get_distance(bg_url, front_url)
    actual_move = pixel_distance * (330 / 480)

    # --- 步骤 3: 最终验证 ---

    verify_raw = {
        "points": generate_tracks(BASE_REAL_TRACK, actual_move),
        "distanceX": pixel_distance / 480.0,
        "fp": "***********",#抓取的固定值
        "address": "https://www.yunpian.com",
        "yp_riddler_id": "**********"#抓取的固定值
    }

    aes_key_ver = get_random_str(16)
    aes_iv_ver = get_random_str(16)
    i_ver, k_ver = encrypt_data(verify_raw, aes_key_ver, aes_iv_ver, public_key_str)



    ver_params = {
        'cb': get_random_str(11).lower(),
        'i': i_ver,
        'k': k_ver,
        'token': token,
        'captchaId': CAPTCHA_ID
    }

    final_resp = requests.get('https://captcha.yunpian.com//v1/jsonp/captcha/verify', params=ver_params, headers=header)
    print(f"🎉 最终验证结果: {final_resp.text}")

