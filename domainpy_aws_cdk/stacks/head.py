import typing

from aws_cdk import core as cdk

from domainpy_aws_cdk.constructs.head import Definition, TraceStore, Publisher, MessageType


class Message(typing.TypedDict):
    name: str
    message_type: MessageType
    structs: typing.Sequence[Definition]
    attributes: typing.Sequence[Definition]
    resolutions: typing.Sequence[str]


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
        messages: typing.Sequence[Message],
        message_lake_stack: MessageLakeStack,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.publishers = []

        for m in messages:
            self.publishers.append(
                Publisher(
                    self, m['name'], **m, trace_store=message_lake_stack.trace_store
                )
            )
