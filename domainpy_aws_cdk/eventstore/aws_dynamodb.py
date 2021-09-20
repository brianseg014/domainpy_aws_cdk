import typing

from aws_cdk import core as cdk
from aws_cdk import aws_dynamodb as dynamodb

from domainpy_aws_cdk.eventstore.base import EventStoreBase


class DynamoDBTableEventStore(EventStoreBase):
    class Import(EventStoreBase):
        def __init__(self, scope: cdk.Construct, id: str, table_arn: str) -> None:
            super().__init__(scope, id)

            self.table = dynamodb.Table.from_table_arn(table_arn)

    @classmethod
    def bring(self, scope: cdk.Construct, id: str, export_name: str) -> Import:
        table_arn = cdk.Fn.import_value(f'{export_name}TableArn')

        return DynamoDBTableEventStore.Import(scope, id, table_arn)

    def __init__(
        self, 
        scope: cdk.Construct, 
        id: str, 
        *, 
        export_name: typing.Optional[str] = None
    ) -> None:
        super().__init__(scope, id)

        self.table = dynamodb.Table(self, 'table',
            partition_key={ 'name': 'stream_id', 'type': dynamodb.AttributeType.STRING },
            sort_key={ 'name': 'number', 'type': dynamodb.AttributeType.NUMBER },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        if export_name is not None:
            cdk.CfnOutput(self, 'table-arn',
                export_name=f'{export_name}TableArn',
                value=self.table.table_arn
            )
