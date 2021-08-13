import typing

from aws_cdk import core as cdk

from domainpy_aws_cdk.constructs.head import (
    Gateway,
    ApplicationCommandDefinition,
    IntegrationEventDefinition,
    TraceStore, 
    Publisher
)


class MessageLakeStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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

        gateway = Gateway(self, 'gateway', share_prefix=share_prefix)

        for message in messages:
            gateway.add_publisher(
                Publisher(self, message.topic,
                    message=message,
                    trace_store=message_lake_stack.trace_store,
                    share_prefix=share_prefix
                )
            )
    