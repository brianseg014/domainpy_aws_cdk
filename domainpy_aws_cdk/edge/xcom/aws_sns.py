
from aws_cdk import core as cdk

from domainpy_aws_cdk.edge.base import IGateway, IChannelHook
from domainpy_aws_cdk.edge.aws_apigateway import RestApiGateway
from domainpy_aws_cdk.xcom.aws_sns import SnsTopicChannel


class SnsTopicChannelHook(IChannelHook):
    
    def __init__(self, channel_name: str, channel: SnsTopicChannel) -> None:
        self.channel_name = channel_name
        self.channel = channel

    def bind(self, gateway: IGateway):
        if isinstance(gateway, RestApiGateway):
            self._bind_rest_api_gateway(gateway)
        else:
            raise cdk.ValidationError('gateway-channel incompatible')

    def _bind_rest_api_gateway(self, gateway: RestApiGateway):
        gateway.microservice.add_environment(f'{self.channel_name}_SERVICE', 'AWS::SNS:Topic')
        gateway.microservice.add_environment(f'{self.channel_name}_TOPIC_ARN', self.channel.topic.topic_arn)
        self.channel.topic.grant_publish(gateway.microservice)
