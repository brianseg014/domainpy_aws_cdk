import typing

from aws_cdk import core as cdk
from aws_cdk import aws_iam as iam

from domainpy_aws_cdk.constructs.tail import (
    EventLake,
    EventBus
)


class EventLakeStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.domain_event_lake = EventLake(self, 'domain-event')
        self.integration_event_lake = EventLake(self, 'integration-event')


class EventBusStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *,
        event_lake_stack: EventLakeStack,
        share_prefix: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.domain_bus = EventBus(self, 'domain', 
            event_lake=event_lake_stack.domain_event_lake,
            export_name=f'{share_prefix}DomainBusName'
        )

        self.integration_bus = EventBus(self, 'integration', 
            event_lake=event_lake_stack.integration_event_lake,
            export_name=f'{share_prefix}IntegrationBusName'
        )
