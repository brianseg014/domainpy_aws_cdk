
from aws_cdk import core as cdk

from domainpy_aws_cdk.edge.base import IGateway, ICommandChannelHook
from domainpy_aws_cdk.edge.aws_apigateway import RestApiGateway
from domainpy_aws_cdk.xcom.aws_sns import SnsTopicChannel


class SnsTopicCommandChannelHook(ICommandChannelHook):
    
    def __init__(self, channel: SnsTopicChannel) -> None:
        self.channel = channel

    def bind(self, gateway: IGateway):
        if isinstance(gateway, RestApiGateway):
            self._bind_rest_api_gateway(gateway)
        else:
            raise cdk.ValidationError('gateway-commandchannel incompatible')

    def _bind_rest_api_gateway(self, gateway: RestApiGateway):
        gateway.microservice.add_environment(
            'COMMAND_CHANNEL_TOPIC_ARN', self.channel.topic.topic_arn
        )
        self.channel.topic.grant_publish(gateway.microservice)
