import typing
import dataclasses

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
    

@dataclasses.dataclass
class MessageProps:
    definition: typing.Union[ApplicationCommandDefinition, IntegrationEventDefinition]
    resource_path: str
    method: str


class GatewayBusStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *,
        messages: typing.Sequence[MessageProps],
        message_lake_stack: MessageLakeStack,
        share_prefix: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        domainpy_layer = DomainpyLayerVersion(self, 'domainpy')

        self.gateway = Gateway(self, 'gateway', share_prefix=share_prefix)

        for message in messages:
            self.gateway.add_publisher(
                Publisher(self, message.definition.topic,
                    definition=message.definition,
                    trace_store=message_lake_stack.trace_store,
                    share_prefix=share_prefix,
                    domainpy_layer=domainpy_layer
                ),
                resource_path=message.resource_path,
                method=message.method
            )
    
        Resolver(self, 'resolver',
            trace_store=message_lake_stack.trace_store,
            message_lake=message_lake_stack.message_lake,
            share_prefix=share_prefix,
            domainpy_layer=domainpy_layer
        )
