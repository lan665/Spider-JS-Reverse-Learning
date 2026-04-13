import scrapy
import json
from lagou_spider.items import LagouCompanyItem


class LagouSpider(scrapy.Spider):
    name = "lagou"
    allowed_domains = ["lagou.com"]

    def start_requests(self):
        self.logger.info("🚀 Spider 启动！准备执行翻页任务...")

        # 循环 1 到 5 页进行测试
        for page in range(1, 6):
            url = "https://www.lagou.com/gongsi/0-0-0-0.json"

            yield scrapy.Request(
                url=url,
                method='POST',
                callback=self.parse,
                dont_filter=True,
                meta={'page': page}  #把页码传递给 Middleware 进行加密
            )

    def parse(self, response):
        current_page = response.meta.get('page')
        self.logger.info(f"📦 收到第 {current_page} 页响应，正在处理...")

        try:
            resp_json = response.json()
            encrypted_data = resp_json.get('content') or resp_json.get('data')

            if not encrypted_data:
                self.logger.error(f"⚠️ 第 {current_page} 页未找到密文，可能遭遇风控！")
                return

            # 直接调用中间件挂载的解密函数
            plaintext_str = self.decrypt_response(encrypted_data)

            if "解密失败" in plaintext_str:
                self.logger.error(f"❌ 第 {current_page} 页解密失败: {plaintext_str}")
                return

            # 将解密出的 JSON 字符串转为字典
            parsed_data = json.loads(plaintext_str)
            company_list = parsed_data.get('result', [])

            self.logger.info(f"🔓 第 {current_page} 页解密成功！提取到 {len(company_list)} 条数据。")

            # 组装 Item 扔给 Pipeline (数据库)
            for company in company_list:
                item = LagouCompanyItem()
                item['companyId'] = company.get('companyId')
                item['companyFullName'] = company.get('companyFullName')
                item['companyShortName'] = company.get('companyShortName')
                item['companyLogo'] = company.get('companyLogo')
                yield item

        except Exception as e:
            self.logger.error(f"❌ 第 {current_page} 页业务解析报错: {e}")