import random
import string
import base64
import json
import hashlib
import requests
from scrapy import signals
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


class LagouAuthDownloaderMiddleware:
    def __init__(self):
        # 1. 你的 RSA 公钥
        self.public_key_pem = (
            "************"
        )
        # 2. 你的 AES 偏移量和动态生成的 Key
        self.aes_iv = b'c558Gq0YQK2QUlMc'
        self.aes_key = self._generate_aes_key(32)

        # 3. 你抓取到的真实有效的风控 Cookie
        self.cookies = "*******"
        self.secret_key_value = ""

    @classmethod
    def from_crawler(cls, crawler):
        # 绑定爬虫启动信号
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def spider_opened(self, spider):
        """爬虫启动时：执行你的 negotiate_key() 逻辑"""
        spider.logger.info(f"🔑 爬虫启动，本地伪造的 AES Key: {self.aes_key}")

        secret_key_decode = self._rsa_encrypt(self.aes_key)

        # 必须带上基础请求头，否则协商可能失败
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': '***************',
            'content-type': 'application/json',
        }
        json_data = {'secretKeyDecode': secret_key_decode}

        # 同步发起 requests 请求获取凭证
        resp = requests.post('https://gate.lagou.com/system/agreement', headers=headers, json=json_data)
        res_json = resp.json()

        if res_json.get('message') == 'success':
            self.secret_key_value = res_json['content']['secretKeyValue']
            spider.logger.info(f"✅ 密钥协商成功！获取凭证: {self.secret_key_value}")

            # 神奇的关联：把你的解密函数直接挂载到 spider 对象上，这样在 lagou.py 里就能直接用了！
            spider.decrypt_response = self.decrypt_response
        else:
            spider.logger.error(f"❌ 密钥协商失败: {resp.text}")

    def process_request(self, request, spider):
        """每个请求发出前：执行你的 generate_xs_header() 并组装 Headers"""
        # 仅针对业务接口进行加密
        if "0-0-0-0.json" in request.url:
            url_to_sign = request.url

            x_s_header = self._generate_xs_header(url_to_sign, params_str="")
            x_ss_req_header = json.dumps({"secret": self.secret_key_value}, separators=(',', ':'))

            # 将你的请求头完美注入到 Scrapy 的 request 对象中
            request.headers['X-K-HEADER'] = self.secret_key_value
            request.headers['X-S-HEADER'] = x_s_header
            request.headers['X-SS-REQ-HEADER'] = x_ss_req_header

            request.headers['Origin'] = 'https://www.lagou.com'
            request.headers['Referer'] = 'https://www.lagou.com/gongsi/'

            # 注入你的巨型 Cookie
            request.headers['Cookie'] = self.cookies

            # 注入基础反爬 User-Agent 和 Content-Type
            request.headers[
                'User-Agent'] = '*********'
            request.headers['content-type'] = 'application/json'

        return None  # 返回 None 表示放行请求

    # ================= 加密/解密函数=================
    def _generate_aes_key(self, length=32):
        library = string.ascii_letters + string.digits
        return ''.join(random.choice(library) for _ in range(length))

    def _rsa_encrypt(self, plain_text):
        rsa_key = RSA.import_key(self.public_key_pem)
        cipher = PKCS1_v1_5.new(rsa_key)
        encrypted_bytes = cipher.encrypt(plain_text.encode('utf-8'))
        return base64.b64encode(encrypted_bytes).decode('utf-8')

    def _generate_xs_header(self, url_to_sign, params_str=""):
        origin_header_str = '{"deviceType":1}'
        raw_value = f"{origin_header_str}{url_to_sign}{params_str}"
        code = hashlib.sha256(raw_value.encode('utf-8')).hexdigest()
        payload_dict = {"originHeader": origin_header_str, "code": code}
        payload_str = json.dumps(payload_dict, separators=(',', ':'))
        cipher = AES.new(self.aes_key.encode('utf-8'), AES.MODE_CBC, self.aes_iv)
        ciphertext = cipher.encrypt(pad(payload_str.encode('utf-8'), AES.block_size))
        return base64.b64encode(ciphertext).decode('utf-8')

    def decrypt_response(self, encrypted_base64):
        try:
            encrypted_bytes = base64.b64decode(encrypted_base64)
            cipher = AES.new(self.aes_key.encode('utf-8'), AES.MODE_CBC, self.aes_iv)
            decrypted_bytes = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            return f"解密失败: {e}"