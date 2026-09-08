# 新电脑恢复（Anaconda Prompt / CMD）

最新迁移包同时包含抽取结果和问答界面。完成本页证据图恢复后，按 [问答恢复说明](QA_GUIDE.md) 重建12条声明并启动页面。

详细步骤见 [完整安装教程](INSTALL_WINDOWS.md)。克隆后进入bankrag目录，执行 `python -m zipfile -e dist/bankrag-portable.zip restored`，再 `cd restored` 后执行下文命令。

安装 Miniconda/Anaconda 和 Docker Desktop，并启动 Docker Desktop Linux 引擎。
解压 bankrag-portable.zip 到任意目录，在 Anaconda Prompt 切换至解压后的项目目录。
也可从私有 GitHub 仓库克隆：`git clone https://github.com/gaidasu837/bankrag.git`。

```bat
conda env create -f environment.yml
conda activate bankrag
set PYTHONPATH=%CD%\src
python -m bankrag.import_graph --dry-run
python -m unittest discover -s tests -v
```

预期校验 15 份文档、35 个片段。原始 HTML 按哈希从数据库旁的 raw 目录定位，不依赖旧电脑的盘符。

先确认新电脑端口没有占用：

```bat
netstat -ano | findstr "LISTENING" | findstr ":17474 :17687"
```

没有输出时启动（只在新电脑执行；旧电脑已有独立容器，不重复启动）：

```bat
set /p BANKRAG_PASSWORD=Neo4j password (12 or more letters and digits):
docker compose up -d
docker compose logs --tail 60 neo4j
set BANKRAG_PASSWORD=
```

日志出现 Started. 后：

```bat
python -m bankrag.import_graph
```

输入刚设置的密码。访问 http://localhost:17474 ，连接 bolt://localhost:17687 ，用户名和数据库名均为 neo4j。

核验：

```cypher
MATCH (d:BankRagDocument) RETURN count(d);
MATCH (c:BankRagChunk) RETURN count(c);
MATCH (:BankRagDocument)-[r:HAS_CHUNK]->(:BankRagChunk) RETURN count(r);
```

预期 15、35、35。SQLite 和原始网页是恢复来源，未搬运 Docker 引擎、Conda 安装目录或旧 Neo4j 数据卷。旧库中如果以后增加了仅存于 Neo4j 的数据，必须另行备份，不能只靠此包恢复。

所有资料仍待时效核验；业务实体抽取、Ollama模型和完整GraphRAG问答尚未搭建。此包不含密码、API密钥或模型文件。
