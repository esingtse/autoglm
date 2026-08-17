"""Device control utilities for Android automation."""

import os
import subprocess
import time
from typing import List, Optional, Tuple

from phone_agent.config.apps import APP_PACKAGES
from phone_agent.config.timing import TIMING_CONFIG


def get_current_app(device_id: str | None = None) -> str:
    """
    Get the currently focused app name.

    Args:
        device_id: Optional ADB device ID for multi-device setups.

    Returns:
        The app name if recognized, otherwise "System Home".
    """
    adb_prefix = _get_adb_prefix(device_id)

    result = subprocess.run(
        adb_prefix + ["shell", "dumpsys", "window"], capture_output=True, text=True, encoding="utf-8"
    )
    output = result.stdout
    if not output:
        raise ValueError("No output from dumpsys window")

    # Parse window focus info
    for line in output.split("\n"):
        if "mCurrentFocus" in line or "mFocusedApp" in line:
            for app_name, package in APP_PACKAGES.items():
                if package in line:
                    return app_name

    return "System Home"


def tap(
    x: int, y: int, device_id: str | None = None, delay: float | None = None
) -> None:
    """
    Tap at the specified coordinates.

    Args:
        x: X coordinate.
        y: Y coordinate.
        device_id: Optional ADB device ID.
        delay: Delay in seconds after tap. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_tap_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(delay)


def double_tap(
    x: int, y: int, device_id: str | None = None, delay: float | None = None
) -> None:
    """
    Double tap at the specified coordinates.

    Args:
        x: X coordinate.
        y: Y coordinate.
        device_id: Optional ADB device ID.
        delay: Delay in seconds after double tap. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_double_tap_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(TIMING_CONFIG.device.double_tap_interval)
    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(delay)


def long_press(
    x: int,
    y: int,
    duration_ms: int = 3000,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    """
    Long press at the specified coordinates.

    Args:
        x: X coordinate.
        y: Y coordinate.
        duration_ms: Duration of press in milliseconds.
        device_id: Optional ADB device ID.
        delay: Delay in seconds after long press. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_long_press_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix
        + ["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms)],
        capture_output=True,
    )
    time.sleep(delay)


def swipe(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration_ms: int | None = None,
    device_id: str | None = None,
    delay: float | None = None,
) -> None:
    """
    Swipe from start to end coordinates.

    Args:
        start_x: Starting X coordinate.
        start_y: Starting Y coordinate.
        end_x: Ending X coordinate.
        end_y: Ending Y coordinate.
        duration_ms: Duration of swipe in milliseconds (auto-calculated if None).
        device_id: Optional ADB device ID.
        delay: Delay in seconds after swipe. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_swipe_delay

    adb_prefix = _get_adb_prefix(device_id)

    if duration_ms is None:
        # Calculate duration based on distance
        dist_sq = (start_x - end_x) ** 2 + (start_y - end_y) ** 2
        duration_ms = int(dist_sq / 1000)
        duration_ms = max(1000, min(duration_ms, 2000))  # Clamp between 1000-2000ms

    subprocess.run(
        adb_prefix
        + [
            "shell",
            "input",
            "swipe",
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
            str(duration_ms),
        ],
        capture_output=True,
    )
    time.sleep(delay)


def back(device_id: str | None = None, delay: float | None = None) -> None:
    """
    Press the back button.

    Args:
        device_id: Optional ADB device ID.
        delay: Delay in seconds after pressing back. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_back_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "keyevent", "4"], capture_output=True
    )
    time.sleep(delay)


def home(device_id: str | None = None, delay: float | None = None) -> None:
    """
    Press the home button.

    Args:
        device_id: Optional ADB device ID.
        delay: Delay in seconds after pressing home. If None, uses configured default.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_home_delay

    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "keyevent", "KEYCODE_HOME"], capture_output=True
    )
    time.sleep(delay)


