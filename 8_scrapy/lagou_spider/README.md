# 📝 实战复盘：企业级非对称加密逆向与 Scrapy 异步架构集成全过程

> **文档定位**：记录从前端网络抓包、JS 加解密算法还原，到 Scrapy 爬虫工程化落地的标准流程。
> **目标站点特征**：动态密钥协商 (RSA+AES)、防篡改签名头、全密文响应、阿里云 WAF 风控防护。

---

##  阶段一：加密参数定位与逻辑拆解

### 1. 案发现场分析 (抓包特征)
通过浏览器 Network 面板观察业务接口（如 `0-0-0-0.json`），发现以下强加密特征：
* **Request Headers**：存在三个未知的自定义签名头：`X-S-HEADER`, `X-K-HEADER`, `X-SS-REQ-HEADER`。
* **Response Body**：返回的并非明文 JSON，而是无意义的 Base64 密文串。
* **前置通信**：在请求业务接口前，总会先向 `/agreement` 发起一次预检请求。

### 2. 断点定位技巧
由于网络流完全加密，无法通过传统的全局搜索（Search）定位参数。采用**“解密结果反推法”**：
1. 编写 Tampermonkey (油猴) 脚本，对 `JSON.parse` 进行全局 Hook。
2. 当拦截到明文数据被解析时，触发 `debugger`。
3. 通过 DevTools 的 **Call Stack (调用堆栈)** 向上回溯，穿透第三方底层库（如 `ajax-hook`），精准定位到高内聚的业务层加密文件 `secret.js`。

---

##  阶段二：密码学架构识破与算法还原

在 `secret.js` 中，识破了目标站点经典的**“数字信封（混合加密）”**架构骗局。

### 1. 识破“动态密钥协商”骗局
* **误区**：最初认为缓存中的 `aesKey` 是服务端下发的。
* **真相**：通过源码发现 `generatekey(32)`，实锤 32 位随机 AES 密钥是**前端本地动态生成**的。
* **协商闭环**：前端使用内置的 `RSA 公钥` 对这个 AES 密钥进行加密，通过 `/agreement` 接口发送给服务端。服务端解密后，返回一个 `secretKeyValue` 作为本次会话的**唯一凭证**。

### 2. 算法还原 (Python 重构)
脱离浏览器，使用 Python 的 `pycryptodome` 库进行 1:1 重构：
* **AES-CBC-PKCS7**：用于响应体解密与 `X-S-HEADER` (包含 SHA256 哈希值) 的防篡改签名。
* **RSA-PKCS1_v1_5**：使用 PEM 公钥证书，专用于将 AES 密钥护送至服务端。

---

##  阶段三：Scrapy 工程化集成与中间件开发

将写死的单线程 Python 脚本，重构为工业级并发框架的代码范式。核心思想是：**让爬虫 Spider 只负责业务逻辑，将加解密与风控对抗全部下沉至中间件 (Middleware)。**

### 1. 中间件核心改造 (`middlewares.py`)
打造名为 `LagouSpiderDownloaderMiddleware` 的核心安检口：
* **挂载全局协商**：利用 Scrapy 的 `spider_opened` 信号钩子。在爬虫启动的一瞬间，利用 `requests` 同步发起预检，完成全网密钥协商，并将凭证保存为全局变量。
* **动态签名注入**：在 `process_request` 方法中，拦截所有发往业务接口的请求。全自动计算当前的 `X-S-HEADER`，并注入有效的 WAF Cookie (`acw_tc` 等) 与浏览器原生指纹 (`User-Agent`)。

### 2. 补全风控溯源头 (踩坑复盘)
**痛点**：在 Scrapy 引擎发出请求后，遭遇 WAF 秒级封杀，返回 `<title>滑动验证页面</title>`。
**排雷**：经比对日志，发现 Scrapy 发出的请求丢失了溯源标识。
**修复**：在 Spider 发起 `yield scrapy.Request()` 时，强行绑死 `Origin` 和 `Referer` 参数，成功伪装成浏览器内发出的合法 AJAX 请求，突破 WAF 封锁。

### 3. Spider 响应解密 (`spiders/lagou.py`)
Spider 收到 HTTP 200 的响应后，直接调用由中间件传递过来的 `decrypt_response` 函数。将密文盲盒拆开后，解析出明文 JSON 数据并组装成 `Item` 抛给管道。

---

##  阶段四：Twisted 异步持久化入库

为了防止爬虫的高并发特性被数据库的同步 I/O 阻塞，引入 Twisted 异步连接池。

### 1. 禁用同步 PyMySQL
坚决不在 Pipeline 中直接编写 `cursor.execute()` 和 `db.commit()`。

### 2. 构建异步管道 (`pipelines.py`)
* 使用 `adbapi.ConnectionPool` 构建异步连接池。
* 通过 `@classmethod def from_crawler` 钩子，安全地从 `settings.py` 中读取数据库密码配置，解决实例化的传参冲突。
* 在 `do_insert` 中编写 `ON DUPLICATE KEY UPDATE` 的 SQL 语句，结合 `db_pool.runInteraction()` 将插入操作扔给后台线程池异步执行，实现海量数据的丝滑入库。

---

##  阶段性挂起：企业级 WAF Cookie 攻防

**当前状态：半自动化（降速 + 手动搬运 Cookie）**

在本项目中，我们遭遇了业内顶级的**阿里云 WAF 企业级防火墙**。该防火墙的核心难点在于其动态下发的安全 Cookie（如 `acw_sc__v3`, `acw_tc` 等），具有极高的逆向门槛。

###  为什么暂停在 Cookie 自动化获取阶段？
1. **极端代码混淆**：WAF 下发的 JS 代码包含了二代/三代壳，采用了复杂的 AST 控制流平坦化，难以直接静态分析。
2. **海量指纹采集**：生成 Cookie 的算法重度依赖浏览器底层硬件与运行环境指纹（Canvas, WebGL, WebRTC 等），直接使用纯 Node.js 环境（如 JSDOM）极易触发风控，导致下发废弃 Cookie。
3. **极短的生命周期与高频变动**：一旦触发风控，Cookie 会瞬间失效并弹出极其恶心的滑动验证码。

---

##  实战总结

1. **环境隔离思维**：“业务算法加密”与“WAF 环境风控”是两道独立的防线。算法全对不代表能拿数据，必须配合合法的 Cookie 与原生 Header 指纹。
2. **高 ROI 爬虫策略**：面对阿里系复杂的动态 WAF Cookie (如极端 AST 混淆与硬件指纹)，在业务需求可控的情况下，采用“**手动获取有效 Cookie + Scrapy 降速限流 (`DOWNLOAD_DELAY`)**”的半自动化策略