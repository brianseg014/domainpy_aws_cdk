import typing

from aws_cdk import core as cdk
from aws_cdk import aws_dynamodb as dynamodb

from domainpy_aws_cdk.tracestore.base import TraceStoreBase, TraceSegmentStoreBase


class DynamoDBTableTraceStore(TraceStoreBase):
    class Import(TraceStoreBase):
        def __init__(self, scope: cdk.Construct, id: str, table_arn: str) -> None:
            super().__init__(scope, id)

            self.table = dynamodb.Table.from_table_arn(self, 'table', table_arn)

    @classmethod
    def bring(cls, scope: cdk.Construct, id: str, export_name: str) -> Import:
        table_arn = cdk.Fn.import_value(export_name)

        return DynamoDBTableTraceStore.Import(scope, id, table_arn)

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *, 
        export_name: typing.Optional[str] = None
    ) -> None:
        super().__init__(scope, construct_id)

        self.table = dynamodb.Table(self, 'table',
            partition_key={ 'name': 'trace_id', 'type': dynamodb.AttributeType.STRING },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST
        )

        if export_name is not None:
            cdk.CfnOutput(self, 'table-arn',
                export_name=f'{export_name}TableArn',
                value=self.table.table_arn
            )



class DynamoDBTableTraceSegmentStore(TraceSegmentStoreBase):

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.table = dynamodb.Table(self, 'table',
            partition_key={ 'name': 'trace_id', 'type': dynamodb.AttributeType.STRING },
            sort_key={ 'name': 'subject', 'type': dynamodb.AttributeType.STRING },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )
