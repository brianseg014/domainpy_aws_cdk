import abc

from aws_cdk import core as cdk


class IGateway:
    pass


class BaseGateway(cdk.Construct, IGateway):
    pass


class ITraceStoreHook:
    @abc.abstractmethod
    def bind(self, gateway: IGateway):
        pass


class ICommandChannelHook:
    @abc.abstractmethod
    def bind(self, gateway: IGateway):
        pass


class ITraceStoreSubscription:
    @abc.abstractmethod
    def bind(self, trace_store_hook: ITraceStoreHook):
        pass
