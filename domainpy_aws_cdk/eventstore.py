from __future__ import annotations

import typing

import constructs
import aws_cdk as cdk
import aws_cdk.aws_dynamodb as cdk_dynamodb


class EventStore(constructs.Construct):
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
            stream=cdk_dynamodb.StreamViewType.NEW_IMAGE,
            partition_key=cdk_dynamodb.Attribute(
                name="stream_id", type=cdk_dynamodb.AttributeType.STRING
            ),
            sort_key=cdk_dynamodb.Attribute(
                name="number", type=cdk_dynamodb.AttributeType.NUMBER
            ),
        )
