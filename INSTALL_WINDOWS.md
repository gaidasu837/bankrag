# BankRAG 新电脑安装与恢复完整教程

更新：现已增加Ollama抽取、12条审核声明和问答页面。本页保留基础环境恢复步骤；完成第8节后请继续 [问答系统恢复与启动](QA_GUIDE.md)。第9节原先暂缓的模型选型现已确定为qwen3:14b。当前问答是原文证据阅读版，并非完整自由生成GraphRAG。

适用：Windows 11 x64，Anaconda Prompt / CMD。编写于2026-09-08。
只复制代码块内的命令，不复制 `(bankrag) C:\...>` 提示符。所有下划线、冒号、括号均使用英文半角，不添加反斜杠转义。每条命令执行成功后再继续。

## 1. 当前能恢复什么

项目已经完成15份工行官方网页、35个原文片段的SQLite存储与Neo4j证据图。恢复后的结构为 `BankRagSource → BankRagDocument → BankRagChunk`，原始网页和哈希都在迁移包内。
这不是已完成的聊天机器人：正文清洗、业务关系抽取、时效核验、向量检索和Ollama接入仍待建设。安装Ollama不会自动完成这些功能。
无需独显即可恢复和查询当前证据图。新电脑需要联网下载软件、Python依赖和Neo4j镜像；软件安装目录不会随压缩包迁移。

## 2. 安装Miniconda（已有Anaconda则跳过）

普通CMD执行，下载到用户下载目录：

```bat
cd /d "%USERPROFILE%\Downloads"
curl.exe -L --fail https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe -o Miniconda3-latest-Windows-x86_64.exe
start /wait "" Miniconda3-latest-Windows-x86_64.exe
```

安装界面选择Just Me，使用默认路径即可；不必加入全局PATH，不必注册为默认Python。阅读并按你的情况接受安装条款。完成后从开始菜单打开Anaconda Prompt：

```bat
conda --version
```

