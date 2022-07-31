import typing

import constructs
import aws_cdk as cdk
import aws_cdk.aws_dynamodb as cdk_dynamodb


class TraceStore(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        *,
        export_name: typing.Optional[str] = None,
    ) -> None:
        super().__init__(scope, id)

        self.table = cdk_dynamodb.Table(
            self,
            "table",
            billing_mode=cdk_dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            partition_key=cdk_dynamodb.Attribute(
                name="trace_id", type=cdk_dynamodb.AttributeType.STRING
            ),
            sort_key=cdk_dynamodb.Attribute(
                name="segment_id", type=cdk_dynamodb.AttributeType.STRING
            ),
        )

        if export_name is not None:
            cdk.CfnOutput(
                self,
                "table-arn",
                export_name=f"{export_name}TableArn",
                value=self.table.table_arn,
            )
