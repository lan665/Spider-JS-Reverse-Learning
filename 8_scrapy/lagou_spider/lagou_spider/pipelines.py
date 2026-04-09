import pymysql
from pymysql import cursors
from twisted.enterprise import adbapi


class LagouSpiderPipeline:
    def __init__(self, db_pool):
        self.db_pool = db_pool

    # 💡 终极修复：使用 Scrapy 最标准的 from_crawler 钩子
    @classmethod
    def from_crawler(cls, crawler):
        # 从 crawler.settings 中安全地提取配置
        db_params = dict(
            host=crawler.settings.get('MYSQL_HOST', '127.0.0.1'),
            port=crawler.settings.getint('MYSQL_PORT', 3306),
            user=crawler.settings.get('MYSQL_USER', 'root'),
            password=crawler.settings.get('MYSQL_PASSWORD', 'root'),
            database=crawler.settings.get('MYSQL_DBNAME', 'spider_db'),
            charset='utf8mb4',
            cursorclass=cursors.DictCursor,
            use_unicode=True,
        )
        # 创建异步连接池
        db_pool = adbapi.ConnectionPool('pymysql', **db_params)
        return cls(db_pool)

    def process_item(self, item, spider):
        # 探头：打印日志确认管道工作
        spider.logger.info(f"🚚 管道接收到数据: {item.get('companyFullName')}")

        # 异步插入数据库
        query = self.db_pool.runInteraction(self.do_insert, item)
        query.addErrback(self.handle_error, item, spider)
        return item

    def do_insert(self, cursor, item):
        insert_sql = """
                     INSERT INTO lagou_company
                     (company_id, encrypt_company_id, company_full_name, company_short_name, company_logo)
                     VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY \
                     UPDATE \
                         company_full_name= \
                     VALUES (company_full_name), company_logo= \
                     VALUES (company_logo) \
                     """
        cursor.execute(insert_sql, (
            item.get('companyId'),
            item.get('encryptCompanyId'),
            item.get('companyFullName'),
            item.get('companyShortName'),
            item.get('companyLogo')
        ))

    def handle_error(self, failure, item, spider):
        spider.logger.error(f"❌ 数据库写入失败: {failure}")