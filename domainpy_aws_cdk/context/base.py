import abc

from aws_cdk import core as cdk


class IContext:
    pass


class ContextBase(cdk.Construct, IContext):
    pass


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
