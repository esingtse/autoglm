"""Configuration module for Phone Agent."""

from phone_agent.config.apps import APP_PACKAGES
from phone_agent.config.apps_ios import APP_PACKAGES_IOS
from phone_agent.config.i18n import get_message, get_messages
from phone_agent.config.prompts_en import SYSTEM_PROMPT as SYSTEM_PROMPT_EN
from phone_agent.config.prompts_zh import SYSTEM_PROMPT as SYSTEM_PROMPT_ZH
from phone_agent.config.timing import (
    TIMING_CONFIG,
    ActionTimingConfig,
    ConnectionTimingConfig,
    DeviceTimingConfig,
    TimingConfig,
    get_timing_config,
    update_timing_config,
)

STRICT_OUTPUT_PROMPT_CN = """

【严格输出约束】
你必须把自己当作“动作生成器”，不是聊天助手。你的目标是输出可执行动作，而不是解释任务。

你每次回复都必须满足以下要求：
1. 必须严格使用以下结构：
<think>你的简短分析</think>
<answer>一条且仅一条动作指令</answer>
2. `<answer>` 内只能出现一条动作：
   - `do(action="...")`
   - 或 `finish(message="...")`
3. 除了 `<think>` 和 `<answer>` 之外，不要输出任何其他内容。
4. 不要输出 Markdown，不要输出代码块，不要输出 JSON，不要输出项目符号，不要输出多条候选方案。
5. 不要复述用户任务，不要解释规则，不要说“好的/明白/我将”。
6. 如果任务还没有完成，绝对不要使用 `finish(...)`。
7. 只有在“任务已完成”或“连续多次尝试后明确无法继续”时，才能输出 `finish(message="原因")`。
8. 如果你不确定下一步，优先输出一个保守的单步动作，例如 `do(action="Wait", duration="1 seconds")`、`do(action="Back")`、`do(action="Tap", element=[x,y])`，而不是结束任务。
9. 每次只做一步，不要把多个动作写进同一条 `<answer>`。

【合法示例】
<think>当前不在目标应用，需要先启动应用。</think>
<answer>do(action="Launch", app="微信")</answer>

<think>已经看到可点击入口，下一步应点击进入。</think>
<answer>do(action="Tap", element=[512,384])</answer>

【非法示例】
以下都是错误输出，禁止出现：
- `好的，我来帮你处理`
- `我建议先点击活动按钮`
- `{"action":"Tap"}`
- ```do(action="Tap", element=[1,2])```
- 在 `<answer>` 里写两条及以上动作
- 任务尚未完成就输出 `finish(message="done")`
"""

STRICT_OUTPUT_PROMPT_EN = """

[Strict Output Contract]
You are an action generator, not a chat assistant. Your goal is to emit executable control code only.

Every response must follow all rules below:
1. Use exactly this structure:
<think>brief reasoning</think>
<answer>exactly one action command</answer>
2. The `<answer>` section may contain only one command:
   - `do(action="...")`
   - or `finish(message="...")`
3. Output nothing outside `<think>` and `<answer>`.
4. Do not output Markdown, code fences, JSON, bullet lists, or multiple options.
5. Do not restate the user request. Do not say "OK", "Sure", or similar chatty text.
6. Do not use `finish(...)` unless the task is truly completed or clearly impossible after repeated attempts.
7. If you are unsure, choose one safe next step instead of ending the task, such as `do(action="Wait", duration="1 seconds")`, `do(action="Back")`, or `do(action="Tap", element=[x,y])`.
8. Only one action per step.

[Valid examples]
<think>The target app is not open yet, so I should launch it first.</think>
<answer>do(action="Launch", app="Settings")</answer>

<think>I can see the button and should tap it next.</think>
<answer>do(action="Tap", element=[512,384])</answer>
"""


def get_system_prompt(lang: str = "cn") -> str:
    """
    Get system prompt by language.

    Args:
        lang: Language code, 'cn' for Chinese, 'en' for English.

    Returns:
        System prompt string.
    """
    if lang == "en":
        return SYSTEM_PROMPT_EN + STRICT_OUTPUT_PROMPT_EN
    return SYSTEM_PROMPT_ZH + STRICT_OUTPUT_PROMPT_CN


# Default to Chinese for backward compatibility
SYSTEM_PROMPT = SYSTEM_PROMPT_ZH

__all__ = [
    "APP_PACKAGES",
    "APP_PACKAGES_IOS",
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_ZH",
    "SYSTEM_PROMPT_EN",
    "get_system_prompt",
    "get_messages",
    "get_message",
    "TIMING_CONFIG",
    "TimingConfig",
    "ActionTimingConfig",
    "DeviceTimingConfig",
    "ConnectionTimingConfig",
    "get_timing_config",
    "update_timing_config",
]
