#!/usr/bin/env python3
"""
db-inspector 的 MCP 服务封装。

把 skill 的能力（连 MySQL/Oracle、看表结构、读数据、只读查询、连接管理）
暴露为 MCP 工具，供任意 MCP 客户端（Claude Desktop / IDE 等）调用。

**与 skill 模式共享同一套实现与存储**：
- 复用 db_tool.py 的底层函数（resolve_config / connect / table_schema ...），不重写逻辑。
- 连接信息仍存 ~/.db_skill/connections.json，两种模式互通——skill 存的连接 MCP 能用，反之亦然。

启动（默认 streamable-http 传输，MCP 官方推荐的 HTTP 传输，对反代/负载均衡更友好）::

    python3 scripts/mcp_server.py                      # streamable-http，默认 127.0.0.1:8765
    python3 scripts/mcp_server.py --host 0.0.0.0 --port 9000
    python3 scripts/mcp_server.py --transport sse      # 旧版 SSE（客户端不支持 streamable-http 时）
    python3 scripts/mcp_server.py --transport stdio    # stdio（部分客户端只支持这个）

也可用环境变量配置：DB_MCP_HOST / DB_MCP_PORT / DB_MCP_TRANSPORT。
端点：streamable-http 为 http://<host>:<port>/mcp ，sse 为 http://<host>:<port>/sse 。

依赖：pip install mcp，外加按需的 mysql-connector-python / oracledb。
"""
import argparse
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db_tool  # noqa: E402  复用 skill 的全部底层逻辑
import connections as store  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP(
    "db-inspector",
    host=os.environ.get("DB_MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("DB_MCP_PORT", "8765")),
)


def _args(**kw) -> SimpleNamespace:
    """构造 db_tool.resolve_config / maybe_save 所需的 args 对象。"""
    base = dict(conn=None, type=None, host=None, port=None, user=None,
                password=None, database=None, save_as=None)
    base.update({k: v for k, v in kw.items() if v is not None})
    return SimpleNamespace(**base)


def _connect_args(conn=None, type=None, host=None, port=None, user=None,
                  password=None, database=None, save_as=None):
    return _args(conn=conn, type=type, host=host, port=port, user=user,
                 password=password, database=database, save_as=save_as)


def _with_conn(args, work):
    """解析配置→连接→执行 work(conn,cfg)→连库成功自动保存→关闭。
    统一异常处理，错误以 dict 返回而非抛出（避免拖垮 MCP 服务）。"""
    try:
        cfg = db_tool.resolve_config(args)
    except SystemExit as e:
        return {"error": str(e)}
    conn = None
    try:
        conn = db_tool.connect(cfg)
        result = work(conn, cfg)
        saved = db_tool.maybe_save(cfg, args)
        if isinstance(result, dict) and saved:
            result.setdefault("saved_as", saved["name"])
        return result
    except SystemExit as e:
        return {"error": str(e)}
    except Exception as e:  # noqa: BLE001  连接/SQL 错误统一回传
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# 连接管理（不连库）
# --------------------------------------------------------------------------- #
@mcp.tool()
def list_connections() -> list:
    """列出所有已保存的数据库连接（密码脱敏）。"""
    return store.list_masked()


@mcp.tool()
def find_connections(keyword: str) -> list:
    """按关键字模糊查找已保存连接（匹配 name/host/database/user/type），密码脱敏。"""
    return [store.masked(m) for m in store.find(keyword)]


@mcp.tool()
def save_connection(name: str, type: str, host: str, user: str, password: str,
                    port: str = "", database: str = "") -> dict:
    """仅保存一条连接信息（不实际连库）。type 取 mysql 或 oracle。"""
    cfg = {"name": name, "type": type, "host": host, "user": user,
           "password": password}
    if port:
        cfg["port"] = port
    if database:
        cfg["database"] = database
    if not cfg.get("port"):
        cfg["port"] = db_tool.DEFAULT_PORTS.get(type, "")
    saved = store.upsert(cfg)
    return store.masked(saved)


@mcp.tool()
def rename_connection(old: str, new: str) -> dict:
    """重命名一条已保存连接。"""
    return store.rename(old, new)


# --------------------------------------------------------------------------- #
# 连库操作（conn=已存连接名，或内联 type/host/port/user/password/database）
# --------------------------------------------------------------------------- #
@mcp.tool()
def test_connection(conn: str = "", type: str = "", host: str = "",
                    port: str = "", user: str = "", password: str = "",
                    database: str = "", save_as: str = "") -> dict:
    """测试数据库连接是否可用。可用 conn 指定已存连接，或内联连接参数。
    成功连上会按 host+port+user 自动保存/覆盖。"""
    args = _connect_args(conn or None, type or None, host or None, port or None,
                         user or None, password or None, database or None,
                         save_as or None)
    return _with_conn(args, lambda c, cfg: {
        "ok": True, "type": cfg["type"],
        "host": cfg.get("host"), "port": cfg.get("port"),
        "database": cfg.get("database"),
    })


@mcp.tool()
def list_databases(conn: str = "", type: str = "", host: str = "",
                   port: str = "", user: str = "", password: str = "",
                   database: str = "", save_as: str = "") -> dict:
    """列出可用的库 / schema（已过滤系统库）。用户没指定库名时用它先探查。"""
    args = _connect_args(conn or None, type or None, host or None, port or None,
                         user or None, password or None, database or None,
                         save_as or None)
    return _with_conn(args, lambda c, cfg: {
        "type": cfg["type"], "databases": db_tool.list_databases(c, cfg),
    })


@mcp.tool()
def list_tables(conn: str = "", type: str = "", host: str = "",
                port: str = "", user: str = "", password: str = "",
                database: str = "", save_as: str = "") -> dict:
    """列出库中所有表名。"""
    args = _connect_args(conn or None, type or None, host or None, port or None,
                         user or None, password or None, database or None,
                         save_as or None)
    return _with_conn(args, lambda c, cfg: {
        "database": cfg.get("database"),
        "tables": db_tool.list_tables(c, cfg),
    })


@mcp.tool()
def get_table_schema(table: str = "", conn: str = "", type: str = "",
                     host: str = "", port: str = "", user: str = "",
                     password: str = "", database: str = "", sample: int = 3,
                     save_as: str = "") -> dict:
    """获取表结构（列 / 索引 / 外键，外加 sample 行示例数据；sample=0 只看结构）。
    table 留空则返回库中全部表的结构。"""
    args = _connect_args(conn or None, type or None, host or None, port or None,
                         user or None, password or None, database or None,
                         save_as or None)

    def work(c, cfg):
        targets = [table] if table else db_tool.list_tables(c, cfg)
        return {"type": cfg["type"], "database": cfg.get("database"),
                "tables": {t: db_tool.table_schema(c, cfg, t, sample=sample)
                           for t in targets}}
    return _with_conn(args, work)


@mcp.tool()
def read_table_data(table: str, conn: str = "", type: str = "", host: str = "",
                    port: str = "", user: str = "", password: str = "",
                    database: str = "", limit: int = 20, offset: int = 0,
                    save_as: str = "") -> dict:
    """读取某张表的数据（分页：limit 行数，offset 偏移）。"""
    args = _connect_args(conn or None, type or None, host or None, port or None,
                         user or None, password or None, database or None,
                         save_as or None)
    return _with_conn(args, lambda c, cfg: {
        "table": table,
        **db_tool.read_data(c, cfg, table, limit=limit, offset=offset),
    })


@mcp.tool()
def run_query(sql: str, conn: str = "", type: str = "", host: str = "",
              port: str = "", user: str = "", password: str = "",
              database: str = "", limit: int = 200, save_as: str = "") -> dict:
    """执行只读查询（仅允许 SELECT / WITH 开头，禁止多语句）。limit 限制返回行数。"""
    args = _connect_args(conn or None, type or None, host or None, port or None,
                         user or None, password or None, database or None,
                         save_as or None)
    return _with_conn(args, lambda c, cfg: db_tool.run_query(c, cfg, sql, limit=limit))


def ensure_self_signed_cert() -> tuple:
    """确保自签证书存在并返回 (certfile, keyfile) 路径。
    存到 DB_SKILL_HOME/certs/（docker 下即挂载的 /data，重启复用、不重复生成）。
    已存在则直接复用；用纯 Python 的 cryptography 生成，不依赖 openssl 命令。"""
    cert_dir = store.STORE_DIR / "certs"
    cert_dir.mkdir(parents=True, exist_ok=True)
    certfile = cert_dir / "cert.pem"
    keyfile = cert_dir / "key.pem"
    if certfile.exists() and keyfile.exists():
        return str(certfile), str(keyfile)

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        import ipaddress
    except ImportError:
        raise SystemExit("[ERROR] HTTPS 自动证书需要 cryptography: pip install cryptography")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(san, critical=False)
        .sign(key, hashes.SHA256())
    )
    keyfile.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    try:
        os.chmod(keyfile, 0o600)
    except OSError:
        pass
    print(f"[db-inspector] 已自动生成自签证书: {cert_dir}", file=sys.stderr)
    return str(certfile), str(keyfile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="db-inspector MCP 服务（默认 streamable-http 传输）")
    parser.add_argument("--transport", choices=["streamable-http", "sse", "stdio"],
                        default=os.environ.get("DB_MCP_TRANSPORT", "streamable-http"),
                        help="传输方式，默认 streamable-http")
    parser.add_argument("--host", help="HTTP 监听地址，覆盖默认/环境变量")
    parser.add_argument("--port", type=int, help="HTTP 监听端口，覆盖默认/环境变量")
    parser.add_argument("--certfile", default=os.environ.get("DB_MCP_CERTFILE"),
                        help="TLS 证书文件路径，提供后以 HTTPS 启动（仅 http 类传输）")
    parser.add_argument("--keyfile", default=os.environ.get("DB_MCP_KEYFILE"),
                        help="TLS 私钥文件路径，配合 --certfile")
    parser.add_argument("--tls", action="store_true",
                        default=os.environ.get("DB_MCP_TLS", "").lower() in ("1", "true", "yes"),
                        help="以 HTTPS 启动；未提供 --certfile/--keyfile 时自动生成自签证书并复用")
    cli = parser.parse_args()

    if cli.host:
        mcp.settings.host = cli.host
    if cli.port:
        mcp.settings.port = cli.port

    _paths = {"streamable-http": "/mcp", "sse": "/sse"}
    # 显式给了证书 → 用它；只开 --tls 没给证书 → 自动生成自签证书
    if cli.certfile and cli.keyfile:
        certfile, keyfile = cli.certfile, cli.keyfile
        use_tls = True
    elif cli.tls:
        certfile, keyfile = ensure_self_signed_cert()
        use_tls = True
    else:
        certfile = keyfile = None
        use_tls = False

    if cli.transport == "stdio":
        if use_tls:
            print("[db-inspector] stdio 传输不支持 TLS，忽略证书", file=sys.stderr)
        mcp.run(transport="stdio")
    elif use_tls:
        # FastMCP.run() 不暴露 SSL，故取出 ASGI app 用 uvicorn 直接加载证书跑 HTTPS
        import uvicorn
        app = (mcp.streamable_http_app() if cli.transport == "streamable-http"
               else mcp.sse_app())
        print(f"[db-inspector] {cli.transport} (HTTPS) 服务启动: "
              f"https://{mcp.settings.host}:{mcp.settings.port}{_paths[cli.transport]}",
              file=sys.stderr)
        uvicorn.run(app, host=mcp.settings.host, port=mcp.settings.port,
                    ssl_certfile=certfile, ssl_keyfile=keyfile,
                    log_level=mcp.settings.log_level.lower())
    else:
        print(f"[db-inspector] {cli.transport} 服务启动: "
              f"http://{mcp.settings.host}:{mcp.settings.port}{_paths[cli.transport]}",
              file=sys.stderr)
        mcp.run(transport=cli.transport)
