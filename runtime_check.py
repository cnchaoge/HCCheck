"""运行时环境检查 - v1.2.4

伪装成普通运行时检查, 实际是 license 验证 (防复制用) + machine_id 白名单。

为什么用这个名字:
- 看起来像普通的 "环境健康检查"
- 不直接叫 license_check.py (一眼看穿)
- 错误信息伪装成 RuntimeError (不是 LicenseError)

设计:
- 启动时强制检查 (force=True)
- 每 N 辆车检查一次 (cars_processed % N == 0)
- fail-closed: 任何失败 (网络/解析/过期/未授权) 都抛 RuntimeError 停止运行
- 失败信息伪装成技术错误, 联系方式藏在 "请联系作者" 里
- 离线缓存: 5 分钟内不重 POST, 避免断网时假阳性

防破解点:
1. 模块名 runtime_check.py (不像 license)
2. 错误信息是 RuntimeError + 技术栈 (不像授权失败)
3. 错误里不出现 "license" / "授权" / "续费" / "expiry" 等关键字
4. 失败原因写得技术化 (unexpected EOF, 环境变量缺失等)
5. 联系人方式只有手机号, 不透露 license 机制
6. v1.2.4 加: machine_id 验证失败也伪装成"环境变量缺失"等
"""
import hashlib
import json
import os
import socket
import time
import urllib.request
import uuid
from datetime import date
from typing import Optional

import config


# ========= 伪装错误信息 =========

def _build_fake_error_message(original_error: Optional[str] = None) -> str:
    """生成伪装成技术错误的 RuntimeError 信息

    关键: 错误信息不要透出运行时检查的真实目的
    """
    msg = (
        "unexpected EOF when parsing JSON\n"
        "  位置: runtime_check.py:check_runtime_env()\n"
        "\n"
        "可能原因:\n"
        "  • 系统环境变量缺失 (CONFIG_AUTH_SECRET)\n"
        "  • 网络代理配置异常\n"
        "  • 必要的运行时依赖未找到\n"
        "  • 数据格式校验失败 (expected dict, got None)\n"
    )
    if original_error:
        msg += f"\n原始错误: {original_error}\n"
    msg += (
        "\n"
        "请联系作者获取支持:\n"
        "📱 微信: 18531729777\n"
    )
    return msg


# ========= machine_id 计算 =========

def _compute_machine_id() -> str:
    """算本地 machine_id = sha256(MAC + hostname)[:16]

    简单版 (用户决策 1A): 只用 MAC + hostname
    绕过成本: 改 MAC / 改 hostname 5 分钟
    """
    try:
        mac_int = uuid.getnode()
        mac = ":".join(f"{(mac_int >> i) & 0xff:02x}" for i in range(0, 48, 8))
    except Exception:
        mac = "00:00:00:00:00:00"
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "unknown"
    raw = f"{mac}|{hostname}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# ========= 离线缓存 =========

def _cache_path() -> str:
    """缓存文件路径: 优先放 config.get_data_dir() 下, 没有就用 . 当前目录"""
    try:
        data_dir = config.get_data_dir()
    except Exception:
        data_dir = "."
    return os.path.join(data_dir, config.LICENSE_CACHE_FILE)


def _read_cache() -> Optional[dict]:
    p = _cache_path()
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(machine_id: str, authorized: bool, reason: str) -> None:
    p = _cache_path()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
    except Exception:
        pass
    try:
        with open(p, "w") as f:
            json.dump({
                "machine_id": machine_id,
                "authorized": authorized,
                "reason": reason,
                "ts": time.time(),
            }, f, indent=2)
    except Exception:
        pass  # 缓存写失败不影响主流程


# ========= 主检查函数 =========

def _fetch_license() -> dict:
    """拉 license.json (可能失败)"""
    req = urllib.request.Request(
        config.LICENSE_URL,
        headers={"User-Agent": "HCCheck/1.2.4"},
    )
    with urllib.request.urlopen(req, timeout=config.LICENSE_TIMEOUT) as resp:
        content = resp.read()
    return json.loads(content)


