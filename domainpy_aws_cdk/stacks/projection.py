import typing

from aws_cdk import core as cdk

from domainpy_aws_cdk.constructs.projection import (
    DynamoDBProjection,
    DynamoDBProjector,
    ElasticSearchInitializerProps,
    ElasticSearchProjection, 
    ElasticSearchProjector
)


class DynamoDBProjectionDataStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, *, projection_id: str, parent_projection_id: typing.Optional[str] = None, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.projection = DynamoDBProjection(self, 'projection', 
            projection_id=projection_id,
            parent_projection_id=parent_projection_id
        )


class DynamoDBProjectorComputeStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *, 
        entry: str,
        domain_subscriptions: typing.Dict[str, typing.Sequence[str]],
        data_stack: DynamoDBProjectionDataStack,
        share_prefix: str,
        index: str = 'app',
        handler: str = 'handler',
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.projector = DynamoDBProjector(self, 'projector',
            entry=entry,
            domain_subscriptions=domain_subscriptions,
            projection=data_stack.projection,
            share_prefix=share_prefix,
            index=index,
            handler=handler
        )


class ElasticSearchProjectionDataStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str,
        *,
        initializers: typing.Optional[typing.Sequence[ElasticSearchInitializerProps]] = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.projection = ElasticSearchProjection(self, 'projection',
            initializers=initializers
        )


class ElasticSearchProjectorComputeStack(cdk.Stack):

    def __init__(
        self,
        scope: cdk.Construct,
        construct_id: str,
        *,
        entry: str,
        domain_subscriptions: typing.Dict[str, typing.Sequence[str]],
        data_stack: ElasticSearchProjectionDataStack,
        share_prefix: str,
        index: str = 'app',
        handler: str = 'handler',
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.projector = ElasticSearchProjector(self, 'projector',
            entry=entry,
            domain_subscriptions=domain_subscriptions,
            projection=data_stack.projection,
            share_prefix=share_prefix,
            index=index,
            handler=handler
        )
