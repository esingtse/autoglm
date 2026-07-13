# -*- coding: utf-8 -*-
import asyncio
import logging
import time
from typing import Optional

import grpc

from commonproto.pb4.proto.grpc.k2av_pb2 import Reply
from commonproto.pb4.proto.grpc.k2av_pb2 import Request
from commonproto.pb4.proto.grpc.k2av_pb2_grpc import K2AVServiceStub

logger = logging.getLogger(__name__)


def create_k2av_stub(server: str, channel_options: list = None) -> K2AVServiceStub:
    """创建 k2av stub

    Args:
        server: gRPC server
        channel_options: An optional list of key-value pairs to configure the channel.

    Returns:
        K2AVServiceStub
    """
    logger.info(f"creating k2av channel...{server=}")
    channel = grpc.insecure_channel(target=server, options=channel_options)
    return K2AVServiceStub(channel)


def create_k2av_aio_stub(server: str, channel_options: list = None) -> K2AVServiceStub:
    """创建支持异步的 k2av stub

    Args:
        server: gRPC server
        channel_options: An optional list of key-value pairs to configure the channel.

    Returns:
        K2AVServiceStub
    """
    logger.info(f"creating k2av aio.channel...{server=}")
    channel = grpc.aio.insecure_channel(target=server, options=channel_options)
    return K2AVServiceStub(channel)


def send_k2av(
    stub: K2AVServiceStub, request: Request, retries: int = 3, timeout: int = 10, delay: int = 0
) -> Optional[Reply]:
    """将数据发送至 k2av server

    Args:
        stub: K2AVServiceStub
        request: k2av_pb2.Request
        retries: 最大重试次数
        timeout: 单次请求超时时间
        delay: seconds 重试间隔时间

    Returns:

    """
    last_error = None
    while retries >= 0:
        retries -= 1
        try:
            reply = stub.SendGRPC(request, timeout=timeout)
            logger.info(f"success, sent to k2av: {reply.code=}")
            return reply
        except grpc.RpcError as error:
            last_error = error
            logger.warning(f"retry to send, left {retries=} {error=}")
            if delay > 0:
                time.sleep(delay)
    logger.error(f"failed, {last_error=} {request=}")
    raise last_error


async def send_k2av_aio(
    stub: K2AVServiceStub, request: Request, retries: int = 3, timeout: int = 10, delay: int = 0
) -> Optional[Reply]:
    """将数据发送至 k2av server

    Args:
        stub: K2AVServiceStub
        request: k2av_pb2.Request
        retries: 最大重试次数
        timeout: 单次请求超时时间
        delay: seconds 重试间隔时间

    Returns:

    """
    last_error = None
    while retries >= 0:
        retries -= 1
        try:
            reply = await stub.SendGRPC(request, timeout=timeout)
            logger.debug(f"success, sent to k2av: {reply.code=}")
            return reply
        except grpc.RpcError as error:
            last_error = error
            logger.warning(f"retry to send, left {retries=} {error=}")
            if delay > 0:
                await asyncio.sleep(delay)
    logger.error(f"failed, {last_error=} {request=}")
    raise last_error
