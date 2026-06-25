#!/usr/bin/env python3
"""
数据库工具：连接 DB，获取表结构、读取表数据。支持 MySQL 与 Oracle。

连接信息可保存到 ~/.db_skill/connections.json（密码明文，文件权限 600），
下次用 `--conn <名称>` 或 `find` 子命令智能提取，免去重复输入。

子命令::

    list                          列出所有已保存连接（密码脱敏）
    find <关键字>                  模糊查找已保存连接
    save                          仅保存连接信息（不连库），需 --name + 连接参数
    delete --name <名称>          删除一条连接
    test                          测试连接是否可用
    tables                        列出库中所有表名
    schema [--table T ...]        获取表结构（列/索引/外键/3 行示例），默认全部表
    data --table T [--limit N]    读取某表数据
    query --sql "SELECT ..."      执行只读 SELECT 查询

连接参数（两种方式，可混用：先按 --conn 取出已存配置，再用内联参数覆盖）::

    --conn <名称>                 使用已保存连接
    --type {mysql,oracle} --host --port --user --password --database
    --save-as <名称>              连库成功后把本次内联参数保存为该名称

示例::

    db_tool.py save --name local --type mysql --host 127.0.0.1 \\
        --user root --password 123456 --database shop
    db_tool.py tables --conn local
    db_tool.py schema --conn local --table users --table orders
    db_tool.py data --conn local --table users --limit 20
    db_tool.py query --conn local --sql "SELECT id,name FROM users WHERE id<10"
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import connections as store  # noqa: E402

DEFAULT_PORTS = {"mysql": "3306", "oracle": "1521"}


# --------------------------------------------------------------------------- #
# 连接配置解析
# --------------------------------------------------------------------------- #
def resolve_config(args) -> dict:
    """综合 --conn（已存配置）与内联参数，得到最终连接 dict。
    内联参数优先级高于已存配置（用于临时覆盖）。"""
    cfg = {}
    if getattr(args, "conn", None):
        saved = store.get(args.conn)
        if not saved:
            matches = store.find(args.conn)
            if len(matches) == 1:
                saved = matches[0]
            elif len(matches) > 1:
                names = ", ".join(m["name"] for m in matches)
                raise SystemExit(f"[ERROR] '{args.conn}' 匹配到多个连接: {names}，请用精确名称")
            else:
                raise SystemExit(f"[ERROR] 未找到名为 '{args.conn}' 的已保存连接")
        cfg.update(saved)

    # 内联参数覆盖
    for f in ("type", "host", "port", "user", "password", "database"):
        v = getattr(args, f, None)
        if v is not None:
            cfg[f] = v

    if getattr(args, "save_as", None):
        cfg["name"] = args.save_as

    # 补默认端口
    if cfg.get("type") and not cfg.get("port"):
        cfg["port"] = DEFAULT_PORTS.get(cfg["type"])

    if not cfg.get("type"):
        raise SystemExit("[ERROR] 缺少数据库类型，请用 --type 或 --conn 指定")
    if cfg["type"] not in ("mysql", "oracle"):
        raise SystemExit(f"[ERROR] 仅支持 mysql / oracle，收到: {cfg['type']}")
    return cfg


def _auto_name(cfg: dict) -> str:
    """为新连接生成简短易记的默认名：优先用登录用户名。
    用户名通常含环境+库信息（如 ksafeature_hs_member），既能区分不同环境下的
    同名库，又与判重身份(host+port+user)中的 user 一致——同身份必得同名。
    无用户名时回退到 database / host。冲突则追加 -2/-3。"""
    import re
    raw = cfg.get("user") or cfg.get("database") or cfg.get("host") or "db"
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(raw)).strip("_-") or "db"
    existing = {r.get("name") for r in store.load_all()}
    if base not in existing:
        return base
    i = 2
    while f"{base}-{i}" in existing:
        i += 1
    return f"{base}-{i}"


def maybe_save(cfg: dict, args) -> dict | None:
    """连库成功后自动保存连接信息，返回保存后的记录（未保存则 None）。
    规则：
    - 用 --conn 复用已存连接：按名称更新（同时刷新 last_used）。
    - 提供了内联连接信息：按特征(type/host/port/user/database)查找，
      已存在则覆盖那条（保留原名称与创建时间），不存在则新建
      （名称取 --save-as，否则自动生成）。"""
    # 没有可连接的最小信息就不存
    if not cfg.get("type") or not cfg.get("host"):
        return None

    # 用了已保存连接：按名称更新整条
    if getattr(args, "conn", None) and cfg.get("name"):
        return store.upsert(cfg)

    # 内联连接：同特征已存在 → 覆盖（沿用原名称）
    existing = store.find_by_identity(cfg)
    if existing:
        cfg["name"] = existing["name"]
        return store.upsert(cfg)

    # 全新连接 → 命名后保存
    cfg["name"] = getattr(args, "save_as", None) or cfg.get("name") or _auto_name(cfg)
    return store.upsert(cfg)


# --------------------------------------------------------------------------- #
# 数据库连接（按类型分派）
# --------------------------------------------------------------------------- #
def connect(cfg: dict):
    if cfg["type"] == "mysql":
        try:
            import mysql.connector as mc
        except ImportError:
            raise SystemExit("[ERROR] 缺少依赖: pip install mysql-connector-python")
        return mc.connect(
            host=cfg.get("host", "127.0.0.1"),
            port=int(cfg.get("port", 3306)),
            user=cfg.get("user", "root"),
            password=cfg.get("password", ""),
            database=cfg.get("database", ""),
        )
    if cfg["type"] == "oracle":
        try:
            import oracledb
        except ImportError:
            raise SystemExit("[ERROR] 缺少依赖: pip install oracledb")
        dsn = f"{cfg.get('host','127.0.0.1')}:{cfg.get('port','1521')}/{cfg.get('database','')}"
        return oracledb.connect(
            user=cfg.get("user", ""), password=cfg.get("password", ""), dsn=dsn
        )
    raise SystemExit(f"[ERROR] 不支持的类型: {cfg['type']}")


def _quote_ident(cfg: dict, name: str) -> str:
    """按数据库类型安全地引用标识符（表名/列名），防止注入。
    仅允许字母数字下划线和点，否则拒绝。"""
    import re
    if not re.fullmatch(r"[A-Za-z0-9_.$]+", name or ""):
        raise SystemExit(f"[ERROR] 非法标识符: {name!r}")
    if cfg["type"] == "mysql":
        return ".".join(f"`{p}`" for p in name.split("."))
    return ".".join(f'"{p}"' for p in name.split("."))  # oracle


# --------------------------------------------------------------------------- #
# 取表名
# --------------------------------------------------------------------------- #
def list_databases(conn, cfg: dict) -> list:
    """列出可用的库 / schema，过滤掉系统库，便于在用户没指定库名时智能选择。"""
    cur = conn.cursor()
    if cfg["type"] == "mysql":
        cur.execute("SHOW DATABASES")
        sys_db = {"information_schema", "mysql", "performance_schema", "sys"}
        return [r[0] for r in cur.fetchall() if r[0].lower() not in sys_db]
    # oracle: 以 owner（schema）作为「库」的类比
    cur.execute("SELECT DISTINCT owner FROM all_tables ORDER BY owner")
    sys_owner = {"SYS", "SYSTEM", "OUTLN", "XDB", "CTXSYS", "MDSYS", "DBSNMP",
                 "APPQOSSYS", "GSMADMIN_INTERNAL", "AUDSYS", "DVSYS", "LBACSYS",
                 "OJVMSYS", "ORDSYS", "ORDDATA", "WMSYS", "OLAPSYS"}
    return [r[0] for r in cur.fetchall() if r[0] not in sys_owner]


def list_tables(conn, cfg: dict) -> list:
    cur = conn.cursor()
    if cfg["type"] == "mysql":
        cur.execute("SHOW TABLES")
        return [r[0] for r in cur.fetchall()]
    # oracle: 当前 schema（user）下的表
    owner = (cfg.get("user", "") or "").upper()
    cur.execute("SELECT table_name FROM all_tables WHERE owner = :o ORDER BY table_name", o=owner)
    return [r[0] for r in cur.fetchall()]


# --------------------------------------------------------------------------- #
# 取表结构
# --------------------------------------------------------------------------- #
def table_schema(conn, cfg: dict, table: str, sample: int = 3) -> dict:
    cur = conn.cursor()
    if cfg["type"] == "mysql":
        cur.execute(f"DESCRIBE {_quote_ident(cfg, table)}")
        columns = [{"field": r[0], "type": r[1], "null": r[2], "key": r[3],
                    "default": r[4], "extra": r[5]} for r in cur.fetchall()]
        cur.execute(f"SHOW INDEX FROM {_quote_ident(cfg, table)}")
        indexes = [{"name": r[2], "column": r[4], "unique": r[1] == 0} for r in cur.fetchall()]
        cur.execute("""
            SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL
        """, (cfg.get("database", ""), table))
        fks = [{"column": r[0], "ref_table": r[1], "ref_column": r[2]} for r in cur.fetchall()]
    else:  # oracle
        owner = (cfg.get("user", "") or "").upper()
        cur.execute("""
            SELECT column_name, data_type, nullable, data_default, data_length
            FROM all_tab_columns WHERE owner=:o AND table_name=:t ORDER BY column_id
        """, o=owner, t=table)
        columns = [{"field": r[0], "type": r[1], "null": "YES" if r[2] == "Y" else "NO",
                    "default": r[3], "length": r[4]} for r in cur.fetchall()]
        cur.execute("""
            SELECT i.index_name, c.column_name, i.uniqueness
            FROM all_indexes i JOIN all_ind_columns c
              ON i.index_name=c.index_name AND i.owner=c.index_owner
            WHERE i.owner=:o AND i.table_name=:t ORDER BY i.index_name, c.column_position
        """, o=owner, t=table)
        indexes = [{"name": r[0], "column": r[1], "unique": r[2] == "UNIQUE"} for r in cur.fetchall()]
        cur.execute("""
            SELECT a.column_name, c_pk.table_name, c_pk.constraint_name
            FROM all_cons_columns a
            JOIN all_constraints c ON a.owner=c.owner AND a.constraint_name=c.constraint_name
            JOIN all_constraints c_pk ON c.r_owner=c_pk.owner AND c.r_constraint_name=c_pk.constraint_name
            WHERE c.constraint_type='R' AND a.owner=:o AND a.table_name=:t
        """, o=owner, t=table)
        fks = [{"column": r[0], "ref_table": r[1], "ref_column": r[2]} for r in cur.fetchall()]

    result = {"columns": columns, "indexes": indexes, "foreign_keys": fks}
    if sample > 0:
        result["sample_rows"] = read_data(conn, cfg, table, sample)["rows"]
    return result


# --------------------------------------------------------------------------- #
# 读表数据
# --------------------------------------------------------------------------- #
def read_data(conn, cfg: dict, table: str, limit: int = 20, offset: int = 0) -> dict:
    cur = conn.cursor()
    ident = _quote_ident(cfg, table)
    if cfg["type"] == "mysql":
        cur.execute(f"SELECT * FROM {ident} LIMIT %s OFFSET %s", (int(limit), int(offset)))
    else:  # oracle 12c+
        cur.execute(
            f"SELECT * FROM {ident} OFFSET :o ROWS FETCH NEXT :l ROWS ONLY",
            o=int(offset), l=int(limit),
        )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    return {"columns": cols, "rows": rows, "count": len(rows)}


# --------------------------------------------------------------------------- #
# 只读查询
# --------------------------------------------------------------------------- #
def run_query(conn, cfg: dict, sql: str, limit: int = 200) -> dict:
    stripped = sql.strip().rstrip(";").strip()
    low = stripped.lower()
    if not (low.startswith("select") or low.startswith("with")):
        raise SystemExit("[ERROR] 仅允许只读查询（SELECT / WITH 开头）")
    # 粗略拦截多语句
    if ";" in stripped:
        raise SystemExit("[ERROR] 不允许多条语句")
    cur = conn.cursor()
    cur.execute(stripped)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = [dict(zip(cols, row)) for row in cur.fetchall()[:limit]]
    return {"columns": cols, "rows": rows, "count": len(rows)}


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


# --------------------------------------------------------------------------- #
# 子命令处理
# --------------------------------------------------------------------------- #
def cmd_list(args):
    recs = store.list_masked()
    if not recs:
        print("（暂无已保存连接）")
        return
    emit(recs)


def cmd_find(args):
    matches = [store.masked(m) for m in store.find(args.keyword)]
    if not matches:
        print(f"（没有匹配 '{args.keyword}' 的连接）")
        return
    emit(matches)


def cmd_save(args):
    cfg = resolve_config(args)
    if not cfg.get("name"):
        cfg["name"] = args.name
    if not cfg.get("name"):
        raise SystemExit("[ERROR] save 需要 --name 指定连接名称")
    saved = store.upsert(cfg)
    print(f"已保存连接 '{saved['name']}'（{saved['type']} @ {saved.get('host')}:{saved.get('port')}）")


def cmd_delete(args):
    ok = store.delete(args.name)
    print(f"已删除 '{args.name}'" if ok else f"未找到 '{args.name}'")


def cmd_rename(args):
    r = store.rename(args.old, args.new)
    if r["ok"]:
        print(f"已重命名：'{args.old}' → '{args.new}'")
    else:
        raise SystemExit(f"[ERROR] {r['error']}")


def cmd_test(args):
    cfg = resolve_config(args)
    conn = connect(cfg)
    conn.close()
    saved = maybe_save(cfg, args)
    print(f"连接成功：{cfg['type']} @ {cfg.get('host')}:{cfg.get('port')}/{cfg.get('database')}")
    if saved:
        print(f"连接信息已保存为 '{saved['name']}'")


def cmd_databases(args):
    cfg = resolve_config(args)
    conn = connect(cfg)
    try:
        dbs = list_databases(conn, cfg)
        saved = maybe_save(cfg, args)
        emit({"type": cfg["type"], "saved_as": saved and saved["name"],
              "database_count": len(dbs), "databases": dbs})
    finally:
        conn.close()


def cmd_tables(args):
    cfg = resolve_config(args)
    conn = connect(cfg)
    try:
        tables = list_tables(conn, cfg)
        saved = maybe_save(cfg, args)
        emit({"database": cfg.get("database"), "saved_as": saved and saved["name"],
              "table_count": len(tables), "tables": tables})
    finally:
        conn.close()


def cmd_schema(args):
    cfg = resolve_config(args)
    conn = connect(cfg)
    try:
        targets = args.table or list_tables(conn, cfg)
        schema = {t: table_schema(conn, cfg, t, sample=args.sample) for t in targets}
        saved = maybe_save(cfg, args)
        emit({"type": cfg["type"], "database": cfg.get("database"),
              "saved_as": saved and saved["name"], "tables": schema})
    finally:
        conn.close()


def cmd_data(args):
    cfg = resolve_config(args)
    conn = connect(cfg)
    try:
        result = read_data(conn, cfg, args.table, limit=args.limit, offset=args.offset)
        saved = maybe_save(cfg, args)
        emit({"table": args.table, "saved_as": saved and saved["name"], **result})
    finally:
        conn.close()


def cmd_query(args):
    cfg = resolve_config(args)
    conn = connect(cfg)
    try:
        result = run_query(conn, cfg, args.sql, limit=args.limit)
        maybe_save(cfg, args)
        emit(result)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# 参数解析
# --------------------------------------------------------------------------- #
def add_conn_args(p):
    p.add_argument("--conn", help="使用已保存连接的名称")
    p.add_argument("--type", choices=["mysql", "oracle"], help="数据库类型")
    p.add_argument("--host")
    p.add_argument("--port")
    p.add_argument("--user")
    p.add_argument("--password")
    p.add_argument("--database", help="MySQL: schema 名 / Oracle: service name")
    p.add_argument("--save-as", dest="save_as", help="连库成功后保存为该名称")


def build_parser():
    parser = argparse.ArgumentParser(description="数据库结构与数据读取工具（MySQL / Oracle）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="列出所有已保存连接")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("find", help="模糊查找已保存连接")
    p.add_argument("keyword")
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("save", help="仅保存连接信息（不连库）")
    add_conn_args(p)
    p.add_argument("--name", help="连接名称")
    p.set_defaults(func=cmd_save)

    p = sub.add_parser("delete", help="删除一条连接")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("rename", help="重命名一条连接")
    p.add_argument("--old", required=True, help="原名称")
    p.add_argument("--new", required=True, help="新名称")
    p.set_defaults(func=cmd_rename)

    p = sub.add_parser("test", help="测试连接")
    add_conn_args(p)
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("databases", help="列出可用的库 / schema（已过滤系统库）")
    add_conn_args(p)
    p.set_defaults(func=cmd_databases)

    p = sub.add_parser("tables", help="列出所有表名")
    add_conn_args(p)
    p.set_defaults(func=cmd_tables)

    p = sub.add_parser("schema", help="获取表结构")
    add_conn_args(p)
    p.add_argument("--table", action="append", help="指定表（可多次），不指定则全部")
    p.add_argument("--sample", type=int, default=3, help="每表示例行数，0 表示不取")
    p.set_defaults(func=cmd_schema)

    p = sub.add_parser("data", help="读取表数据")
    add_conn_args(p)
    p.add_argument("--table", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(func=cmd_data)

    p = sub.add_parser("query", help="执行只读 SELECT 查询")
    add_conn_args(p)
    p.add_argument("--sql", required=True)
    p.add_argument("--limit", type=int, default=200, help="最多返回行数")
    p.set_defaults(func=cmd_query)

    return parser


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
