import typing
import dataclasses

from aws_cdk import core as cdk

from domainpy_aws_cdk.constructs.utils import DomainpyLayerVersion
from domainpy_aws_cdk.constructs.head import (
    Gateway,
    Proxy,
    QueryDefinition,
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
    

@dataclasses.dataclass(frozen=True)
class MethodProps:
    definition: typing.Union[QueryDefinition, ApplicationCommandDefinition, IntegrationEventDefinition]
    resource_path: str
    http_method: str
    proxy_url: typing.Optional[str] = None
    not_available: bool = False


class GatewayStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *,
        methods: typing.Sequence[MethodProps],
        message_lake_stack: MessageLakeStack,
        share_prefix: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        domainpy_layer = DomainpyLayerVersion(self, 'domainpy')

        self.gateway = Gateway(self, 'gateway', share_prefix=share_prefix)

        for method in methods:
            if method.not_available:
                self.gateway.add_mock_as_temporary_unavailable(
                    resource_path=method.resource_path,
                    method=method.http_method
                )
            elif method.proxy_url is not None:
                self.gateway.add_proxy(
                    Proxy(self, method.definition.topic, 
                        definition=method.definition
                    ),
                    resource_path=method.resource_path,
                    method=method.http_method,
                    proxy_url=method.proxy_url
                )
            elif isinstance(method.definition, (ApplicationCommandDefinition, IntegrationEventDefinition)):
                self.gateway.add_publisher(
                    Publisher(self, method.definition.topic,
                        definition=method.definition,
                        trace_store=message_lake_stack.trace_store,
                        share_prefix=share_prefix,
                        domainpy_layer=domainpy_layer
                    ),
                    resource_path=method.resource_path,
                    method=method.http_method
                )
            else:
                raise Exception(f'unhandled method: {method}')
    
        Resolver(self, 'resolver',
            trace_store=message_lake_stack.trace_store,
            message_lake=message_lake_stack.message_lake,
            share_prefix=share_prefix,
            domainpy_layer=domainpy_layer
        )
