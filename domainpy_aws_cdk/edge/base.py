from __future__ import annotations

import abc

from aws_cdk import core as cdk


class IGateway:
    @abc.abstractmethod
    def add_integration_event_subscriptions(self, *integration_event_subscriptions: IIntegrationEventSubscription):
        pass

    @abc.abstractmethod
    def add_channels(self, *channels: IChannelHook):
        pass


class BaseGateway(cdk.Construct, IGateway):
    def add_integration_event_subscriptions(self, *integration_event_subscriptions: IIntegrationEventSubscription):
        for integration_event_subscription in integration_event_subscriptions:
            integration_event_subscription.bind(self)

    def add_channels(self, *channels: IChannelHook):
        for channel in channels:
            channel.bind(self)


class ITraceStoreHook:
    @abc.abstractmethod
    def bind(self, gateway: IGateway):
        pass


class IChannelHook:
    @abc.abstractmethod
    def bind(self, gateway: IGateway):
        pass


class IIntegrationEventSubscription:
    @abc.abstractmethod
    def bind(self, gateway: IGateway):
        pass
