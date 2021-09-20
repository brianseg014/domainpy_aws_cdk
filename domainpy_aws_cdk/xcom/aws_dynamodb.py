import typing

from aws_cdk import core as cdk
from aws_cdk import aws_dynamodb as dynamodb

from domainpy_aws_cdk.xcom.base import ChannelBase


class DynamoDBTableChannel(ChannelBase):
    class Import(ChannelBase):
        def __init__(self, scope: cdk.Construct, id: str, table_arn: str) -> None:
            super().__init__(scope, id)

            self.table = dynamodb.Table.from_table_arn(self, 'table', table_arn)
    
    @classmethod
    def bring(self, scope: cdk.Construct, id: str, export_name: str) -> Import:
        table_arn = cdk.Fn.import_value(f'{export_name}TableArn')

        return DynamoDBTableChannel.Import(scope, id, table_arn)

    def __init__(
        self, 
        scope: cdk.Construct, 
        id: str,
        *,
        sort_key: typing.Optional[str] = None,
        export_name: typing.Optional[str] = None
    ) -> None:
        super().__init__(scope, id)

        if sort_key is None:
            self.table = dynamodb.Table(self, 'table',
                partition_key={ 'name': 'trace_id', 'type': dynamodb.AttributeType.STRING },
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                removal_policy=cdk.RemovalPolicy.DESTROY,
                time_to_live_attribute='ttl'
            )
        else:
            self.table = dynamodb.Table(self, 'table',
                partition_key={ 'name': 'trace_id', 'type': dynamodb.AttributeType.STRING },
                sort_key={ 'name': sort_key, 'type': dynamodb.AttributeType.STRING },
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                removal_policy=cdk.RemovalPolicy.DESTROY,
                time_to_live_attribute='ttl'
            )

        if export_name is not None:
            cdk.CfnOutput(self, 'table-arn',
                export_name=f'{export_name}TableArn',
                value=self.table.table_arn
            )
