import abc

from aws_cdk import core as cdk


class IContextMap:
    pass


class ContextMapBase(cdk.Construct, IContextMap):
    pass


class IDomainEventChannelSubscription:
    @abc.abstractmethod
    def bind(self, context_map: IContextMap):
        pass


class IContextHook:
    @abc.abstractmethod
    def bind(self, context_map: IContextMap):
        pass


class ITraceSegmentStoreHook:
    @abc.abstractmethod
    def bind(self, context_map: IContextMap):
        pass
