# db-inspector

连接 **MySQL / Oracle**，获取表结构、读取表数据、执行只读查询。连接信息会自动保存，
下次按名称或关键字智能复用，免重复输入。

提供两种使用方式，**共享同一套底层实现**：

- **Skill 模式** —— 在 Claude 对话里按需调用，开箱即用，无需常驻服务。
- **MCP 模式** —— 暴露为 MCP 工具，供 Claude Desktop / IDE 等客户端调用；可本地直跑，也可用 **Docker** 部署。

---

## 目录结构

```
db_skill/
├── SKILL.md                  # Skill 模式入口与工作流说明
├── Dockerfile                # MCP 服务镜像
├── docker-compose.yml        # 一键启动 MCP（streamable-http）
├── .dockerignore
├── README.md
└── scripts/
    ├── db_tool.py            # 统一 CLI（Skill 模式调它）
    ├── connections.py        # 连接存储（两种模式共用）
    ├── mcp_server.py         # MCP 服务封装（复用 db_tool 底层逻辑）
    └── requirements.txt      # 依赖
```

---

## 能力一览

| 能力 | 说明 |
|------|------|
| 表结构 | 列 / 索引 / 外键，可附带示例行 |
| 表数据 | 分页读取（limit / offset） |
| 只读查询 | 仅 `SELECT` / `WITH`，禁多语句，防误改 |
| 库 / 表探查 | 列库、列表，支持不指定库名先探查 |
| 连接管理 | 保存 / 查找 / 重命名；连库成功自动保存覆盖 |

**自动保存规则**：连库成功后，按 `host + port + user` 判重——同身份覆盖原记录，
不同则新建（默认用登录用户名命名）。

---

## 方式一：Skill 模式

在 Claude 对话里直接表达需求（如「看下 hs_member 库的 member 表结构」），
Claude 会自动加载本 skill 并调用 `scripts/db_tool.py`。

也可手动运行 CLI：

```bash
# 按需装驱动
pip install mysql-connector-python   # MySQL
pip install oracledb                 # Oracle

# 首次：内联连接，连上即自动保存
python3 scripts/db_tool.py tables --type mysql \
    --host 127.0.0.1 --port 3306 --user root --password 123456 --database shop

# 之后：按名称复用
python3 scripts/db_tool.py schema --conn root --table users
python3 scripts/db_tool.py data   --conn root --table users --limit 50
```

连接信息存于 `~/.db_skill/connections.json`（权限 600）。子命令详见 [SKILL.md](SKILL.md)。

---

## 方式二：MCP 模式（本地直跑）

```bash
pip install -r scripts/requirements.txt   # 含 mcp

# 无参数启动 = 默认 streamable-http，监听 127.0.0.1:8765，端点 /mcp
python3 scripts/mcp_server.py

# 自定义地址 / 端口
python3 scripts/mcp_server.py --host 0.0.0.0 --port 9000

# 切换传输方式
python3 scripts/mcp_server.py --transport sse      # 旧版 SSE（端点 /sse）
python3 scripts/mcp_server.py --transport stdio    # stdio（部分客户端只支持这个）
```

也可用环境变量覆盖：`DB_MCP_HOST` / `DB_MCP_PORT` / `DB_MCP_TRANSPORT`。

端点：

- **streamable-http（默认）**：`http://<host>:<port>/mcp`
- SSE：`http://<host>:<port>/sse`

---

## 方式三：Docker 部署 MCP（推荐用于常驻服务）

> 需先启动 Docker（Docker Desktop 或 dockerd）。

### 用 docker-compose（最简单）

```bash
# 构建并后台启动
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

启动后 streamable-http 端点为 `http://localhost:8765/mcp`。连接信息持久化到宿主机 `./data/connections.json`。

### 用 docker 裸命令

```bash
# 构建镜像
docker build -t db-inspector-mcp .

# 运行：映射端口 + 挂载持久化目录
docker run -d --name db-inspector-mcp \
  -p 8765:8765 \
  -v "$(pwd)/data:/data" \
  db-inspector-mcp
```

### 容器环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_MCP_HOST` | `0.0.0.0` | 监听地址（容器内必须 `0.0.0.0` 才能对外暴露） |
| `DB_MCP_PORT` | `8765` | 监听端口 |
| `DB_MCP_TRANSPORT` | `streamable-http` | 传输方式：`streamable-http` / `sse` / `stdio` |
| `DB_SKILL_HOME` | `/data` | 连接信息存储目录（挂卷持久化） |

### 关于连接信息共享

Docker 模式默认把连接存到挂载的 `./data`，与本地 Skill 模式的 `~/.db_skill` **相互隔离**。
若想让两者共用同一份连接，把宿主机的 `~/.db_skill` 挂载进去即可：

```bash
docker run -d --name db-inspector-mcp \
  -p 8765:8765 \
  -v "$HOME/.db_skill:/data" \
  db-inspector-mcp
```

---

## MCP 客户端配置

**streamable-http（默认，推荐）**：

```json
{
  "mcpServers": {
    "db-inspector": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

旧版 SSE（仅当客户端不支持 streamable-http 时，需以 `--transport sse` 启动服务）：

```json
{
  "mcpServers": {
    "db-inspector": {
      "url": "http://127.0.0.1:8765/sse"
    }
  }
}
```

### 暴露的 MCP 工具（10 个）

所有连库类工具都接受 `conn`（已存连接名）**或**内联参数
（`type` / `host` / `port` / `user` / `password` / `database`），两者可混用（内联覆盖已存值）；
连库成功后会按 `host+port+user` 自动保存/覆盖，返回里带 `saved_as` 告知存成的名称。

**连接管理类（不连库）**

| 工具 | 参数 | 功能 |
|------|------|------|
| `list_connections` | — | 列出所有已保存连接（密码脱敏） |
| `find_connections` | `keyword` | 按关键字模糊查找连接（匹配 name/host/database/user/type），密码脱敏 |
| `save_connection` | `name, type, host, user, password, port?, database?` | 仅保存一条连接信息，不实际连库 |
| `rename_connection` | `old, new` | 重命名一条连接 |

**连库操作类**

| 工具 | 参数 | 功能 |
|------|------|------|
| `test_connection` | 连接参数 | 测试连接是否可用，成功后自动保存/覆盖 |
| `list_databases` | 连接参数 | 列出可用库 / schema（已过滤系统库），用户没指定库名时先探查 |
| `list_tables` | 连接参数 | 列出库中所有表名 |
| `get_table_schema` | `table?, sample=3` + 连接参数 | 表结构：列/索引/外键 + `sample` 行示例；`table` 留空返回全部表；`sample=0` 只看结构 |
| `read_table_data` | `table, limit=20, offset=0` + 连接参数 | 分页读取某表数据 |
| `run_query` | `sql, limit=200` + 连接参数 | 只读查询，仅 `SELECT` / `WITH`，禁多语句 |

---

## 安全说明

- 连接密码以**明文**存储在连接文件中（文件权限 600）。本设计面向**本地 / 内网开发**，
  请勿在公网或共享主机上保存生产库密码。
- 只读查询强制校验（仅 `SELECT` / `WITH`、禁分号多语句）；表名 / 列名做标识符白名单校验，
  数据值参数化绑定，避免注入。
- Docker 对外暴露端口时注意网络边界：`-p 8765:8765` 会绑定到宿主机所有网卡，
  仅本机使用可改为 `-p 127.0.0.1:8765:8765`。