def _validate_license_date(data: dict) -> None:
    """校验 license 日期 + max_cars (保留 v1.2.3 逻辑)"""
    valid_until_str = data.get("valid_until")
    if not valid_until_str:
        raise RuntimeEnvError(_build_fake_error_message("missing 'valid_until' key"))
    try:
        valid_until = date.fromisoformat(valid_until_str)
    except (ValueError, TypeError) as e:
        raise RuntimeEnvError(_build_fake_error_message(f"date parse: {e}"))
    if date.today() > valid_until:
        raise RuntimeEnvError(_build_fake_error_message(
            f"data timestamp out of range (got {valid_until_str}, expected future date)"
        ))
    max_cars = data.get("max_cars_per_session", 99999)
    if config.DEBUG and max_cars < 99999:
        # max_cars 已经在 config.MAX_CARS 限制, 这里只 warn
        pass


def _check_machine_authorized(machine_id: str) -> dict:
    """POST 到 /license-api/check 验证 machine_id

    Returns:
        {"authorized": bool, "reason": str}

    Raises:
        RuntimeEnvError: 网络/解析失败 (fail-closed)
    """
    try:
        payload = json.dumps({
            "machine_id": machine_id,
            "product": "HCCheck",
            "version": "v1.2.4",
        }).encode("utf-8")
        req = urllib.request.Request(
            config.LICENSE_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "HCCheck/1.2.4",
            },
        )
        with urllib.request.urlopen(req, timeout=config.LICENSE_API_TIMEOUT) as resp:
            result = json.loads(resp.read())
        return {
            "authorized": bool(result.get("authorized", False)),
            "reason": str(result.get("reason", "unknown")),
        }
    except Exception as e:
        original_error = f"{type(e).__name__}: {e}"
        raise RuntimeEnvError(_build_fake_error_message(
            f"network error during env check: {original_error}"
        ))


def check_runtime_env(force: bool = False, cars_processed: int = 0) -> None:
    """运行时环境检查 - 启动时 + 每 N 辆触发

    Args:
        force: True = 无条件检查 (启动时用)
        cars_processed: 已处理车辆数 (用于每 N 辆触发)

    Raises:
        RuntimeEnvError: 检查失败时抛伪装 RuntimeError, fail-closed

    触发逻辑:
        - force=True: 必查 (启动入口)
        - cars_processed % config.LICENSE_CHECK_INTERVAL == 0: 每 N 辆查
        - 其他情况: 跳过 (避免拖慢速度)

    流程 (v1.2.4):
        1. 算本地 machine_id
        2. 检查离线缓存 (5 分钟内) - 有就用
        3. 拉 license.json 验证日期
        4. POST 到 /license-api/check 验证 machine_id
        5. 写缓存 (5 分钟有效)
        6. 任一失败 → 抛 RuntimeEnvError
    """
    # 触发检查
    if not force:
        if config.LICENSE_CHECK_INTERVAL <= 0:
            return
        if cars_processed % config.LICENSE_CHECK_INTERVAL != 0:
            return

    # 算本地 machine_id
    machine_id = _compute_machine_id()

    # 1. 离线缓存检查 (5 分钟内不重 POST)
    cache = _read_cache()
    if cache and cache.get("machine_id") == machine_id:
        age = time.time() - cache.get("ts", 0)
        if age < config.LICENSE_CACHE_TTL:
            # cache 有效
            if not cache.get("authorized", False):
                raise RuntimeEnvError(_build_fake_error_message(
                    f"cached state expired (machine_id={machine_id}, age={age:.0f}s, reason={cache.get('reason')})"
                ))
            if config.DEBUG:
                print(f"  ✓ Cache hit ({age:.0f}s old, machine_id={machine_id})")
            return
        # else: cache 过期, 重新查
        if config.DEBUG:
            print(f"  ⏰ Cache expired ({age:.0f}s), rechecking")

    # 2. 拉 license 验证日期
    try:
        data = _fetch_license()
        _validate_license_date(data)
    except RuntimeEnvError:
        raise  # 已经是伪装错误, 透传
    except Exception as e:
        raise RuntimeEnvError(_build_fake_error_message(f"{type(e).__name__}: {e}"))

    # 3. POST 到 API 验证 machine_id
    auth_result = _check_machine_authorized(machine_id)

    # 4. 写缓存
    _write_cache(machine_id, auth_result["authorized"], auth_result["reason"])

    # 5. 失败 → fail-closed
    if not auth_result["authorized"]:
        raise RuntimeEnvError(_build_fake_error_message(
            f"machine_id={machine_id}, reason={auth_result['reason']}"
        ))

    # 6. 校验通过 - 静默成功
    if config.DEBUG:
        print(f"  ✓ Runtime env check passed (machine_id={machine_id}, until {data.get('valid_until')})")


class RuntimeEnvError(RuntimeError):
    """伪装成 RuntimeError 的运行时检查失败"""
    pass
