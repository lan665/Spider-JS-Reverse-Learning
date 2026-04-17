import random
import string
import base64
import json
import hashlib
import requests
import threading
import time
from scrapy import signals
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from DrissionPage import ChromiumPage, ChromiumOptions
from twisted.internet import threads
import asyncio
# ==========================================
# 全局常量：真实野生轨迹数据
# ==========================================
BASE_REAL_TRACK = [
    [270, 1748, 57], [271, 1748, 66], [274, 1748, 75], [279, 1748, 85], [282, 1748, 90],
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
    [476, 1743, 475], [479, 1742, 538], [482, 1742, 608], [485, 1742, 690], [488, 1741, 797]
]


class LagouAuthDownloaderMiddleware:
    def __init__(self):
        # 1. 你的 RSA 公钥 (请替换为你自己的)
        self.public_key_pem = (
            ""
        )

        # 2. AES 配置
        self.aes_iv = b''
        self.aes_key = self._generate_aes_key(32)
        self.secret_key_value = ""

        # 3. Cookie 管理与并发控制
        self.cookie_lock = threading.Lock()
        self.dynamic_waf_cookies = {}
        # 填入抓到的业务长效 Cookie (不需要包含 acw_tc 等 WAF 参数)
        self.base_cookies = {
            ""
        }

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def spider_opened(self, spider):
        """爬虫启动：执行密钥协商"""
        spider.logger.info(f"🔑 本地伪造的 AES Key: {self.aes_key}")
        secret_key_decode = self._rsa_encrypt(self.aes_key)
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': '',
            'Content-Type': 'application/json; charset=UTF-8',
        }
        json_data = {'secretKeyDecode': secret_key_decode}

        resp = requests.post('https://gate.lagou.com/system/agreement', headers=headers, json=json_data)
        res_json = resp.json()

        if res_json.get('message') == 'success':
            self.secret_key_value = res_json['content']['secretKeyValue']
            spider.logger.info(f"✅ 密钥协商成功！获取凭证: {self.secret_key_value}")
            # 挂载解密函数给 spider
            spider.decrypt_response = self.decrypt_response
        else:
            spider.logger.error(f"❌ 密钥协商失败: {resp.text}")

    # ================= 核心：请求与风控响应拦截 =================

    async def process_request(self, request, spider):
        # 1. 解耦：从 Spider 传递的 meta 中动态提取原料
        payload_dict = request.meta.get('payload_dict')
        form_str_for_hash = request.meta.get('form_str_for_hash')

        # 如果没有携带加密原料，说明是普通请求，直接放行
        if not payload_dict or not form_str_for_hash:
            return None

        # 2. 异步改造：如果没有 WAF Cookie，挂起引擎，丢给后台线程去跑浏览器
        if not self.dynamic_waf_cookies:
            spider.logger.info(f"⏳ 引擎挂起，等待获取 WAF Cookie...")
            # 2. 改用 await asyncio.to_thread 将耗时任务放入原生线程池，彻底消除 Deferred 警告
            await asyncio.to_thread(self._refresh_waf_cookies, spider, request.url)

        # 3. 如果已经有了 Cookie，直接进行内存组装
        self._assemble_request(request, payload_dict, form_str_for_hash)
        return None

    def _async_prepare_request(self, request, spider, payload_dict, form_str_for_hash):
        """后台线程专用的执行流"""
        self._refresh_waf_cookies(spider, request.url)  # 这步会耗时几秒，但因为在线程池里，不影响 Scrapy 主引擎并发
        self._assemble_request(request, payload_dict, form_str_for_hash)
        return None  # 返回 None 表示放行请求

    def _assemble_request(self, request, payload_dict, form_str_for_hash):
        """统一的加密参数组装工厂"""
        # 兵分两路生成签名与载荷
        x_s_header = self._generate_xs_header(request.url, params_str=form_str_for_hash)
        encrypted_data = self._encrypt_payload(payload_dict)

        # 注入发包核心参数
        request.headers['User-Agent'] = ''
        request.headers['X-K-HEADER'] = self.secret_key_value
        request.headers['X-S-HEADER'] = x_s_header
        request.headers['X-SS-REQ-HEADER'] = json.dumps({"secret": self.secret_key_value}, separators=(',', ':'))
        request.headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        request.headers['Origin'] = 'https://www.lagou.com'
        request.headers['Referer'] = 'https://www.lagou.com/gongsi/'

        request._set_body(f"data={encrypted_data}".encode('utf-8'))
        request.cookies = {**self.base_cookies, **self.dynamic_waf_cookies}

    def process_response(self, request, response, spider):
        """检测阿里 WAF 拦截并触发自动重试"""
        if response.status in [403, 405] or "滑动验证" in response.text:
            retries = request.meta.get('waf_retries', 0)
            if retries >= 2:
                spider.logger.error(f"☠️ 请求重试 2 次依然失败，丢弃: {request.url}")
                return response

            spider.logger.warning(f"🚨 遭遇 WAF 拦截！准备重置通行证...")

            # 💡 核心修复：清空失效的 Cookie，促使下次重试时去触发后台获取
            with self.cookie_lock:
                self.dynamic_waf_cookies = {}

            # 复制原请求，打上新的标记重投队列
            new_request = request.copy()
            new_request.meta['waf_retries'] = retries + 1
            new_request.dont_filter = True

            return new_request  # 将请求打回重新调度

        return response

    def _refresh_waf_cookies(self, spider, url):
        with self.cookie_lock:
            if self.dynamic_waf_cookies:
                spider.logger.info("✅ 检测到已有新鲜通行证，直接借用，取消唤醒浏览器...")
                return

            spider.logger.info("🔧 [泵机] 正在隐蔽启动浏览器提取通行证...")
            new_cookies = self._get_waf_cookie_via_listen(url)
            if new_cookies:
                self.dynamic_waf_cookies = new_cookies
                spider.logger.info(f"✅ [泵机] 护照刷新成功！")

    # ================= 基础加解密算法 =================

    def _generate_aes_key(self, length=32):
        return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

    def _rsa_encrypt(self, plain_text):
        cipher = PKCS1_v1_5.new(RSA.import_key(self.public_key_pem))
        return base64.b64encode(cipher.encrypt(plain_text.encode('utf-8'))).decode('utf-8')

    def _generate_xs_header(self, url_to_sign, params_str=""):
        origin_header = '{"deviceType":1}'
        code = hashlib.sha256(f"{origin_header}{url_to_sign}{params_str}".encode('utf-8')).hexdigest()
        payload_str = json.dumps({"originHeader": origin_header, "code": code}, separators=(',', ':'))

        cipher = AES.new(self.aes_key.encode('utf-8'), AES.MODE_CBC, self.aes_iv)
        ciphertext = cipher.encrypt(pad(payload_str.encode('utf-8'), AES.block_size))
        return base64.b64encode(ciphertext).decode('utf-8')

    def _encrypt_payload(self, data_dict):
        plaintext = json.dumps(data_dict, separators=(',', ':'))
        cipher = AES.new(self.aes_key.encode('utf-8'), AES.MODE_CBC, self.aes_iv)
        ciphertext = cipher.encrypt(pad(plaintext.encode('utf-8'), AES.block_size))
        return base64.b64encode(ciphertext).decode('utf-8')

    def decrypt_response(self, encrypted_base64):
        try:
            cipher = AES.new(self.aes_key.encode('utf-8'), AES.MODE_CBC, self.aes_iv)
            decrypted_bytes = unpad(cipher.decrypt(base64.b64decode(encrypted_base64)), AES.block_size)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            return f"解密失败: {e}"

    # ================= DrissionPage 物理辅助模块 =================

    def _generate_tracks(self, base_track, target_move):
        if not base_track or len(base_track) < 2: return base_track
        start_x = base_track[0][0]
        scale = target_move / (base_track[-1][0] - start_x)
        new_track = []
        for x, y, t in base_track:
            new_track.append([start_x + int(round((x - start_x) * scale)), y, t])
        new_track[-1][0] = start_x + int(round(target_move))
        return new_track

    def _get_waf_cookie_via_listen(self, target_url):
        co = ChromiumOptions()
        co.set_argument('--disable-blink-features=AutomationControlled')
        page = ChromiumPage(co)

        page.get(target_url)
        page.wait.load_start()
        time.sleep(2)

        slider_btn = page.ele('#nc_1_n1z', timeout=2)
        slider_track = page.ele('#nc_1_n1t', timeout=2)

        if not slider_btn:
            iframe = page.get_frame('#baxia-dialog-content', timeout=2)
            if iframe:
                slider_btn = iframe.ele('#nc_1_n1z')
                slider_track = iframe.ele('#nc_1_n1t')
                page = iframe

        if slider_btn and slider_track:
            target_distance = slider_track.rect.size[0] - slider_btn.rect.size[0]
            custom_tracks = self._generate_tracks(BASE_REAL_TRACK, target_distance)

            action = page.actions
            action.hold(slider_btn)
            current_x, current_y, current_t = custom_tracks[0]
            for next_x, next_y, next_t in custom_tracks[1:]:
                action.move(offset_x=next_x - current_x, offset_y=next_y - current_y)
                sleep_time = (next_t - current_t) / 1000.0 + random.uniform(0.001, 0.003)
                if sleep_time > 0: time.sleep(sleep_time)
                current_x, current_y, current_t = next_x, next_y, next_t
            action.release()

            # 轮询等待 Cookie
            for _ in range(10):
                current_page_obj = page.page if hasattr(page, 'page') else page

                cookies_raw = current_page_obj.cookies()
                cookies_dict = cookies_raw if isinstance(cookies_raw, dict) else {c['name']: c['value'] for c in
                                                                                  cookies_raw}

                acw_sc__v3 = cookies_dict.get('acw_sc__v3')
                if acw_sc__v3:
                    return {"acw_tc": cookies_dict.get('acw_tc', ''), "acw_sc__v3": acw_sc__v3,
                            "tfstk": cookies_dict.get('tfstk', '')}
                time.sleep(0.5)
            return None
        else:
            current_page_obj = page.page if hasattr(page, 'page') else page
            cookies_raw = current_page_obj.cookies()
            cookies_dict = cookies_raw if isinstance(cookies_raw, dict) else {c['name']: c['value'] for c in
                                                                              cookies_raw}
            return {k: v for k, v in
                    {"acw_tc": cookies_dict.get('acw_tc'), "acw_sc__v3": cookies_dict.get('acw_sc__v3'),
                     "tfstk": cookies_dict.get('tfstk')}.items() if v}