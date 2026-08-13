# -*- coding: utf-8 -*-
"""
第0部手机：最初六款通用模板游戏
===========================
- 和平精英、王者荣耀、蛋仔派对、小小蚁国、完美世界、三角洲行动
- 全部使用通用模板 TASK_HEPING（%s 替换游戏名，第一步含"如果遇到登录，优先选'QQ登录'"）
- 导出: GAMES / GAME_PROMPT_MAPPING / DEFAULT_PROMPT
"""

# 默认模板（通用）从 phone1 引入
from prompts.phone1 import TASK_HEPING

# ============================================================
# 本手机配置：游戏列表 + prompt 映射
# ============================================================
# 本手机安装的游戏（一次跑完）
GAMES = ["和平精英", "王者荣耀", "蛋仔派对", "小小蚁国", "完美世界", "三角洲行动"]

# 游戏名 → 专属 prompt（未配置的游戏回退 DEFAULT_PROMPT）
GAME_PROMPT_MAPPING = {}

# 默认 prompt（未配置专属 prompt 的游戏使用）
DEFAULT_PROMPT = TASK_HEPING
