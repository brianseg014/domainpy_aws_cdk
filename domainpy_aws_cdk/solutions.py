import typing

from aws_cdk import core as cdk

from domainpy_aws_cdk.templates import BusinessConceptTemplate, BusinessConceptChannels, MessageTypeTemplate
from domainpy_aws_cdk.edge.base import IGateway
from domainpy_aws_cdk.context.base import IContext
from domainpy_aws_cdk.scheduler.base import IScheduleEventChannel
from domainpy_aws_cdk.xcom.base import IChannel

from domainpy_aws_cdk import scheduler
from domainpy_aws_cdk import xcom

from domainpy_aws_cdk.edge import hooks as edge_hooks
from domainpy_aws_cdk.context import hooks as context_hooks
from domainpy_aws_cdk.scheduler import hooks as scheduler_hooks


class MessageTypeSolution(MessageTypeTemplate):

    @classmethod
    def _bring_command_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        return xcom.SnsTopicChannel.bring(scope, id, export_name)

    @classmethod
    def _bring_query_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        return xcom.SnsTopicChannel.bring(scope, id, export_name)

    @classmethod
    def _bring_integration_event_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        return xcom.SnsTopicChannel.bring(scope, id, export_name)

    @classmethod
    def _bring_schedule_event_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        return xcom.SnsTopicChannel.bring(scope, id, export_name)

    @classmethod
    def _bring_domain_event_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        return xcom.SnsTopicChannel.bring(scope, id, export_name)

    @classmethod
    def _bring_query_result_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        return xcom.DynamoDBTableChannel.bring(scope, id, export_name)
    
    def _create_command_channel(self, id: str, export_name: str) -> IChannel:
        return xcom.SnsTopicChannel(self, id, export_name=export_name)

    def _create_query_channel(self, id: str, export_name: str) -> IChannel:
        return xcom.SnsTopicChannel(self, id, export_name=export_name)

    def _create_integration_event_channel(self, id: str, export_name: str) -> IChannel:
        return xcom.SnsTopicChannel(self, id, export_name=export_name)

    def _create_schedule_event_channel(self, id: str, integration_event_channel: IChannel, export_name: str) -> IScheduleEventChannel:
        return scheduler.StepFunctionScheduleEventChannel(self, id, 
            integration_event_hook=scheduler_hooks.SnsTopicIntegrationEventChannelHook(integration_event_channel), 
            export_name=export_name
        )

    def _create_domain_event_channel(self, id: str, export_name: str) -> IChannel:
        return xcom.SnsTopicChannel(self, id, export_name=export_name)

    def _create_query_result_channel(self, id: str, export_name: str) -> IChannel:
        return xcom.DynamoDBTableChannel(self, id, export_name=export_name)

    def _bind_gateway(self, command_channel: IChannel, query_channel: IChannel, integration_event_channel: IChannel, query_result_channel: IChannel, gateway: IGateway):
        gateway.add_integration_event_subscriptions(
            edge_hooks.SnsTopicIntegrationEventSubscription(integration_event_channel)
        )
        gateway.add_channels(
            edge_hooks.SnsTopicChannelHook(command_channel),
            edge_hooks.SnsTopicChannelHook(query_channel),
        )

    def _bind_context(self, commands_topics: typing.Sequence[str], command_channel: IChannel, integration_event_channel: IChannel, schedule_event_channel: IScheduleEventChannel, domain_event_channel: IChannel, query_result_channel: IChannel, context: IContext):
        context.add_command_subscriptions(
            context_hooks.SnsTopicCommandChannelSubscription(command_channel, commands_topics)
        )
        context.add_channels(
            context_hooks.SnsTopicChannelHook(integration_event_channel),
            context_hooks.StepFunctionSchedulerChannelHook(schedule_event_channel),
            context_hooks.SnsTopicChannelHook(domain_event_channel),
            context_hooks.DynamoDBTableChannelHook(query_result_channel)
        )


class BusinessConceptSolution(BusinessConceptTemplate):

    @classmethod
    def _bring_default_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        return xcom.SnsTopicChannel.bring(scope, id, export_name)

    @classmethod
    def _bring_schedule_event_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        return xcom.SnsTopicChannel.bring(scope, id, export_name)

    @classmethod
    def _bring_query_result_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        return xcom.DynamoDBTableChannel.bring(scope, id, export_name)

    def _create_default_channel(self, id: str, export_name: str) -> IChannel:
        return xcom.SnsTopicChannel(self, id, export_name=export_name)

    def _create_schedule_event_channel(self, id: str, integration_event_channel: IChannel, export_name: str) -> IScheduleEventChannel:
        return scheduler.StepFunctionScheduleEventChannel(self, id, 
            integration_event_hook=scheduler_hooks.SnsTopicIntegrationEventChannelHook(integration_event_channel), 
            export_name=export_name
        )

    def _create_query_result_channel(self, id: str, export_name: str) -> IChannel:
        return xcom.DynamoDBTableChannel(self, id, export_name=export_name)

    def _bind_gateway(self, concept: str, channels: BusinessConceptChannels, gateway: IGateway):
        concept_upper = concept.upper()
        gateway.add_integration_event_subscriptions(
            edge_hooks.SnsTopicIntegrationEventSubscription(channels['default'])
        )
        gateway.add_channels(
            edge_hooks.SnsTopicChannelHook(f'{concept_upper}_DEFAULT', channels['default'])
        )

    def _bind_context(self, concept: str, commands_topics: typing.Sequence[str], channels: BusinessConceptChannels, context: IContext):
        concept_upper = concept.upper()
        context.add_command_subscriptions(
            context_hooks.SnsTopicCommandChannelSubscription(channels['default'], commands_topics)
        )
        context.add_channels(
            context_hooks.SnsTopicCommandChannelSubscription(f'{concept_upper}_DEFAULT', channels['default']),
            context_hooks.StepFunctionSchedulerChannelHook(f'{concept_upper}_SCHEDULE_EVENT', channels['schedule_event']),
            context_hooks.DynamoDBTableChannelHook(f'{concept_upper}_QUERY_RESULT', channels['query_result'])
        )
