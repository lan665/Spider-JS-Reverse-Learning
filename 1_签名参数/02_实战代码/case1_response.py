import base64
import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


class Decryptor:
    """
    某政务交易平台 (G) 响应体 AES 解密工具
    """

    def __init__(self):
        # 🛡️ 密钥与偏移量出于安全合规考虑已进行脱敏替换
        # 这里的 Key 为 32 位（对应 AES-256），IV 为 16 位
        self.key = b'YOUR_AES_KEY_32_BYTE_***********'
        self.iv = b'YOUR_AES_IV_16_B'

    def decrypt(self, ciphertext: str) -> dict:
        """
        AES-CBC-PKCS7 解密逻辑
        :param ciphertext: 接口返回的 Base64 格式密文 Data
        """
        try:
            # 1. Base64 解码
            encrypted_bytes = base64.b64decode(ciphertext)

            # 2. 初始化 AES 密码器 (CBC 模式)
            cipher = AES.new(self.key, AES.MODE_CBC, self.iv)

            # 3. 解密并去除 PKCS7 填充
            decrypted_bytes = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)

            # 4. 转换为字符串并解析为 JSON 字典
            decrypted_str = decrypted_bytes.decode('utf-8')
            return json.loads(decrypted_str)

        except Exception as e:
            print(f"解密失败: {e}")
            return {}


# === 测试调用 ===
if __name__ == '__main__':
    # 模拟抓包获取的 response.Data 密文
    test_ciphertext = "MZphJmFlelDpw2aSCfdFbwZwyMk42mt3..."

    decryptor = Decryptor()
    plaintext_json = decryptor.decrypt(test_ciphertext)

    if plaintext_json:
        print("解密成功，提取的明文数据：")
        print(json.dumps(plaintext_json, ensure_ascii=False, indent=2))