import abc

from aws_cdk import core as cdk


class IProjector:
    pass


class ProjectorBase(cdk.Construct, IProjector):
    pass


class IProjectionHook:
    @abc.abstractmethod
    def bind(self, projector: IProjector):
        pass


class IDomainEventChannelSubscription:
    @abc.abstractmethod
    def bind(self, projector: IProjector):
        pass


class IIntegrationEventChannelHook:
    @abc.abstractmethod
    def bind(self, projector: IProjector):
        pass


class ITraceSegmentStoreHook:
    @abc.abstractmethod
    def bind(self, projector: IProjector):
        pass
