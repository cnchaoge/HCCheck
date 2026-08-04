"""运行时环境检查 - v1.2.3

伪装成普通运行时检查, 实际是 license 验证 (防复制用)。

为什么用这个名字:
- 看起来像普通的 "环境健康检查"
- 不直接叫 license_check.py (一眼看穿)
- 错误信息伪装成 RuntimeError (不是 LicenseError)

设计:
- 启动时强制检查 (force=True)
- 每 N 辆车检查一次 (cars_processed % N == 0)
- fail-closed: 任何失败 (网络/解析/过期) 都抛 RuntimeError 停止运行
- 失败信息伪装成技术错误, 联系方式藏在 "请联系作者" 里

防破解点:
1. 模块名 runtime_check.py (不像 license)
2. 错误信息是 RuntimeError + 技术栈 (不像授权失败)
3. 错误里不出现 "license" / "授权" / "续费" / "expiry" 等关键字
4. 失败原因写得技术化 (unexpected EOF, 环境变量缺失等)
5. 联系人方式只有手机号, 不透露 license 机制
"""
import urllib.request
import json
import os
from datetime import date
from typing import Optional

import config


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
    """
    # 触发检查
    if not force:
        if config.LICENSE_CHECK_INTERVAL <= 0:
            return  # 配置为 0 = 禁用
        if cars_processed % config.LICENSE_CHECK_INTERVAL != 0:
            return  # 还不到检查时机

    # 实际拉 license (伪装成"读取配置")
    original_error = None
    data = None
    try:
        req = urllib.request.Request(
            config.LICENSE_URL,
            headers={"User-Agent": "HCCheck/1.2.3"},
        )
        with urllib.request.urlopen(req, timeout=config.LICENSE_TIMEOUT) as resp:
            content = resp.read()
        data = json.loads(content)
    except Exception as e:
        original_error = f"{type(e).__name__}: {e}"

    # 失败分支 - 伪装成技术错误
    if data is None:
        raise RuntimeEnvError(_build_fake_error_message(original_error))

    # 校验必需字段 (伪装成"配置项缺失")
    valid_until_str = data.get("valid_until")
    if not valid_until_str:
        raise RuntimeEnvError(_build_fake_error_message("missing 'valid_until' key"))

    # 校验日期 (伪装成"格式错误")
    try:
        valid_until = date.fromisoformat(valid_until_str)
    except (ValueError, TypeError) as e:
        raise RuntimeEnvError(_build_fake_error_message(f"date parse: {e}"))

    # 校验过期 (伪装成"系统时钟"或"环境变量")
    if date.today() > valid_until:
        # 注意: 不说 "expired" / "过期", 伪装成"数据已失效"
        raise RuntimeEnvError(_build_fake_error_message(
            f"data timestamp out of range (got {valid_until_str}, expected future date)"
        ))

    # 校验会话车辆限额 (伪装成"内存限制")
    max_cars = data.get("max_cars_per_session", 99999)
    if cars_processed >= max_cars:
        raise RuntimeEnvError(_build_fake_error_message(
            f"cars_processed ({cars_processed}) >= session_limit ({max_cars})"
        ))

    # 校验通过 - 静默成功 (DEBUG 模式才打)
    if config.DEBUG:
        print(f"  ✓ Runtime env check passed (until {valid_until_str})")

class RuntimeEnvError(RuntimeError):
    """伪装成 RuntimeError 的运行时检查失败"""
    pass
