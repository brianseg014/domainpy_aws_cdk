import typing

from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions

from domainpy_aws_cdk.context.base import (
    IContext, 
    ICommandChannelSubscription,
    IChannelHook
)
from domainpy_aws_cdk.context.aws_lambda import LambdaContextBase
from domainpy_aws_cdk.xcom.aws_sns import SnsTopicChannel


class SnsTopicCommandChannelSubscription(ICommandChannelSubscription):
    
    def __init__(
        self, 
        channel: SnsTopicChannel,
        topics: typing.Sequence[str]
    ) -> None:
        self.channel = channel
        self.topics = topics

    def bind(self, context: IContext):
        if isinstance(context, LambdaContextBase):
            self._bind_lambda_context(context)
        else:
            raise Exception('context-channel incompatible')

    def _bind_lambda_context(self, context: LambdaContextBase):
        command_topic = self.channel.topic
        context_queue = context.queue
        context_dlq = context.dlq

        command_topic.add_subscription(
            sns_subscriptions.SqsSubscription(context_queue,
                raw_message_delivery=True,
                dead_letter_queue=context_dlq,
                filter_policy={
                    'topic': sns.SubscriptionFilter(conditions=self.topics)
                }
            )
        )


class SnsTopicChannelHook(IChannelHook):

    def __init__(
        self, 
        channel_name: str,
        channel: SnsTopicChannel
    ) -> None:
        self.channel_name = channel_name
        self.channel = channel

    def bind(self, context: IContext):
        if isinstance(context, LambdaContextBase):
            self._bind_lambda_context(context)
        else:
            raise Exception('context-channel incompatible')

    def _bind_lambda_context(self, context: LambdaContextBase):
        context_function = context.microservice
        channel_topic = self.channel.topic

        context_function.add_environment(f'{self.channel_name}_SERVICE', 'AWS::SNS::Topic')
        context_function.add_environment(f'{self.channel_name}_TOPIC_ARN', channel_topic.topic_arn)
        channel_topic.grant_publish(context_function)
