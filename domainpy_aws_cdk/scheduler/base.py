import abc

from aws_cdk import core as cdk
from aws_cdk import aws_lambda as lambda_


class IScheduleEventChannel:
    pass


class ScheduleEventChannelBase(cdk.Construct, IScheduleEventChannel):
    pass


class IIntegrationEventChannelHook:
    @abc.abstractmethod
    def bind(self, schedule_event_channel: IScheduleEventChannel):
        pass
