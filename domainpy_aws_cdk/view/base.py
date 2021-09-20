import abc

from aws_cdk import core as cdk


class IView:
    pass


class ViewBase(cdk.Construct, IView):
    pass


class IQueryChannelSubscription:
    @abc.abstractmethod
    def bind(self, view: IView):
        pass


class IChannelHook:
    @abc.abstractmethod
    def bind(self, view: IView):
        pass


class IProjectionHook:
    @abc.abstractmethod
    def bind(self, view: IView):
        pass


class ITraceSegmentStoreHook:
    @abc.abstractmethod
    def bind(self, view: IView):
        pass
