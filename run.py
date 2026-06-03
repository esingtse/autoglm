from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig
from phone_agent.model import ModelConfig


import os

# 通过 Google Gemini 的 OpenAI 兼容接入端点调用
# 文档: https://ai.google.dev/gemini-api/docs/openai
# 在 https://aistudio.google.com/app/apikey 获取 API Key

# Gemini
model_config = ModelConfig(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    model_name="gemini-3.5-flash",
    api_key='',
    extra_body={
        "reasoning_effort": "low",   # 关闭思考；也可 "low" / "medium" / "high"
    },
)

# Qwen
# model_config = ModelConfig(
#     base_url="https://calciumion-new-api.dam-test.umlife.com/v1",
#     model_name="qwen3.7-plus",
#     api_key='',
#     extra_body={
#         "reasoning_effort": "low",   # 关闭思考；也可 "low" / "medium" / "high"
#     },
# )


agent = PhoneAgent(
    model_config=model_config,
    agent_config=AgentConfig(lang="cn",verbose=True, max_steps=1000),
)


TASK_WANGZHE = """
第一步：帮我打开王者荣耀，进入游戏并查看活动。注意不要把登录后的默认活动页误判成需要关闭的弹窗，我需要进入真正的游戏活动中心。

第二步：找到“活动”入口并进入。如果进入后直接展示某个默认活动页，说明已经成功进入活动中心，不要退出。

第三步：遍历活动页中的所有活动标签。优先按固定顺序逐个查看，不要重复进入同一个活动。如果活动列表超过一屏，就继续滑动直到看完。如果持续两次点击活动后无法切换，则代表没有更多活动了，不要继续点击。

第四步：每识别到一个活动，就立刻记录一条结构化结果。不要等到最后统一总结。记录时请使用：
do(action="Note", message="{'app_id': '', 'package': '', 'app_name': '', 'title': '活动标题', 'content': '活动内容', 'reward': '活动奖励，没有则写无奖励', 'event_date': 'YYYY-mm-dd', 'ts_crawl': ''}")

第五步：全部活动识别完成后，只执行：
finish(message="done")
不要在 finish 里重复输出大段总结。
""".strip()


# TASK_HEPING = """
# 第一步：帮我打开和平精英，进入游戏并查看活动，要注意不是登录界面的弹窗显示的活动，我需要进入到游戏主页面。
# 第二步:点击屏幕右下方带有"活动"字样的图标，坐标:(903, 620),当点击一次之后，后面的步骤都在活动页面进行，不要重复点击进入活动页面了。 
# 第三步：记录下这个页面下面的所有活动标题，并输出他们各自的坐标。然后再分别点击具体的活动，收集分析活动规则内容和奖励.
# 第四步:汇总使用json格式输出。
# """.strip()

# TASK_HEPING = """
# 第一步：帮我打开和平精英，进入游戏并查看活动，要注意不是登录界面的弹窗显示的活动，我需要进入到游戏主页面。
# 第二步:点击屏幕右下方带有"活动>>>"字样的图标，期间可能在右侧的一级菜单中有多个标签页，我需要你准确识别带有"活动"字样的标签页并点击进入。 
# 第三步：当进入活动页面之后，需要确认右侧一级标签页是否处于“活动”标签页的选中状态，选中状态的活动标签会变成白底深色字，后面的步骤都在此活动页面进行，不要重复点击进入活动页面或者其他标签页了
# 第四步：记录下活动页面的标题（在右侧有个可以滚动的二级活动列表），然后按顺序逐个点击活动（要注意活动与活动之间会有一些分割线标题，要区分开，一般活动卡片是有图片加下方的文字来组成一个完整的活动，当前选中的活动会在图片左侧出现一个小箭头），获取活动页面的标题和具体规则内容和奖励。活动列表可以下拉，但要避免点击到最下方的“时光商店”。
# 第五步: 汇总使用txt格式输出
# """.strip()

TASK_HEPING = """
第一步：在屏幕中找到《和平精英》游戏图标并点击启动，等待游戏加载完成并进入主屏幕。加载过程中如有任何弹窗、提示框、权限请求或通知出现，自行寻找关闭、跳过、同意或确认按钮将其关闭，不需要请求用户协助，直到完全进入游戏主屏幕为止。

第二步：在屏幕中寻找与"活动"相关的入口，点击进入活动中心页面。

第三步：进入活动中心后，找到所有一级标签页，逐一点击每个一级标签，判断该标签下是否包含活动内容。如果包含则收集，不包含则跳过，继续下一个。所有一级标签都必须依次检查，不能跳过。

第四步：在每个含有活动内容的一级标签下，逐个查看所有活动，获取每个活动的所属一级标签名称、活动名称、活动时间、参与规则和奖励内容。列表需要从顶部开始，持续向下滚动直到底部，确保所有活动都被加载并收集，不能遗漏。每次滚动后需等待内容加载完成再继续。

第五步：所有一级标签都检查完毕后，输出一条 Note，包含从所有标签下收集到的完整活动信息，格式如下：

=== 活动汇总 ===

【所属一级标签 - 活动名称】
活动时间：xxx
规则：xxx
奖励：xxx

（每个活动之间空一行）

输出完这条汇总 Note 之后，再执行 finish。
""".strip()


# task = TASK_WANGZHE
task = TASK_HEPING

result = agent.run(task)
print(result)

# if agent.active_skill is not None:
#     print(f"Matched skill: {agent.active_skill.skill_id} ({agent.active_skill.name})")
