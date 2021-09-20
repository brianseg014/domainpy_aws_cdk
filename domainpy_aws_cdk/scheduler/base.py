import abc

from aws_cdk import core as cdk
from aws_cdk import aws_lambda as lambda_


class ISchedulerChannel:
    pass


class SchedulerChannelBase(cdk.Construct, ISchedulerChannel):
    pass


class IIntegrationEventChannelHook:
    @abc.abstractmethod
    def bind(self, scheduler: ISchedulerChannel) -> None:
        pass

    @abc.abstractproperty
    def function(self) -> lambda_.Function:
        pass


class IntegrationEventChannelHookBase(IIntegrationEventChannelHook):
    pass
