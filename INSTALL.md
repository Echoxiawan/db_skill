# db-inspector 安装指南

连接 MySQL / Oracle，获取表结构、读取表数据、执行只读查询。连接信息自动保存，下次按名称或关键字智能复用。

支持 Claude Code、Kiro、Cursor、Windsurf、Cline、Gemini CLI、Codex CLI、Aider 等主流 AI 编程工具。

**仓库地址**：`https://github.com/Echoxiawan/db_skill`

---

## 目录

- [方式一：从远程仓库安装（推荐）](#方式一从远程仓库安装推荐)
- [方式二：从本地仓库安装](#方式二从本地仓库安装)
- [Python 依赖安装](#python-依赖安装)
- [MCP 模式（可选）](#mcp-模式可选)
- [安装验证](#安装验证)
- [卸载](#卸载)
- [常见问题](#常见问题)

---

## 方式一：从远程仓库安装（推荐）

### Claude Code

技能目录：`~/.claude/skills/db-inspector/`

```bash
git clone https://github.com/Echoxiawan/db_skill.git ~/.claude/skills/db-inspector
```

触发方式：对话中输入 `/db-inspector`，或直接说「看表结构 / 连数据库 / 查表数据」

---

### Kiro

全局技能目录：`~/.kiro/skills/db-inspector/`

```bash
git clone https://github.com/Echoxiawan/db_skill.git ~/.kiro/skills/db-inspector
```

触发方式：对话中输入 `/db-inspector`，或直接说「看表结构 / 连数据库」

---

### Cursor

Cursor 使用项目级 Rules 文件（`.cursor/rules/*.mdc`），在当前项目根目录执行：

```bash
mkdir -p .cursor/rules
curl -L https://raw.githubusercontent.com/Echoxiawan/db_skill/main/SKILL.md \
  -o .cursor/rules/db-inspector.mdc
```

> Cursor 全局 Rules（所有项目生效）：
> ```bash
> mkdir -p ~/.cursor/rules
> curl -L https://raw.githubusercontent.com/Echoxiawan/db_skill/main/SKILL.md \
>   -o ~/.cursor/rules/db-inspector.mdc
> ```

> 注意：Rules 模式只加载 SKILL.md 文本，不含 `scripts/` 脚本。需要执行 CLI 时请改用「方式二」完整克隆仓库到本地，或参考 SKILL.md 内的命令手动运行。

---

### Windsurf

**全局规则**（所有工作区生效，推荐）

```bash
curl -L https://raw.githubusercontent.com/Echoxiawan/db_skill/main/SKILL.md \
  >> ~/.codeium/windsurf/memories/global_rules.md
```

**项目级规则**（仅当前项目生效）

```bash
curl -L https://raw.githubusercontent.com/Echoxiawan/db_skill/main/SKILL.md \
  -o .windsurfrules
```

---

### Cline（VS Code 扩展）

**全局规则**（所有项目生效）

```bash
mkdir -p ~/Documents/Cline/Rules
curl -L https://raw.githubusercontent.com/Echoxiawan/db_skill/main/SKILL.md \
  -o ~/Documents/Cline/Rules/db-inspector.md
```

**项目级规则**（仅当前项目生效）

```bash
curl -L https://raw.githubusercontent.com/Echoxiawan/db_skill/main/SKILL.md \
  -o .clinerules
```

安装后在 Cline 界面的 Rules 图标处确认规则已加载。

---

### Gemini CLI

Gemini CLI 有原生 Skills 系统，直接 clone 到技能目录：

**全局**（推荐，所有项目生效）：`~/.gemini/skills/db-inspector/`

```bash
git clone https://github.com/Echoxiawan/db_skill.git ~/.gemini/skills/db-inspector
```

**项目级**（仅当前项目生效）：`.gemini/skills/db-inspector/`

```bash
mkdir -p .gemini/skills
git clone https://github.com/Echoxiawan/db_skill.git .gemini/skills/db-inspector
```

触发方式：对话中输入 `/db-inspector`，或直接说「看表结构 / 连数据库」

---

### OpenAI Codex CLI

Codex CLI 有原生 Skills 系统，每个 Skill 是一个包含 `SKILL.md` 的文件夹：

**全局**（推荐，所有项目生效）：`~/.codex/skills/db-inspector/`

```bash
git clone https://github.com/Echoxiawan/db_skill.git ~/.codex/skills/db-inspector
```

**项目级**（仅当前项目生效）：`.codex/skills/db-inspector/`

```bash
mkdir -p .codex/skills
git clone https://github.com/Echoxiawan/db_skill.git .codex/skills/db-inspector
```

触发方式：对话中输入 `/db-inspector`，或直接说「看表结构 / 连数据库」

---

### Aider

Aider 通过 `--read` 参数加载约定文件，推荐写入项目配置：

```bash
# 下载到项目根目录
curl -L https://raw.githubusercontent.com/Echoxiawan/db_skill/main/SKILL.md \
  -o CONVENTIONS.md

# 写入 .aider.conf.yml 自动加载（无则新建）
echo "read: [CONVENTIONS.md]" >> .aider.conf.yml
```

或每次启动时手动指定：

```bash
aider --read CONVENTIONS.md
```

---

## 方式二：从本地仓库安装

适用于已将本仓库 clone 到本地的情况，在**本仓库根目录**执行。

### Claude Code
```bash
cp -r . ~/.claude/skills/db-inspector
```

### Kiro
```bash
cp -r . ~/.kiro/skills/db-inspector
```

### Cursor（项目级）
```bash
mkdir -p .cursor/rules
cp SKILL.md .cursor/rules/db-inspector.mdc
```

### Cursor（全局）
```bash
mkdir -p ~/.cursor/rules
cp SKILL.md ~/.cursor/rules/db-inspector.mdc
```

### Windsurf（全局）
```bash
cat SKILL.md >> ~/.codeium/windsurf/memories/global_rules.md
```

### Windsurf（项目级）
```bash
cp SKILL.md .windsurfrules
```

### Cline（全局）
```bash
mkdir -p ~/Documents/Cline/Rules
cp SKILL.md ~/Documents/Cline/Rules/db-inspector.md
```

### Cline（项目级）
```bash
cp SKILL.md .clinerules
```

### Gemini CLI（全局）
```bash
cp -r . ~/.gemini/skills/db-inspector
```

### Gemini CLI（项目级）
```bash
mkdir -p .gemini/skills
cp -r . .gemini/skills/db-inspector
```

### OpenAI Codex CLI（全局）
```bash
cp -r . ~/.codex/skills/db-inspector
```

### OpenAI Codex CLI（项目级）
```bash
mkdir -p .codex/skills
cp -r . .codex/skills/db-inspector
```

### Aider
```bash
cp SKILL.md CONVENTIONS.md
echo "read: [CONVENTIONS.md]" >> .aider.conf.yml
```

---

## Python 依赖安装

辅助脚本需要 Python 3.10+。按数据库类型按需安装即可（克隆 skill 后立即执行，避免使用时缺库）。

**用 `requirements.txt` 一键安装**（含全部驱动 + MCP 模式依赖）：

```bash
# 进入 skill 目录后执行（路径按你的安装位置调整）
pip install -r scripts/requirements.txt
```

或按需手动安装：

```bash
# 数据库驱动（按实际选择，Skill 模式只需装用到的那个）
pip install mysql-connector-python   # MySQL
pip install oracledb                 # Oracle（thin 模式，无需 Oracle Client）
```

> 仅在使用 **MCP 模式** 时还需以下两项；纯 Skill 模式可跳过：
> ```bash
> pip install mcp           # MCP 服务框架
> pip install cryptography  # HTTPS 自动生成自签证书
> ```

---

## MCP 模式（可选）

除 Skill 模式外，本仓库还可作为 MCP 服务启动，供 Claude Desktop / IDE 等客户端调用。

```bash
# 默认 streamable-http，监听 127.0.0.1:8765，端点 /mcp
python3 scripts/mcp_server.py
```

客户端配置（以 Claude Code 为例）：

```bash
claude mcp add --transport http --scope user db-inspector http://127.0.0.1:8765/mcp
```

完整的 MCP 启动参数、HTTPS、Docker 部署方式见 [README.md](README.md)。

---

## 安装验证

```bash
# Claude Code
ls ~/.claude/skills/db-inspector/SKILL.md

# Kiro
ls ~/.kiro/skills/db-inspector/SKILL.md

# Gemini CLI
ls ~/.gemini/skills/db-inspector/SKILL.md

# Codex CLI
ls ~/.codex/skills/db-inspector/SKILL.md
```

安装完成后，在 Agent 对话中输入 `/db-inspector` 或「看下某库的表结构」，Agent 应提示输入连接信息或列出已保存连接。

---

## 卸载

### Claude Code
```bash
rm -rf ~/.claude/skills/db-inspector
```

### Kiro
```bash
rm -rf ~/.kiro/skills/db-inspector
```

### Cursor（全局）
```bash
rm ~/.cursor/rules/db-inspector.mdc
```

### Cursor（项目级）
```bash
rm .cursor/rules/db-inspector.mdc
```

### Windsurf（项目级）
```bash
rm .windsurfrules
```

### Cline（全局）
```bash
rm ~/Documents/Cline/Rules/db-inspector.md
```

### Cline（项目级）
```bash
rm .clinerules
```

### Gemini CLI（全局）
```bash
rm -rf ~/.gemini/skills/db-inspector
```

### Gemini CLI（项目级）
```bash
rm -rf .gemini/skills/db-inspector
```

### OpenAI Codex CLI（全局）
```bash
rm -rf ~/.codex/skills/db-inspector
```

### OpenAI Codex CLI（项目级）
```bash
rm -rf .codex/skills/db-inspector
```

> 卸载 skill 不会删除已保存的连接信息（`~/.db_skill/connections.json`）。如需一并清除：
> ```bash
> rm -rf ~/.db_skill
> ```

---

## 常见问题

**Q：`scripts/` 目录下的脚本找不到？**

确保完整 clone 了仓库，而不只是下载了 `SKILL.md`：

```bash
ls ~/.claude/skills/db-inspector/scripts/
# 应包含：db_tool.py connections.py mcp_server.py requirements.txt
```

Cursor / Windsurf / Cline / Aider 的 Rules 模式只加载 SKILL.md 文本，不含脚本。需要跑 CLI 时改用完整克隆方式。

**Q：连接数据库报缺少驱动？**

按数据库类型安装对应驱动：

```bash
pip install mysql-connector-python   # MySQL
pip install oracledb                 # Oracle
```

**Q：连接信息存在哪里？**

存于 `~/.db_skill/connections.json`（文件权限 600，仅本人可读写），连库成功后自动保存。Skill 模式与本地 MCP 模式共用这份存储；Docker 部署的 MCP 服务则存于容器挂载卷，相互隔离。
