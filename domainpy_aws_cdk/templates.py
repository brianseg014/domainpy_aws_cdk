import abc
import typing
import jsii

from aws_cdk import core as cdk

from domainpy_aws_cdk.edge.base import IGateway
from domainpy_aws_cdk.context.base import IChannelHook, IContext
from domainpy_aws_cdk.xcom.base import IChannel
from domainpy_aws_cdk.scheduler.base import IScheduleEventChannel


class ITemplate:
    pass


class TemplateBase(cdk.Construct, ITemplate, metaclass=jsii.JSIIAbstractClass):
    pass



class MessageTypeTemplate(TemplateBase):
    class Import(TemplateBase):
        def __init__(
            self, 
            scope: cdk.Construct, 
            id: str, 
            command_channel: IChannel,
            query_channel: IChannel,
            integration_event_channel: IChannel,
            schedule_event_channel: IScheduleEventChannel,
            domain_event_channel: IChannel,
            query_result_channel: IChannel
        ) -> None:
            super().__init__(scope, id)
            self.command_channel = command_channel
            self.query_channel = query_channel
            self.integration_event_channel = integration_event_channel
            self.schedule_event_channel = schedule_event_channel
            self.domain_event_channel = domain_event_channel
            self.query_result_channel = query_result_channel

    @classmethod
    def bring(cls, scope: cdk.Construct, id: str, export_name: str) -> Import:
        command_channel = cls._bring_command_channel(scope, 'command-channel', f'{export_name}CommandChannel')
        query_channel = cls._bring_query_channel(scope, 'query-channel', f'{export_name}QueryChannel')
        integration_event_channel = cls._bring_integration_event_channel(scope, 'integration-event-channel', f'{export_name}IntegrationEventChannel')
        schedule_event_channel = cls._bring_schedule_event_channel(scope, 'schedule-event-channel', f'{export_name}ScheduleEventChannel')
        domain_event_channel = cls._bring_domain_event_channel(scope, 'domain-event-channel', f'{export_name}DomainEventChannel')
        query_result_channel = cls._bring_query_result_channel(scope, 'query-result-channel', f'{export_name}QueryResultChannel')
        return MessageTypeTemplate.Import(scope, id,
            command_channel=command_channel,
            query_channel=query_channel,
            integration_event_channel=integration_event_channel,
            schedule_event_channel=schedule_event_channel,
            domain_event_channel=domain_event_channel,
            query_result_channel=query_result_channel
        )

    @classmethod
    @abc.abstractmethod
    def _bring_command_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        pass

    @classmethod
    @abc.abstractmethod
    def _bring_query_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        pass

    @classmethod
    @abc.abstractmethod
    def _bring_integration_event_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        pass

    @classmethod
    @abc.abstractmethod
    def _bring_schedule_event_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        pass

    @classmethod
    @abc.abstractmethod
    def _bring_domain_event_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        pass

    @classmethod
    @abc.abstractmethod
    def _bring_query_result_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        pass

    def __init__(self, scope: cdk.Construct, id: str, *, export_name: str) -> None:
        super().__init__(scope, id)

        self.command_channel = self._create_command_channel('command-channel', f'{export_name}CommandChannel')
        self.query_channel = self._create_query_channel('query-channel', f'{export_name}QueryChannel')
        self.integration_event_channel = self._create_integration_event_channel('integration-event-channel', f'{export_name}IntegrationEventChannel')
        self.schedule_event_channel = self._create_schedule_event_channel('schedule-event-channel', self.integration_event_channel, f'{export_name}ScheduleEventChannel')
        self.domain_event_channel = self._create_domain_event_channel('domain-event-channel', f'{export_name}DomainEventChannel')
        self.query_result_channel = self._create_query_result_channel('query-result-channel', f'{export_name}QueryResultChannel')

    @abc.abstractmethod
    def _create_command_channel(self, id: str, export_name: str) -> IChannel:
        pass

    @abc.abstractmethod
    def _create_query_channel(self, id: str, export_name: str) -> IChannel:
        pass

    @abc.abstractmethod
    def _create_integration_event_channel(self, id: str, export_name: str) -> IChannel:
        pass

    @abc.abstractmethod
    def _create_schedule_event_channel(self, id: str, integration_event_channel: IChannel, export_name: str) -> IScheduleEventChannel:
        pass

    @abc.abstractmethod
    def _create_domain_event_channel(self, id: str, export_name: str) -> IChannel:
        pass

    @abc.abstractmethod
    def _create_query_result_channel(self, id: str, export_name: str) -> IChannel:
        pass

    def bind_gateway(self, gateway: IContext):
        self._bind_gateway(
            self.command_channel,
            self.query_channel,
            self.integration_event_channel,
            self.query_result_channel,
            gateway
        )

    def bind_context(self, context: IContext, command_topics: typing.Sequence[str]):
        self._bind_context(
            command_topics,
            self.command_channel,
            self.integration_event_channel,
            self.schedule_event_channel,
            self.domain_event_channel,
            self.query_channel,
            context
        )

    @abc.abstractmethod
    def _bind_gateway(
        self, 
        command_channel: IChannel, 
        query_channel: IChannel, 
        integration_event_channel: IChannel, 
        query_result_channel: IChannel, 
        gateway: IGateway
    ):
        pass

    @abc.abstractmethod
    def _bind_context(
        self,
        commands_topics: typing.Sequence[str],
        command_channel: IChannel, 
        integration_event_channel: IChannel,
        schedule_event_channel: IScheduleEventChannel, 
        domain_event_channel: IChannel, 
        query_result_channel: IChannel, 
        context: IContext
    ):
        pass