def launch_app(
    app_name: str, device_id: str | None = None, delay: float | None = None
) -> bool:
    """
    Launch an app by name.

    Args:
        app_name: The app name (must be in APP_PACKAGES).
        device_id: Optional ADB device ID.
        delay: Delay in seconds after launching. If None, uses configured default.

    Returns:
        True if app was launched, False if app not found.
    """
    if delay is None:
        delay = TIMING_CONFIG.device.default_launch_delay

    if app_name not in APP_PACKAGES:
        return False

    adb_prefix = _get_adb_prefix(device_id)
    package = APP_PACKAGES[app_name]

    subprocess.run(
        adb_prefix
        + [
            "shell",
            "monkey",
            "-p",
            package,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ],
        capture_output=True,
    )
    time.sleep(delay)
    return True


def get_screen_state(device_id: str | None = None) -> str:
    """
    Check whether the screen is on or off.

    Args:
        device_id: Optional ADB device ID.

    Returns:
        "on" if the screen is awake, "off" if it is asleep/off.
    """
    out = _adb_shell(device_id, ["dumpsys", "power"])
    if "mWakefulness=Awake" in out:
        return "on"
    return "off"


def is_locked(device_id: str | None = None) -> bool:
    """
    Check whether the device is on the lock screen.

    Args:
        device_id: Optional ADB device ID.

    Returns:
        True if the keyguard/lock screen is showing.
    """
    out = _adb_shell(device_id, ["dumpsys", "window", "policy"])
    if not out:
        return False
    # 覆盖不同 ROM / Android 版本的锁屏标志：
    #   mIsShowing             —— KeyguardStateMonitor（小米 HyperOS / MIUI 等）
    #   isStatusBarKeyguard    —— AOSP 状态栏 keyguard
    #   mShowingLockscreen     —— 锁屏界面显示
    #   isKeyguardShowing      —— 部分厂商
    return any(
        f"{flag}=true" in out
        for flag in (
            "mIsShowing",
            "isStatusBarKeyguard",
            "mShowingLockscreen",
            "isKeyguardShowing",
        )
    )


def wake_up(device_id: str | None = None, delay: float | None = None) -> None:
    """
    Wake up the screen (KEYCODE_WAKEUP). Safe to call even if already awake.

    Args:
        device_id: Optional ADB device ID.
        delay: Delay in seconds after the keyevent.
    """
    if delay is None:
        delay = 1.0

    _adb_shell(device_id, ["input", "keyevent", "KEYCODE_WAKEUP"])
    time.sleep(delay)


def dismiss_keyguard(device_id: str | None = None) -> bool:
    """
    Dismiss the lock screen with an upward swipe (no password/PIN required).

    Args:
        device_id: Optional ADB device ID.

    Returns:
        True if the device is unlocked afterwards, False otherwise.
    """
    # Best-effort: some ROMs accept wm dismiss-keyguard; ignore failure.
    _adb_shell(device_id, ["wm", "dismiss-keyguard"])
    time.sleep(0.3)

    w, h = _get_screen_size(device_id)
    start_y = int(h * 0.85)
    end_y = int(h * 0.2)

    for _ in range(3):
        swipe(
            w // 2,
            start_y,
            w // 2,
            end_y,
            duration_ms=300,
            device_id=device_id,
            delay=0.8,
        )
        if not is_locked(device_id):
            return True
    return False


def lock_screen(device_id: str | None = None) -> None:
    """
    Lock the screen and turn it off (KEYCODE_SLEEP, fallback KEYCODE_POWER).

    Args:
        device_id: Optional ADB device ID.
    """
    _adb_shell(device_id, ["input", "keyevent", "KEYCODE_SLEEP"])
    time.sleep(0.5)
    if get_screen_state(device_id) == "on":
        _adb_shell(device_id, ["input", "keyevent", "KEYCODE_POWER"])
        time.sleep(0.5)


def _get_screen_size(device_id: str | None) -> tuple[int, int]:
    """Get the screen resolution, falling back to 1080x2400."""
    out = _adb_shell(device_id, ["wm", "size"])
    for token in out.split():
        if "x" in token:
            parts = token.split("x")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return int(parts[0]), int(parts[1])
    return 1080, 2400


def _adb_shell(device_id: str | None, args: list) -> str:
    """Run an `adb shell` command and return combined stdout/stderr text."""
    try:
        result = subprocess.run(
            _get_adb_prefix(device_id) + ["shell"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return ""
    return (result.stdout or "") + (result.stderr or "")


def _get_adb_prefix(device_id: str | None) -> list:
    """Get ADB command prefix with optional device specifier."""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]
