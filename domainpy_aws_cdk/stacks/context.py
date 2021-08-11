import typing

from aws_cdk import core as cdk

from domainpy_aws_cdk.constructs.context import EventStore, IdempotentStore, Context, ContextMap


class ContextDataStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.event_store = EventStore(self, 'eventstore')
        self.idempotent_store = IdempotentStore(self, 'idempotentstore')


class ContextComputeStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str,
        *,
        entry: str,
        gateway_subscriptions: typing.Sequence[str],
        integration_subscriptions: typing.Sequence[str],
        data_stack: ContextDataStack,
        share_prefix: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        Context(self, 'context', 
            entry=entry,
            gateway_subscriptions=gateway_subscriptions, 
            integration_subscriptions=integration_subscriptions,
            event_store=data_stack.event_store, 
            idempotent_store=data_stack.idempotent_store,
            share_prefix=share_prefix
        )


class ContextMapComputeStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str,
        *,
        entry: str,
        context: Context,
        share_prefix: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.context_map = ContextMap(
            self, 
            'context_map',
            entry,
            context
        )
