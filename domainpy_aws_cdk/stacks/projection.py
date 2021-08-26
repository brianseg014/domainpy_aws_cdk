import typing

from aws_cdk import core as cdk

from domainpy_aws_cdk.constructs.projection import ElasticSearchProjection, ElasticSearchProjector, ElasticSearchInitializer


class ElasticSearchProjectionDataStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str,
        *,
        initializers: typing.Optional[typing.Sequence[ElasticSearchInitializer]],
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
        domain_subscriptions: typing.Sequence[str],
        domain_sources: typing.Sequence[str],
        data_stack: ElasticSearchProjectionDataStack,
        share_prefix: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.projector = ElasticSearchProjector(self, 'projector',
            entry=entry,
            domain_subscriptions=domain_subscriptions,
            domain_sources=domain_sources,
            projection=data_stack.projection,
            share_prefix=share_prefix
        )
