import typing

from aws_cdk import core as cdk
from aws_cdk import aws_dynamodb as dynamodb

from domainpy_aws_cdk.projection.base import ProjectionBase


class DynamoDBTableProjection(ProjectionBase):

    def __init__(
        self,
        scope: cdk.Construct,
        id: str,
        *,
        projection_id: str,
        parent_projection_id: typing.Optional[str] = None
    ) -> None:
        super().__init__(scope, id)

        self.table = dynamodb.Table(self, 'table',
            partition_key={ 'name': projection_id, 'type': dynamodb.AttributeType.STRING },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        if parent_projection_id is not None:
            self.table.add_global_secondary_index(
                index_name='by_parent',
                partition_key={ 'name': parent_projection_id, 'type': dynamodb.AttributeType.STRING },
                sort_key={ 'name': projection_id, 'type': dynamodb.AttributeType.STRING },
                projection_type=dynamodb.ProjectionType.ALL
            )