class BusinessConceptChannels(typing.TypedDict):
        default: IChannel
        schedule_event: IScheduleEventChannel
        query_result: IChannel


class BusinessConceptTemplate(TemplateBase):

    class Import(TemplateBase):
        def __init__(
            self, 
            scope: cdk.Construct, 
            id: str, 
            *,
            concepts_channels: typing.Dict[str, BusinessConceptChannels],
        ) -> None:
            super().__init__(scope, id)
            self.concepts_channels = concepts_channels


    @classmethod
    def bring(cls, scope: cdk.Construct, id: str, concepts: typing.Sequence[str], export_name: str) -> Import:
        concepts_channels: typing.TypedDict[str, BusinessConceptChannels] = {
            concept: {
                'default': cls._bring_default_channel(scope, f'{concept}-default-channel', f'{export_name}{concept}DefaultChannel'),
                'schedule_event': cls._bring_schedule_event_channel(scope, f'{concept}-schedule-event', f'{export_name}{concept}ScheduleEventChannel'),
                'query_result': cls._bring_query_result_channel(scope, f'{concept}-query-result-channel', f'{export_name}{concept}QueryResultChannel')
            }
            for concept in concepts
        }

        return BusinessConceptTemplate.Import(scope, id, 
            concepts_channels=concepts_channels
        )

    @classmethod
    @abc.abstractmethod
    def _bring_default_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        pass

    @classmethod
    @abc.abstractmethod
    def _bring_schedule_event_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        pass

    @classmethod
    @abc.abstractmethod
    def _bring_query_result_channel(cls, scope: cdk.Construct, id: str, export_name: str):
        pass
    
    def __init__(self, scope: cdk.Construct, id: str, *, concepts: typing.Sequence[str], export_name: str):
        super().__init__(scope, id)

        self.concepts_channels: typing.Dict[str, BusinessConceptChannels] = {}
        for concept in concepts:
            default_channel  = self._create_default_channel(
                f'{concept}-default-channel', 
                f'{export_name}{concept}DefaultChannel'
            )
            schedule_event_channel = self._create_schedule_event_channel(
                f'{concept}-schedule-event', 
                default_channel, 
                f'{export_name}{concept}ScheduleEventChannel'
            ),
            query_result_channel = self._create_query_result_channel(
                f'{concept}-query-result-channel', 
                f'{export_name}{concept}QueryResultChannel'
            )
            self.concepts_channels[concept] = {
                'default': default_channel,
                'schedule_event': schedule_event_channel,
                'query_result': query_result_channel
            }

    def bind_gateway(self, gateway: IGateway):
        for concept,channels in self.concepts_channels:
            self._bind_gateway(concept, channels, gateway)

    def bind_context(self, context: IContext, commands_topics: typing.Dict[str, typing.Sequence[str]]):
        concepts_with_topics = {
            concept: channels
            for concept,channels in self.concepts_channels.items()
            if concept in commands_topics
        }

        for concept,channels in concepts_with_topics:
            self._bind_context(concept, commands_topics[concept], channels, context)

    @abc.abstractmethod
    def _create_default_channel(self, id: str, export_name: str) -> IChannel:
        pass

    @abc.abstractmethod
    def _create_schedule_event_channel(self, id: str, integration_event_channel: IChannel, export_name: str) -> IScheduleEventChannel:
        pass

    @abc.abstractmethod
    def _create_query_result_channel(self, id: str, export_name: str) -> IChannel:
        pass

    @abc.abstractmethod
    def _bind_gateway(self, concept: str, channels: BusinessConceptChannels, gateway: IGateway):
        pass

    @abc.abstractmethod
    def _bind_context(self, concept: str, commands_topics: typing.Sequence[str], channels: BusinessConceptChannels, context: IContext):
        pass

