import typing

from aws_cdk import core as cdk
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions

from domainpy_aws_cdk.view.base import IView, IQueryChannelSubscription, IChannelHook
from domainpy_aws_cdk.view.aws_lambda import LambdaViewBase
from domainpy_aws_cdk.xcom.aws_sns import SnsTopicChannel


class SnsTopicQueryChannelSubscription(IQueryChannelSubscription):

    def __init__(
        self,
        channel: SnsTopicChannel,
        topics: typing.Sequence[str]
    ) -> None:
        self.channel = channel
        self.topics = topics

    def bind(self, view: IView):
        if isinstance(view, LambdaViewBase):
            self._bind_lambda_view(view)
        else:
            raise cdk.ValidationError('view-channel incompatible')

    def _bind_lambda_view(self, view: LambdaViewBase):
        query_topic = self.channel.topic
        view_queue = view.queue

        query_topic.add_subscription(
            aws_sns_subscriptions.SqsSubscription(view_queue,
                raw_message_delivery=True,
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

    def bind(self, view: IView):
        if isinstance(view, LambdaViewBase):
            self._bind_lambda_view(view)
        else:
            cdk.ValidationError('context-channel incompatible')

    def _bind_lambda_view(self, view: LambdaViewBase):
        view_function = view.microservice
        channel_topic = self.channel.topic

        view_function.add_environment(f'{self.channel_name}_SERVICE', 'AWS::SNS::Topic')
        view_function.add_environment(f'{self.channel_name}_TOPIC_ARN', channel_topic.topic_arn)
        channel_topic.grant_publish(view_function)
