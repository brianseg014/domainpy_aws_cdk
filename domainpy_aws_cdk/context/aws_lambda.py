import abc

from aws_cdk import core as cdk
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python
from aws_cdk import aws_lambda_event_sources as lambda_sources
from aws_cdk import aws_sqs as sqs

from domainpy_aws_cdk.context.base import (
    ContextBase, 
    ICommandChannelSubscription, 
    IEventStoreHook,
    ITraceSegmentStoreHook,
    IDomainEventChannelHook,
    IIntegrationEventChannelHook,
    ISchedulerChannelHook
)
from domainpy_aws_cdk.utils import DomainpyLayerVersion


class LambdaContextBase(ContextBase):
    
    def __init__(self, scope: cdk.Construct, id: str) -> None:
        super().__init__(scope, id)

        self.dlq = sqs.Queue(self, "dlq")
        self.queue = sqs.Queue(self, "queue",
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=20,
                queue=self.dlq
            ),
            visibility_timeout=cdk.Duration.seconds(30),
            receive_message_wait_time=cdk.Duration.seconds(20)
        )

    @abc.abstractproperty
    def function(self) -> lambda_.Function:
        pass



class PythonLambdaEventSourcedContext(LambdaContextBase):

    def __init__(
        self,
        scope: cdk.Construct,
        id: str,
        *,
        microservice_props: lambda_python.PythonFunctionProps,
        command_channel_subscription: ICommandChannelSubscription,
        event_store_hook: IEventStoreHook,
        trace_segment_store_hook: ITraceSegmentStoreHook,
        domain_event_channel_hook: IDomainEventChannelHook,
        integration_event_channel_hook: IIntegrationEventChannelHook,
        scheduler_channel_hook: ISchedulerChannelHook
    ) -> None:
        super().__init__(scope, id)

        if isinstance(microservice_props, dict):
            microservice_props = lambda_python.PythonFunctionProps(**microservice_props)

        domainpy_layer = DomainpyLayerVersion(self, 'domainpy')
        self.microservice = lambda_python.PythonFunction(self, 'microservice',
            runtime=lambda_.Runtime.PYTHON_3_8,
            memory_size=1024,
            layers=[domainpy_layer],
            timeout=cdk.Duration.seconds(10),
            tracing=lambda_.Tracing.ACTIVE,
            description='[CONTEXT] Handles commands and integrations and emits domain events',
            **microservice_props._values
        )
        self.microservice.add_event_source(lambda_sources.SqsEventSource(self.queue))

        command_channel_subscription.bind(self)
        event_store_hook.bind(self)
        trace_segment_store_hook.bind(self)
        domain_event_channel_hook.bind(self)
        integration_event_channel_hook.bind(self)
        scheduler_channel_hook.bind(self)

    @property
    def function(self) -> lambda_.Function:
        return self.microservice
