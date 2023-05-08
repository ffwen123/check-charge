#!/usr/bin/env python
# -*- coding=utf-8 -*-
"""
@time: 2023/5/4 17:32
@Project ：chatgpt-on-wechat
@file: botcharge.py
"""
import json
import os
import requests
import itchat
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from config import conf
import plugins
from plugins import *
from common.log import logger
from common.expired_dict import ExpiredDict


@plugins.register(name="BotCharge", desc="调用API接口判断用户权限", desire_priority=100, version="0.1",
                  author="ffwen123")
class BotCharge(Plugin):
    def __init__(self):
        super().__init__()
        curdir = os.path.dirname(__file__)
        config_path = os.path.join(curdir, "config.json")
        self.params_cache = ExpiredDict(60 * 60)
        self.agent_id = conf().get("wechatcomapp_agent_id")
        if not os.path.exists(config_path):
            logger.info('[RP] 配置文件不存在，将使用config.json.template模板')
            config_path = os.path.join(curdir, "config.json.template")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.check_url = config["check_url"]
                self.pay_url = config["pay_url"]
                self.charge_url = config["charge_url"]
                self.check_count = config["check_count"]
                if not self.check_url:
                    raise Exception("please set your check_url in config or environment variable.")
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply
            logger.info("[RP] inited")
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                logger.warn(f"[RP] init failed, config.json not found.")
            else:
                logger.warn("[RP] init failed." + str(e))
            raise e

    def on_handle_context(self, e_context: EventContext):
        if e_context['context'].type not in [ContextType.IMAGE_CREATE,
                                             ContextType.IMAGE,
                                             ContextType.VOICE,
                                             ContextType.TEXT]:
            return
        logger.debug("[RP] on_handle_context. content: %s" % e_context['context'].content)
        reply = Reply()
        try:
            user_id = e_context['context']["msg"].from_user_id
            # 校验用户权限
            check_perm = requests.get(self.check_url, params={"user_id": user_id,
                                                              "agent_id": self.agent_id}, timeout=3.05)
            # itchat.send("@msg@ 测试主动发消息成功", toUserName=user_id)
            logger.info("[RP] check User result, result={}".format(check_perm.text))
            if check_perm.json().get("result") != "1":
            # if check_perm.json().get("result") in ["0", "-1"]:
                # 返回付款连接
                reply.type = ReplyType.INFO
                reply.content = self.check_count + "\n" + self.pay_url.format(self.agent_id)
                e_context.action = EventAction.BREAK_PASS  # 事件结束后，跳过处理context的默认逻辑
                e_context['reply'] = reply
                logger.info("[RP] check User Permissions fail! user_id={}, agent_id={}".format(user_id, self.agent_id))
            # elif check_perm.json().get("result") == "2":
            #     # 返回当天次数用完
            #     reply.type = ReplyType.INFO
            #     reply.content = "您有免费额度3次，或者" + "\n" + self.pay_url.format(self.agent_id)
            #     e_context.action = EventAction.BREAK_PASS  # 事件结束后，跳过处理context的默认逻辑
            #     e_context['reply'] = reply
            else:
                logger.info("[RP] check success! user_id={}, agent_id={}".format(user_id, self.agent_id))
        except Exception as e:
            reply.type = ReplyType.ERROR
            reply.content = "[RP] " + str(e)
            e_context['reply'] = reply
            logger.exception("[RP] exception: %s" % e)
            e_context.action = EventAction.BREAK_PASS

    def on_decorate_reply(self, e_context: EventContext):
        if e_context["reply"].type in [ReplyType.TEXT, ReplyType.VOICE]:
            if e_context["reply"].content:
                try:
                    user_id = e_context['context']["msg"].from_user_id
                    requests.get(self.charge_url, params={
                        "user_id": user_id,
                        "agent_id": self.agent_id}, timeout=3.05)
                    logger.info("[RP] user charge success! user_id={}, agent_id={}".format(user_id, self.agent_id))
                except Exception as e:
                    logger.exception("[RP] exception: %s" % e)
            return
