import asyncio
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.message.components import At, Reply


from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
from utils import get_ats

@register(
    "astrbot_plugin_recall",
    "Zhalslar",
    "智能撤回插件，可自动判断各场景下消息是否需要撤回",
    "v1.0.0",
    "https://github.com/Zhalslar/astrbot_plugin_recall",
)
class RecallPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)

    @filter.command("撤回")
    async def delete_msg(self, event: AiocqhttpMessageEvent):
        """(引用消息)撤回 | 撤回 @某人(默认bot) 数量(默认10)"""
        client = event.bot
        chain = event.get_messages()
        first_seg = chain[0]
        if isinstance(first_seg, Reply):
            try:
                await client.delete_msg(message_id=int(first_seg.id))
            except Exception:
                yield event.plain_result("我无权撤回这条消息")
            finally:
                event.stop_event()
        elif any(isinstance(seg, At) for seg in chain):
            target_ids = get_ats(event) or [event.get_self_id()]
            target_ids = {str(uid) for uid in target_ids}

            end_arg = event.message_str.split()[-1]
            count = int(end_arg) if end_arg.isdigit() else 10

            payloads = {
                "group_id": int(event.get_group_id()),
                "message_seq": 0,
                "count": count,
                "reverseOrder": True,
            }
            result: dict = await client.api.call_action(
                "get_group_msg_history", **payloads
            )

            messages = list(reversed(result.get("messages", [])))
            delete_count = 0
            sem = asyncio.Semaphore(10)

            # 撤回消息
            async def try_delete(message: dict):
                nonlocal delete_count
                if str(message["sender"]["user_id"]) not in target_ids:
                    return
                async with sem:
                    try:
                        await client.delete_msg(message_id=message["message_id"])
                        delete_count += 1
                    except Exception:
                        pass

            # 并发撤回
            tasks = [try_delete(msg) for msg in messages]
            await asyncio.gather(*tasks)

            yield event.plain_result(f"已从{count}条消息中撤回{delete_count}条")
