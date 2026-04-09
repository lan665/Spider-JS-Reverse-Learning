import scrapy
import json
from lagou_spider.items import LagouCompanyItem


class LagouSpider(scrapy.Spider):
    name = "lagou"
    allowed_domains = ["lagou.com"]

    def start_requests(self):
        self.logger.info("🚀 Spider 启动！准备生成 20 页抓取任务...")

        base_headers = {
            'Referer': 'https://www.lagou.com/gongsi/',
            'Origin': 'https://www.lagou.com'
        }

        for page in range(1, 3):
            url = f"https://www.lagou.com/gongsi/0-0-0-{page}.json"

            yield scrapy.Request(
                url=url,
                callback=self.parse,
                dont_filter=True,
                headers=base_headers,
                # 用 meta 把页码传给 parse，方便我们看日志
                meta={'page': page}
            )

    def parse(self, response):
        current_page = response.meta.get('page')
        self.logger.info(f"📦 收到第 {current_page} 页响应，状态码: {response.status}")

        if "<html" in response.text.lower() or "滑动验证页面" in response.text:
            self.logger.error(f"🛑 第 {current_page} 页遭遇 WAF 拦截！Cookie 可能已失效。")
            return

        try:
            resp_json = response.json()
            encrypted_data = resp_json.get('content') or resp_json.get('data')

            if not encrypted_data or not isinstance(encrypted_data, str):
                self.logger.error(f"⚠️ 第 {current_page} 页未找到密文！")
                return

            # 直接调用中间件挂载的解密函数
            plaintext_str = self.decrypt_response(encrypted_data)

            if "解密失败" in plaintext_str:
                self.logger.error(f"❌ 第 {current_page} 页解密失败: {plaintext_str}")
                return

            parsed_data = json.loads(plaintext_str)
            company_list = parsed_data.get('result', [])

            self.logger.info(f"🔓 第 {current_page} 页解密成功！提取到 {len(company_list)} 家公司。")

            for company in company_list:
                item = LagouCompanyItem()
                item['companyId'] = company.get('companyId')
                item['companyFullName'] = company.get('companyFullName')
                item['companyShortName'] = company.get('companyShortName')
                item['companyLogo'] = company.get('companyLogo')
                yield item

        except Exception as e:
            self.logger.error(f"❌ 第 {current_page} 页解析失败: {e}")