import typing

from aws_cdk import core as cdk

from domainpy_aws_cdk.constructs.utils import DomainpyLayerVersion
from domainpy_aws_cdk.constructs.head import (
    Gateway,
    ApplicationCommandDefinition,
    IntegrationEventDefinition,
    MessageLake,
    TraceStore, 
    Publisher,
    Resolver
)


class MessageLakeStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.message_lake = MessageLake(self, 'messagelake')
        self.trace_store = TraceStore(self, 'tracestore')
    

class GatewayBusStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *,
        messages: typing.Sequence[typing.Union[ApplicationCommandDefinition, IntegrationEventDefinition]],
        message_lake_stack: MessageLakeStack,
        share_prefix: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        domainpy_layer = DomainpyLayerVersion(self, 'domainpy')

        gateway = Gateway(self, 'gateway', share_prefix=share_prefix)

        for message in messages:
            gateway.add_publisher(
                Publisher(self, message.topic,
                    message=message,
                    trace_store=message_lake_stack.trace_store,
                    share_prefix=share_prefix,
                    domainpy_layer=domainpy_layer
                )
            )
    
        Resolver(self, 'resolver',
            trace_store=message_lake_stack.trace_store,
            message_lake=message_lake_stack.message_lake,
            share_prefix=share_prefix,
            domainpy_layer=domainpy_layer
        )