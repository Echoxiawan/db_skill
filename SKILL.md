---
name: db-inspector
description: 连接 MySQL 或 Oracle 数据库，获取表结构、读取表数据、执行只读查询。连接信息（含密码，明文存于 ~/.db_skill/connections.json，权限 600）会自动保存，下次可按名称或关键字智能提取，免重复输入。当用户需要查看数据库表结构、字段、索引、外键、查询表数据，或提到「连数据库 / 看表 / 表结构 / db 连接」时使用。
---

# 数据库结构与数据读取工具

连接 MySQL / Oracle，提取表结构与数据，并把连接信息保存下来供下次智能复用。

## 核心脚本

`scripts/db_tool.py` —— 所有功能的统一入口（子命令式 CLI），skill 模式直接调它。
`scripts/connections.py` —— 连接存储模块（被 db_tool / mcp_server 共用，一般无需直接运行）。
`scripts/mcp_server.py` —— MCP 服务封装（复用 db_tool 底层逻辑），需要 MCP 模式时启动它。

## 两种使用模式（由用户自选）

同一套能力提供两种入口，**共享同一份连接存储 `~/.db_skill/connections.json`**，互通：

1. **Skill 模式（默认）**：在对话里按需调用 `db_tool.py` 的子命令，无需常驻服务，开箱即用。
2. **MCP 模式**：把能力暴露为 MCP 工具，供 Claude Desktop / IDE 等客户端直接调用。
   默认 SSE 传输：
   ```bash
   pip install mcp
   python3 scripts/mcp_server.py                       # SSE，默认 127.0.0.1:8765
   python3 scripts/mcp_server.py --host 0.0.0.0 --port 9000
   python3 scripts/mcp_server.py --transport stdio      # 部分客户端只支持 stdio
   ```
   SSE 端点：`http://<host>:<port>/sse`。也可用环境变量 `DB_MCP_HOST/PORT/TRANSPORT`。
   暴露的工具：`list_connections` `find_connections` `save_connection`
   `rename_connection` `test_connection` `list_databases` `list_tables`
   `get_table_schema` `read_table_data` `run_query`。
   （MCP 模式**不暴露删除**连接的能力——删除是破坏性操作，仅在 skill 的 `db_tool.py delete` 手动执行。
   连库工具在成功连上后会按 `host+port+user` 智能保存/覆盖连接，与 skill 模式一致。）

   MCP 客户端配置示例（SSE）：
   ```json
   { "mcpServers": { "db-inspector": { "url": "http://127.0.0.1:8765/sse" } } }
   ```

## 首次使用：装依赖

按数据库类型按需安装：

```bash
pip install mysql-connector-python   # MySQL
pip install oracledb                 # Oracle（thin 模式，无需 Oracle Client）
pip install mcp                      # 仅 MCP 模式需要
```

## 智能连接提取（重要工作流）

用户的连接信息保存在 `~/.db_skill/connections.json`。**每次用户要操作数据库时，先按下面顺序判断是否已有可复用的连接，避免让用户重复输入：**

1. 先列出已有连接，看用户的意图能否匹配上：
   ```bash
   python3 scripts/db_tool.py list
   ```
2. 若用户给了线索（库名、host、连接名片段等），用 `find` 模糊匹配：
   ```bash
   python3 scripts/db_tool.py find shop
   ```
3. **命中唯一连接** → 直接用 `--conn <名称>` 操作，不要再问用户连接信息。
4. **命中多个** → 把脱敏后的候选列给用户，让其选一个。
5. **没命中** → 这才向用户索取连接信息（type/host/port/user/password，database 可选）。

> 提取出连接信息后，展示给用户时用 `list`/`find` 的脱敏输出（密码已打码），
> 不要把明文密码回显到对话里。

## 自动保存与覆盖

**只要用户提供了连接信息且成功连上，连接就会自动保存，无需任何额外参数。** 规则：

- 判断「是否已存在」只看 **连接地址 + 登录用户名**（即 `host + port + user`）。
  - 同一 `host:port:user` 再次连接 → **覆盖**原记录（更新密码、库名、`last_used`），名称不变、不新增。
  - 换 host、换端口或换登录用户 → 视为**新连接**，自动命名保存。
- **自动命名优先用登录用户名**（如 `ksafeature_hs_member`）。用户名通常含环境+库信息，
  既能区分不同环境下的同名库，又与判重身份中的 `user` 一致——同身份必得同名。
  无用户名时回退到库名 / host。想要自定义名称时给 `--save-as <名称>`，或事后用 `rename` 改名。
- 注意：同账号连不同库**不会**各存一条，只保留最近一次的库名。库名可每次用 `--database` 临时指定。
- 命令输出里的 `saved_as` 字段 / `test` 的提示会告知本次存成了哪个名称，可转述给用户。


## 智能识别库名 / 表名（重要工作流）