如果找不到命令，确认打开的是Anaconda Prompt；不要因此重复安装。
官方说明：[Miniconda Windows安装](https://www.anaconda.com/docs/getting-started/miniconda/install/windows-cli-install)。

## 3. 安装Git与GitHub CLI（用于私有仓库下载）

CMD执行：

```bat
winget install --id Git.Git -e --source winget
winget install --id GitHub.cli -e --source winget
```

关闭终端并重新打开Anaconda Prompt，使PATH更新，然后执行：

```bat
git --version
gh --version
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
```

按提示在浏览器登录拥有仓库权限的GitHub账号。不要在聊天、代码或文档中保存令牌。
若没有winget，可在[Git官网](https://git-scm.com/install/windows)和[GitHub CLI官网](https://cli.github.com/)下载安装程序。也可不装Git，直接在浏览器登录GitHub并下载下文的迁移ZIP。

## 4. 安装WSL 2和Docker Desktop

先在CMD检查：

```bat
wsl --status
wsl --version
```

如果WSL未安装，以管理员身份打开CMD执行：

```bat
wsl --install --no-distribution
```

按系统提示重启电脑。然后在管理员CMD执行更新：

```bat
wsl --update
wsl --set-default-version 2
```

Docker Desktop使用自己的Linux环境，不要求你另外安装Ubuntu。安装Docker Desktop：

```bat
winget install --id Docker.DockerDesktop -e --source winget
```

完成后启动：

```bat
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

若使用了自定义安装路径，从开始菜单打开Docker Desktop。首次打开完成界面提示，启用WSL 2后端，等待引擎运行。再打开Anaconda Prompt检查：

```bat
docker --version
docker info
docker compose version
```

必须看到docker info的Server部分正常显示；仅Client正常还不能运行数据库。
如果没有winget，在[Docker官方Windows安装页面](https://docs.docker.com/desktop/setup/install/windows-install/)下载Windows x86_64安装程序。若提示虚拟化不可用，检查任务管理器CPU页面的虚拟化状态，并按电脑厂商说明在BIOS/UEFI启用；重启后再试。

## 5. 下载和解压项目（两种方式任选一种）

### 方式A：命令行克隆

下面使用用户目录，无需新电脑存在E盘。如果bankrag目录已存在，请选择新的空目录，不覆盖正在使用的项目。

```bat
cd /d "%USERPROFILE%"
git clone https://github.com/gaidasu837/bankrag.git
cd bankrag
python -m zipfile -e dist\bankrag-portable.zip restored
cd restored
```

注意：克隆仓库本身不等于已恢复数据库。数据库在dist中的迁移包内，必须解压。后续命令均在restored目录执行。

### 方式B：浏览器下载

登录GitHub，打开[迁移包](https://github.com/gaidasu837/bankrag/blob/main/dist/bankrag-portable.zip)，点击Download raw file下载ZIP；不要把网页另存为ZIP。解压到自选目录，在Anaconda Prompt用 `cd /d "实际解压目录"` 进入。

### 检查文件

```bat
dir environment.yml
dir compose.yaml
dir data\icbc.sqlite3
dir data\raw\*.html
```

需要同时存在数据库和15个原始HTML，不能只复制SQLite文件。

## 6. 创建Conda环境并验证数据

```bat
conda env create -f environment.yml
conda activate bankrag
set PYTHONPATH=%CD%\src
python --version
python -m bankrag.import_graph --dry-run
python -m unittest discover -s tests -v
```

预期Python 3.11，validated_documents为15，validated_chunks为35，6项测试通过。dry-run不会修改Neo4j。
若已有bankrag环境，先 `conda activate bankrag` 检查是否可用；需要补齐依赖时使用 `conda env update -n bankrag -f environment.yml`，不用删除旧环境。
若Conda提示条款，请阅读后自主决定是否接受，按其提示完成；不要绕过提示。

## 7. 启动Neo4j

先查端口：

```bat
netstat -ano | findstr "LISTENING" | findstr ":17474 :17687"
docker ps -a
```

端口无输出则继续。若已有服务占用，不终止它：优先确认是否就是原来的bankrag数据库。若确需改端口，编辑compose.yaml的左侧主机端口，右侧容器7474/7687保持不变，导入时用 `--uri bolt://localhost:新端口`。

```bat
docker pull neo4j:2026.07.1
set /p BANKRAG_PASSWORD=Enter a password with at least 12 letters and digits:
docker compose up -d
```

等号后面是提示文字，回车后再输入你自己的密码；这里输入可见，不要截图分享。密码不会写入项目文件，但Docker容器管理员可以查看容器配置。保存好密码，导入时还要输入。
Compose创建的容器名通常为bankrag-neo4j-1，与旧电脑手工docker run创建的bankrag-neo4j不同。通过compose服务名neo4j管理即可。

```bat
docker compose logs --tail 60 neo4j
docker compose ps
```

看到Started.且容器为Up后继续。不需要自己执行CREATE DATABASE；使用默认neo4j数据库。数据持久保存在Docker命名卷中。

Compose配置要求密码变量存在，所以上述检查完成前不要清除。若另开窗口运行Compose命令，需重新设置该变量。数据库已有数据时，更改此变量不会修改已有数据库密码。

官方说明：[Neo4j Docker部署](https://neo4j.com/docs/operations-manual/current/docker/introduction/)。

## 8. 导入并验证证据图

```bat
python -m bankrag.import_graph
```

提示Neo4j password时输入密码，此处输入不显示字符，属于正常情况。成功输出Import committed；脚本使用MERGE，重复导入相同文档不会重复创建节点。

```bat
docker compose exec neo4j cypher-shell -u neo4j -d neo4j
```

输入密码进入Cypher终端后，逐条执行完整单行查询：

```cypher
MATCH (d:BankRagDocument) RETURN count(d) AS documents;
MATCH (c:BankRagChunk) RETURN count(c) AS chunks;
MATCH (:BankRagDocument)-[r:HAS_CHUNK]->(:BankRagChunk) RETURN count(r) AS links;
```

结果应为15、35、35。查询必须以英文分号结束，`count(r)`的括号必须是英文半角。退出：

```text
:exit
```

回到CMD后清理当前窗口密码变量：

```bat
set BANKRAG_PASSWORD=
```

浏览器打开 http://localhost:17474 ，连接地址 bolt://localhost:17687，用户名neo4j。查询证据路径：

```cypher
MATCH p=(:BankRagSource)-[:HAS_VERSION]->(:BankRagDocument)-[:HAS_CHUNK]->(:BankRagChunk) RETURN p LIMIT 20;
```

这些路径证明原文出处，不代表业务结论已经通过事实与时效审核。

## 9. Ollama安装（可选，模型选型待新电脑配置确认）

```bat
curl.exe -L --fail https://ollama.com/download/OllamaSetup.exe -o "%TEMP%\OllamaSetup.exe"
start /wait "" "%TEMP%\OllamaSetup.exe"
```

重新打开终端：

```bat
ollama --version
ollama list
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
```

nvidia-smi不可用不代表一定没有独显，可在任务管理器的性能/GPU查看型号和专用显存。共享内存不是专用显存。请根据新电脑显卡型号、显存、内存再确定模型，目前不预设模型下载命令。
Windows安装版通常后台运行，无需重复执行ollama serve。只有后台服务未运行时才手动执行该命令。
官方说明：[Ollama Windows](https://docs.ollama.com/windows)。

## 10. 日常启动、停止与备份

每次打开Anaconda Prompt后进入项目目录：

```bat
conda activate bankrag
set PYTHONPATH=%CD%\src
```

启动Docker Desktop。如果是此前已创建的Compose容器，可在docker ps -a中确认名称后执行：

```bat
docker start bankrag-neo4j-1
docker logs --tail 30 bankrag-neo4j-1
```

若实际名字不同，用实际名称替换。停止容器保留数据：

```bat
docker stop bankrag-neo4j-1
```

不要执行 `docker compose down -v`，它会删除命名卷中的数据库。
重新生成当前SQLite证据库迁移包：

```bat
python scripts\package_portable.py
```

输出dist\bankrag-portable.zip，包含原始网页、SQLite、代码和教程。打包程序会解压到临时目录校验原文哈希及片段一致性。
该操作不备份仅存在于Neo4j的新关系；未来增加业务图谱后需另做Neo4j备份。当前15/35证据图可由SQLite重建。

## 11. 常见问题

| 现象 | 处理 |
|---|---|
| docker info只有Client，提示找不到LinuxEngine | 启动Docker Desktop，等待引擎完成启动 |
| 镜像下载长时间不动 | 等待片刻；确实停滞可Ctrl+C，再执行docker pull neo4j:2026.07.1 |
| BANKRAG_PASSWORD未设置 | 在同一CMD窗口重新执行set /p，再运行Compose |
| 数据库认证失败 | 使用首次创建该数据卷时的密码；不要删除卷来尝试重置 |
| No module named bankrag | 确认当前为项目目录，执行set PYTHONPATH=%CD%\src |
| No module named neo4j | conda activate bankrag，然后python -m pip install "neo4j>=6,<7" |
| 找不到SQLite或raw文件 | 确认迁移ZIP已解压，当前目录包含data和src |
| 哈希或片段校验失败 | 停止导入，重新取得完整迁移包，不跳过证据校验 |
| Cypher一直等待 | 缺RETURN或结尾分号；Ctrl+C取消后复制完整单行语句 |
| Invalid input '）' | 改成英文半角括号，不输入中文标点 |
| 片段统计为15 | 检查查询标签应为BankRagChunk，不是BankRagDocument |
| GitHub 404或Repository not found | 私有仓库需有权限，gh auth status检查登录账号 |

## 12. 完成检查

能读取15份文档与35个片段；6项测试通过；Neo4j图中计数15/35/35；原始HTML仍保留；没有上传密码。达到这些条件代表当前阶段恢复完成，随后再继续清洗与模型抽取。
