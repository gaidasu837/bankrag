# 本地问答界面

## 新电脑恢复到问答阶段

最新迁移包包含成功抽取的两个JSON文件，可重建12条声明。完成INSTALL_WINDOWS.md的环境安装和证据图导入后执行：

```bat
set PYTHONPATH=%CD%\src
python -m bankrag.review_pilot --input data/processed/pilot-20260908T065602050283Z --import-neo4j
```

安装并启动Ollama，下载所用模型（约9.3GB文件，运行另需内存）：

```bat
ollama pull qwen3:14b
python -m bankrag.qa_app
```

无需重新抽取。看到Open http://127.0.0.1:8501后，保持窗口运行并打开此地址。等待网页请求是正常状态。

这是基于12条审核规则声明的证据阅读原型，不是完整向量/社区检索GraphRAG系统。
模型只选择相关原文，页面直接引用原文以避免新增无出处事实。选择仍可能遗漏或误判；不保证回答覆盖所有问题条件。
文档时效未核验，不回答实时利率或授信结论。先完成SQLite、原始HTML和Neo4j证据/声明导入。

在Anaconda Prompt中：

```bat
cd /d E:\workplace\codex\nlp
conda activate bankrag
set PYTHONPATH=%CD%\src
python -m bankrag.qa_app
```

按提示输入Neo4j密码（不回显）。保持窗口运行，打开 http://127.0.0.1:8501 。
原Neo4j连接为bolt://localhost:17687，模型为qwen3:14b。
若端口8501占用，可 `python -m bankrag.qa_app --port 8502` 并访问相应端口。
停止按Ctrl+C。后台服务只监听本机，不在页面填写或保存数据库密码。

首轮测试：账户分为哪几类、部分提前支取如何计息、能否约定转存。反例：今天贷款利率多少、我一定能获批贷款吗。反例应提示证据不足；如返回无关原文，请记录反馈。
每次请求重新验证Neo4j引用与本地快照哈希、文档位置；模型返回不存在的证据编号则停止回答。
同一时间仅处理一个请求；CPU可能需要几分钟。没有Neo4j写操作。模型请求自动绕过系统代理。

页面功能：问题输入、示例问题、等待计时、原文答案、条件/审核说明、官方来源链接、日期与证据链展开。
历史只保存在当前服务进程内，最多30条任务，重启清空。最新迁移包可重建证据图及本次12条声明，不包含Neo4j其他手工改动或完整数据库卷备份。

启动失败：检查Docker、Neo4j密码、Ollama服务以及当前工作目录。依赖缺失执行 `python -m pip install "neo4j>=6,<7"`。