用户描述需求时**经常不会给出准确的库名或表名**（比如「看下用户表」「订单数据有多少」）。
不要直接报错或硬要用户输入，按下面的步骤自己探查并智能匹配：

### 库名缺失时

1. MySQL 不带 `--database` 也能连。先列出可用库（已过滤系统库）：
   ```bash
   python3 scripts/db_tool.py databases --conn shop-dev
   ```
2. 若只有一个业务库 → 直接用它。多个 → 结合用户语境推断，拿不准就把列表给用户选。
3. 选定后，后续命令带上 `--database <库名>`（或更新已存连接）。
   - Oracle 的「库」对应 schema/owner，`databases` 列出的是非系统 owner。

### 表名缺失或不确定时

1. 先列出全部表：
   ```bash
   python3 scripts/db_tool.py tables --conn shop-dev
   ```
2. 把用户的说法和真实表名做**语义匹配**，不要要求字面一致：
   - 「用户 / 会员」→ `users` / `t_user` / `member`
   - 「订单」→ `orders` / `t_order` / `order_info`
   - 中文描述 → 找英文/拼音表名；单数↔复数；忽略 `t_`/`tb_` 前缀。
3. **唯一高置信匹配** → 直接用，并在回复里说明「我理解你指的是 `xxx` 表」。
4. **多个候选** → 列出候选表名让用户确认，必要时各取 `schema`（不取示例行，`--sample 0`）辅助判断。
5. **匹配不到** → 把表清单展示给用户，请其指认。

> 探查表结构来辅助判断时，加 `--sample 0` 只看结构、跳过示例数据，更快也更省。



所有读库子命令都接受连接参数：`--conn <名称>`（用已存连接）或内联
`--type --host --port --user --password --database`，两者可混用（内联覆盖已存值）。
**连库成功即自动保存/覆盖**（见上节）；`--save-as <名称>` 仅用于给新连接指定自定义名称。

| 子命令 | 作用 |
|--------|------|
| `list` | 列出所有已保存连接（密码脱敏） |
| `find <关键字>` | 模糊查找连接（匹配 name/host/database/user/type） |
| `save --name <名称> <连接参数>` | 仅保存连接，不连库 |
| `delete --name <名称>` | 删除一条连接 |
| `rename --old <名> --new <名>` | 重命名一条连接 |
| `test <连接>` | 测试连接是否可用 |
| `databases <连接>` | 列出可用库 / schema（已过滤系统库） |
| `tables <连接>` | 列出库中所有表名 |
| `schema <连接> [--table T ...] [--sample N]` | 表结构：列/索引/外键 + N 行示例（默认全部表、3 行） |
| `data <连接> --table T [--limit N] [--offset M]` | 读取某表数据（默认 20 行） |
| `query <连接> --sql "SELECT ..."` | 执行只读查询（仅 SELECT/WITH，禁多语句） |

## 典型示例

```bash
# 1. 首次：直接用内联参数操作，连上即自动保存（无需先 save）
python3 scripts/db_tool.py tables --type mysql \
    --host 127.0.0.1 --port 3306 --user root --password 123456 --database shop
#    → 输出 saved_as: "mysql-127.0.0.1-root"，下次即可复用

# 2. 之后：按名称操作（也可用 find 模糊定位）
python3 scripts/db_tool.py tables --conn mysql-127.0.0.1-root
python3 scripts/db_tool.py schema --conn mysql-127.0.0.1-root --table users --table orders
python3 scripts/db_tool.py data   --conn mysql-127.0.0.1-root --table users --limit 50

# 3. 想要自定义名称：加 --save-as（Oracle 示例）
python3 scripts/db_tool.py tables --type oracle --host 10.0.0.9 --port 1521 \
    --user scott --password tiger --database ORCLPDB1 --save-as ora-test

# 4. 模糊找连接再用
python3 scripts/db_tool.py find ora      # → 看到 ora-test
python3 scripts/db_tool.py schema --conn ora-test

# 5. 同账号密码变了：再连一次就自动覆盖原记录（host+port+user 相同）
python3 scripts/db_tool.py test --type mysql \
    --host 127.0.0.1 --port 3306 --user root --password new-pwd --database shop
```

## 行为约定

- **MySQL** 的 `--database` 是 schema 名；**Oracle** 的 `--database` 是 service name，
  且只读取当前登录用户（owner = 大写 user）名下的表。
- `query` 子命令强制只读：只允许 `SELECT` / `WITH` 开头，禁止分号多语句，防止误改数据。
- 表名/列名做了标识符白名单校验（仅字母数字下划线点），数据值走参数化绑定，避免注入。
- 输出统一为 JSON，便于进一步分析；`sample_rows` 等大字段在需要时再取。

## 安全说明

连接密码以**明文**存储在 `~/.db_skill/connections.json`（文件权限 600，仅本人可读写）。
此设计面向**本地开发**，请勿在共享主机或生产环境中保存生产库密码。
