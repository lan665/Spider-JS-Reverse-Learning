# 某省公共资源交易平台 Response 响应体解密分析

## 1. 目标接口与抓包分析
![响应体密文抓包分析](./img/01_response_data.png)

* **目标接口:** 列表查询数据接口 (如 `/business/list`)
* **请求方式:** `POST`
* **加密特征:** 服务器返回的 JSON 响应体中，核心数据存放在 `Data` 字段，其值为一段高熵的 Base64 密文字符串，导致无法直接提取标段信息。前端页面上却能正常显示明文。


## 2. 逆向定位过程

### 2.1使用油猴 Hook `JSON.parse`

使用 Tampermonkey 在网页生命周期的极早期 (`document-start`) 注入以下代码，强行劫持并重写全局的 `JSON.parse` 方法。利用页面上可见的明文（如“公共资源交易中心”）作为诱饵进行拦截。

    javascript
    // ==UserScript==
    // @name         通用 JSON.parse 拦截器
    // @match        *://*[.example-target.com/](https://.example-target.com/)* // [!脱敏] 替换为目标网站的泛域名
    // @run-at       document-start
    // ==/UserScript==
    
    (function() {
        const originalParse = JSON.parse;
        JSON.parse = function(text, reviver) {
            if (text && typeof text === 'string' && text.indexOf('公共资源交易中心') !== -1) {
                console.log("🔥 拦截到关键明文解析");
                debugger; // 强行冻结执行流
            }
            return originalParse(text, reviver);
        };
    })();
### 2.3 追溯调用堆栈 (Call Stack)
![响应体密文抓包分析](img/02_hook_json_parse.png)

刷新页面重新触发网络请求，代码成功在 Hook 函数内断住。
展开右侧的 Call Stack (调用堆栈)，向下回溯一层（跳出我们的油猴脚本），瞬间穿透底层框架，精准降落到真实的业务解密现场——Axios 响应拦截器：

    JavaScript
    // 响应拦截器核心逻辑
    return "200" === e.statusCode 
        ? JSON.parse(b(e.data)) 
        : "200" === e.State 
            ? JSON.parse(b(e.Data)) // ⬅️ 目标密文 e.Data 被传入 b()，解密后喂给 JSON.parse
            : (Object(o["Message"])...)
### 3. 加密算法破解
![响应体密文抓包分析](img/03_to_decrypt.png)

单步进入发现的核心解密函数 b(t)，进行代码格式化后，提取出底层解密逻辑：

    JavaScript
    function b(t) {
        var e = h.a.enc.Utf8.parse(r["e"])
          , n = h.a.enc.Utf8.parse(r["i"])
          , a = h.a.AES.decrypt(t, e, {
            iv: n,
            mode: h.a.mode.CBC,
            padding: h.a.pad.Pkcs7
        });
        return a.toString(h.a.enc.Utf8)
    }
**3.1 识别算法特征**
    代码虽然经过混淆，但暴露了极具辨识度的 crypto-js 标准库调用特征：
    
    模式与填充: 明确指出了 mode.CBC 和 pad.Pkcs7。
    算法确认: 调用了 AES.decrypt，确认为标准 AES-CBC 对称加密，无底层逻辑魔改。

**3.2 突破闭包，缴获 Key 与 IV (踩坑点)**
    踩坑记录： 在 Hook 触发的 debugger 状态下，若直接在控制台执行 r["e"] 获取密钥，系统会抛出 ReferenceError: r is not defined。这是因为当前控制台的作用域停留在了全局 Hook 函数中，无法穿透 Webpack 的局部闭包。
    
    破局方法： 在右侧 Call Stack 面板，鼠标单击属于 b 函数的那一层栈帧，强制切换执行上下文。
    此时重新在控制台输入 r["e"] 和 r["i"]，成功缴获硬编码的明文密钥对：
    Key: ****** (出于安全合规要求，已遮挡字符) 
    IV: ****** (出于安全合规要求，已遮挡字符)

## 4. Python 还原代码
    请参考 ../../02_实战代码/response.py