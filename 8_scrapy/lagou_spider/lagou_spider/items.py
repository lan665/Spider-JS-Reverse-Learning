import scrapy


class LagouCompanyItem(scrapy.Item):
    """
    拉勾网公司信息数据模型
    定义好这些字段后，Scrapy 引擎自动帮我们进行数据流转
    """
    # 公司 ID (主键)
    companyId = scrapy.Field()

    # 加密后的公司 ID (备用)
    encryptCompanyId = scrapy.Field()

    # 公司全称
    companyFullName = scrapy.Field()

    # 公司简称
    companyShortName = scrapy.Field()

    # 公司 Logo 路径
    companyLogo = scrapy.Field()

    # （可选）你可以根据后续解密出的其他字段，继续在这里添加
    # 比如：融资阶段、行业领域、面试评价数等
