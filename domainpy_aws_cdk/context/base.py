from __future__ import annotations

import abc

from aws_cdk import core as cdk


class IContext:
    @abc.abstractmethod
    def add_command_subscriptions(self, *command_channel_subscriptions: ICommandChannelSubscription):
        pass

    @abc.abstractmethod
    def add_channels(self, *channels_hook: IChannelHook):
        pass


class ContextBase(cdk.Construct, IContext):
    def add_command_subscriptions(self, *command_channel_subscriptions: ICommandChannelSubscription):
        for command_channel_subscription in command_channel_subscriptions:
            command_channel_subscription.bind(self)

    def add_channels(self, *channels_hook: IChannelHook):
        for channel_hook in channels_hook:
            channel_hook.bind(self)


class ICommandChannelSubscription:
    @abc.abstractmethod
    def bind(self, context: IContext):
        pass


class IChannelHook:
    @abc.abstractmethod
    def bind(self, context: IContext):
        pass


class IEventStoreHook:
    @abc.abstractmethod
    def bind(self, context: IContext):
        pass


class ITraceSegmentStoreHook:
    @abc.abstractmethod
    def bind(self, context: IContext):
        pass
