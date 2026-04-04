import os

# 八大核心模块
modules = [
    "01_网络协议与发包底层对抗",
    "02_加密参数定位体系",
    "03_算法与密码学破解",
    "04_前端架构与代码混淆",
    "05_运行环境与防调试对抗",
    "06_人机交互验证突破",
    "07_视觉渲染欺骗与反爬",
    "08_高级通信与泛Web生态"
]

# 每个模块下的子文件夹
sub_folders = ["01_学习笔记", "02_实战代码"]

for mod in modules:
    for sub in sub_folders:
        # 拼接路径并创建文件夹
        path = os.path.join(mod, sub)
        os.makedirs(path, exist_ok=True)

        # 在每个空文件夹中生成一个 README.md 占位，保证 Git 能够追踪
        readme_path = os.path.join(path, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            if sub == "01_学习笔记":
                f.write(f"# {mod} - 学习笔记\n\n用于记录该阶段的底层原理、理论分析与知识拆解。")
            else:
                f.write(f"# {mod} - 实战代码\n\n用于存放该阶段的爬虫代码、Hook脚本、AST清洗脚本等实战产物。")

# 忽略敏感信息的 .env 占位文件
with open(".env", "w", encoding="utf-8") as f:
    f.write("# 存放隐私配置、Cookie、代理账号，绝对不要提交到 Git！\n")

print("逆向八大模块目录骨架及隐私防线生成完毕！")