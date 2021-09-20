import typing

from aws_cdk import core as cdk
from aws_cdk import aws_apigateway as apigateway

from domainpy_aws_cdk.xcom.base import ChannelBase


class RestApiChannel(ChannelBase):

    def __init__(
        self,
        scope: cdk.Construct,
        id: str,
        *,
        rest_api_props: typing.Optional[apigateway.RestApiProps] = None,
        export_name: typing.Optional[str] = None
    ) -> None:
        super().__init__(scope, id)

        if isinstance(rest_api_props, dict):
            rest_api_props = apigateway.RestApiProps(**rest_api_props)

        _rest_props = {}
        if rest_api_props is not None:
            _rest_props = rest_api_props._values

        if 'rest_api_name' not in _rest_props:
            _rest_props['rest_api_name'] = export_name

        self.rest = apigateway.RestApi(self, 'rest',
            deploy_options=apigateway.StageOptions(
                stage_name='api',
                tracing_enabled=True
            ),
            **_rest_props
        )
