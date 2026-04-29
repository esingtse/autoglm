"""Lightweight skill layer for task-specific prompt injection."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    """A lightweight task skill resolved from the user task text."""

    skill_id: str
    name: str
    trigger_keywords: tuple[str, ...]
    instruction_cn: str
    instruction_en: str | None = None

    def instruction(self, lang: str = "cn") -> str:
        """Return the localized instruction text."""
        if lang == "en" and self.instruction_en:
            return self.instruction_en
        return self.instruction_cn


EVENT_RECORD_RULE_CN = """
结果记录要求：
1. 当你识别到一个活动后，立刻执行一次 Note 动作记录该活动，不要等到最后一次性总结。
2. Note 的 message 必须是单行对象字符串，字段固定为：{'app_id': xxx, 'package': 'xxx', 'app_name': 'xxx', 'title': 'xxx', 'content': 'xxx', 'reward': 'xxx', 'event_date': 'YYYY-mm-dd', 'ts_crawl': 当前时间戳}
3. 其中 app_id、package、app_name、ts_crawl 可以留空字符串，由系统补齐；title 必须填写；reward 没有就写“无奖励”；event_date 不明确就写空字符串。
4. 每条活动单独记录一次 Note。完成全部采集后，只执行 finish(message="done")，不要在 finish 里重复输出大段总结。
""".strip()


EVENT_RECORD_RULE_EN = """
Structured result rules:
1. As soon as you identify one event, emit one Note action for it instead of waiting until the end.
2. The Note message must be a single-line object-like string with these fields: {'app_id': xxx, 'package': 'xxx', 'app_name': 'xxx', 'title': 'xxx', 'content': 'xxx', 'reward': 'xxx', 'event_date': 'YYYY-mm-dd', 'ts_crawl': current timestamp}
3. app_id, package, app_name, and ts_crawl may be left blank for the system to fill in; title is required; reward should be 'No reward' when absent; event_date should be empty when unknown.
4. Record one Note per event. After all records are collected, use finish(message="done") without repeating the full summary there.
""".strip()


GAME_SKILLS: tuple[Skill, ...] = (
    Skill(
        skill_id="game_generic",
        name="Generic Game",
        trigger_keywords=("游戏", "手游", "活动页", "任务页", "副本", "战斗"),
        instruction_cn="""
你当前使用的是“通用游戏操作”技能。执行游戏任务时，额外遵循以下策略：
1. 优先判断当前是否处于登录弹窗、公告弹窗、活动弹窗、主界面、战斗界面中的哪一种状态，再决定动作。
2. 如果任务目标是“活动”“福利”“公告”“任务”，优先寻找底部导航、顶部标签、右侧悬浮入口，不要把正常活动页误判为弹窗。
3. 游戏页面经常有动态效果。点击按钮后若短时间没有明显变化，先 Wait，再复查是否已进入新页面，避免连续误点。
4. 如果进入战斗且存在“自动战斗”“自动寻路”“跳过”之类入口，优先开启，以减少无效等待。
5. 对需要遍历多个活动页签的任务，按固定方向逐个检查，记录已看过的页签，避免反复进入同一项。
6. 如果页面存在“领取”“前往”“参与”“挑战”等多个按钮，先结合任务目标判断，不要默认点击最显眼按钮。
7. 若连续两次处于相似画面且没有推进，优先尝试 Back、切换页签或更换入口，而不是重复同一点位点击。
""".strip(),
        instruction_en="""
Use the generic game skill. Identify whether the screen is a login dialog, popup, main lobby, event page, or battle page before acting. Prefer event/task/welfare entries in bottom navigation, top tabs, or side rails. After taps, wait and verify state changes before retrying. Enable auto-battle, auto-pathing, or skip when available. Traverse tabs in a fixed order and avoid revisiting the same entry repeatedly.
""".strip(),
    ),
    Skill(
        skill_id="wangzhe",
        name="王者荣耀",
        trigger_keywords=("王者荣耀", "王者"),
        instruction_cn="""
你当前使用的是“王者荣耀”技能。执行任务时，额外遵循以下策略：
1. 目标通常是先进入游戏主界面，再从右下角或底部导航寻找“活动”入口。
2. 如果打开“活动”后直接出现默认活动页，这通常代表已经成功进入活动中心，不要把它误判为需要关闭的弹窗。
3. 活动页通常有左侧或侧边的二级标签。需要遍历时，应按从上到下顺序逐个查看，并记录哪些标签已经检查过。
4. 如果需要采集活动信息，优先提取活动标题、规则、奖励、时间；没有奖励时明确记为“无奖励”。
5. 遇到开屏公告、更新提示、礼包弹窗时，先区分它们和真正的活动主页；只有确认阻挡任务目标时才关闭。
""".strip(),
    ),
    Skill(
        skill_id="heping",
        name="和平精英",
        trigger_keywords=("和平精英", "吃鸡"),
        instruction_cn="""
你当前使用的是“和平精英”技能。执行任务时，额外遵循以下策略：
1. 目标通常是先进入游戏主界面，再寻找“活动”入口，不要把登录后默认展示的活动页误判成普通弹窗。
2. 活动页通常有右侧或侧边的活动列表。遍历时按顺序逐个进入，避免重复打开同一个活动。
3. 若页面同时存在“资讯”“公告”“活动”等入口，任务要求采集活动时优先选择“活动”，不要误入“资讯”。
4. 若活动分页超过一屏，使用稳定的短距离滑动查看下一屏，并继续按顺序检查未访问项。
5. 采集活动内容时，优先记录标题、规则、奖励、活动日期；没有奖励时明确写“无奖励”。
""".strip(),
    ),
)


def resolve_skill(task: str, skill_id: str | None = None) -> Skill | None:
    """Resolve a skill from a task string or an explicit skill id."""
    normalized_task = task.lower()

    if skill_id:
        for skill in GAME_SKILLS:
            if skill.skill_id == skill_id:
                return skill
        return None

    for skill in GAME_SKILLS:
        if any(keyword.lower() in normalized_task for keyword in skill.trigger_keywords):
            return skill

    return None


def build_skill_prompt(base_prompt: str, task: str, lang: str = "cn", skill_id: str | None = None) -> tuple[str, Skill | None]:
    """Append skill instructions to the base system prompt when a skill matches."""
    skill = resolve_skill(task, skill_id=skill_id)
    if skill is None:
        return base_prompt, None

    skill_block = (
        "\n\n"
        + ("【Skill】\n" if lang == "en" else "【技能】\n")
        + f"{skill.name}\n"
        + skill.instruction(lang)
        + "\n\n"
        + (EVENT_RECORD_RULE_EN if lang == "en" else EVENT_RECORD_RULE_CN)
    )
    return base_prompt + skill_block, skill
