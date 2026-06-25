#!/usr/bin/env python3
"""
连接信息存储模块。

将数据库连接信息保存到 ~/.db_skill/connections.json，文件权限设为 600（仅本人可读写）。
密码以明文存储——仅适合本地开发环境，不要在共享/生产机器上使用。

记录结构（每个连接一条）::

    {
      "name": "local-mysql",
      "type": "mysql",            # mysql | oracle
      "host": "127.0.0.1",
      "port": "3306",
      "user": "root",
      "password": "secret",
      "database": "mydb",          # mysql: schema 名 / oracle: service name
      "created_at": "2026-06-25T11:00:00",
      "last_used": "2026-06-25T11:30:00"
    }
"""
import json
import os
import stat
from datetime import datetime
from pathlib import Path

STORE_DIR = Path(os.environ.get("DB_SKILL_HOME", str(Path.home() / ".db_skill")))
STORE_FILE = STORE_DIR / "connections.json"

# 一条连接记录的合法字段
FIELDS = ("name", "type", "host", "port", "user", "password", "database",
          "created_at", "last_used")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_store() -> None:
    """确保存储目录与文件存在，且权限收紧为仅本人可访问。"""
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(STORE_DIR, stat.S_IRWXU)  # 700
    except OSError:
        pass
    if not STORE_FILE.exists():
        STORE_FILE.write_text("[]", encoding="utf-8")
    try:
        os.chmod(STORE_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 600
    except OSError:
        pass


def load_all() -> list:
    """读取全部连接记录；文件不存在或损坏时返回空列表。"""
    _ensure_store()
    try:
        data = json.loads(STORE_FILE.read_text(encoding="utf-8") or "[]")
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_all(records: list) -> None:
    _ensure_store()
    STORE_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(STORE_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 600
    except OSError:
        pass


def get(name: str) -> dict | None:
    """按名称精确获取一条连接。"""
    for rec in load_all():
        if rec.get("name") == name:
            return rec
    return None


# 判定「同一个连接」的特征字段：连接地址(host:port) + 登录用户名。
# 不含 type（由 host:port 唯一决定）与 database（库名只是连上后的默认选择，可临时切换）。
IDENTITY_FIELDS = ("host", "port", "user")


def _identity(rec: dict) -> tuple:
    return tuple(str(rec.get(f, "") or "") for f in IDENTITY_FIELDS)


def find_by_identity(conn: dict) -> dict | None:
    """按连接特征（type/host/port/user/database）查找已存记录。
    用于在用户未指定名称时判断「这个连接是否已保存过」，从而覆盖而非新建。"""
    target = _identity(conn)
    for rec in load_all():
        if _identity(rec) == target:
            return rec
    return None


def upsert(conn: dict) -> dict:
    """新增或更新一条连接（按 name 唯一）。返回保存后的记录。"""
    name = conn.get("name")
    if not name:
        raise ValueError("连接必须有 name")

    records = load_all()
    clean = {k: conn[k] for k in FIELDS if k in conn and conn[k] is not None}

    for i, rec in enumerate(records):
        if rec.get("name") == name:
            clean.setdefault("created_at", rec.get("created_at", _now()))
            clean["last_used"] = _now()
            merged = {**rec, **clean}
            records[i] = merged
            _save_all(records)
            return merged

    clean.setdefault("created_at", _now())
    clean.setdefault("last_used", _now())
    records.append(clean)
    _save_all(records)
    return clean


def touch(name: str) -> None:
    """更新某连接的 last_used 时间戳（成功连接后调用）。"""
    records = load_all()
    for rec in records:
        if rec.get("name") == name:
            rec["last_used"] = _now()
            _save_all(records)
            return


def delete(name: str) -> bool:
    """删除一条连接。返回是否真的删除了。"""
    records = load_all()
    remaining = [r for r in records if r.get("name") != name]
    if len(remaining) == len(records):
        return False
    _save_all(remaining)
    return True


def rename(old: str, new: str) -> dict:
    """把连接 old 改名为 new。返回 {ok, error}。"""
    if not new:
        return {"ok": False, "error": "新名称不能为空"}
    records = load_all()
    if not any(r.get("name") == old for r in records):
        return {"ok": False, "error": f"未找到 '{old}'"}
    if old != new and any(r.get("name") == new for r in records):
        return {"ok": False, "error": f"名称 '{new}' 已被占用"}
    for rec in records:
        if rec.get("name") == old:
            rec["name"] = new
            break
    _save_all(records)
    return {"ok": True}


def find(keyword: str) -> list:
    """模糊匹配：在 name/host/database/user/type 中包含 keyword 的连接，
    按 last_used 倒序返回（最近用过的排前面）。"""
    kw = (keyword or "").lower()
    matched = []
    for rec in load_all():
        haystack = " ".join(str(rec.get(f, "")) for f in
                            ("name", "host", "database", "user", "type")).lower()
        if kw in haystack:
            matched.append(rec)
    matched.sort(key=lambda r: r.get("last_used", ""), reverse=True)
    return matched


def masked(rec: dict) -> dict:
    """返回脱敏后的记录（密码打码），用于安全地展示给用户。"""
    out = dict(rec)
    pwd = out.get("password")
    if pwd:
        out["password"] = (pwd[:1] + "***") if len(pwd) > 1 else "***"
    return out


def list_masked() -> list:
    """所有连接的脱敏列表，按 last_used 倒序。"""
    recs = load_all()
    recs.sort(key=lambda r: r.get("last_used", ""), reverse=True)
    return [masked(r) for r in recs]
