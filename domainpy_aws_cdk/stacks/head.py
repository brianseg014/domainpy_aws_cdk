import typing

from aws_cdk import core as cdk

from domainpy_aws_cdk.constructs.head import (
    MessageLake, 
    TraceStore, 
    GatewayResourceProps, 
    GatewayMethodProps,
    Gateway,
    CommandBus
)


class GatewayDataStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.message_lake = MessageLake(self, 'messagelake')
        self.trace_store = TraceStore(self, 'tracestore')


class GatewayComputeStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *, 
        entry: str,
        resources: typing.Sequence[GatewayResourceProps], 
        data_stack: GatewayDataStack,
        share_prefix: str,
        index: str = 'app',
        handler: str = 'handler',
        message_topic_header_key: str = 'x-message-topic',
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.command_bus = CommandBus(self, 'commandbus', 
            share_prefix=share_prefix
        )

        self.gateway = Gateway(self, 'gateway',
            entry=entry,
            resources=resources,
            command_bus=self.command_bus,
            trace_store=data_stack.trace_store,
            index=index,
            handler=handler,
            share_prefix=share_prefix,
            message_topic_header_key=message_topic_header_key
        )
