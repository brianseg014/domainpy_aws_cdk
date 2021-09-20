
from domainpy_aws_cdk.view.base import IView, IChannelHook
from domainpy_aws_cdk.view.aws_lambda import LambdaViewBase
from domainpy_aws_cdk.xcom.aws_dynamodb import DynamoDBTableChannel


class DynamoDBTableChannelHook(IChannelHook):

    def __init__(
        self,
        channel_name: str,
        channel: DynamoDBTableChannel
    ) -> None:
        self.channel_name = channel_name
        self.channel = channel

    def bind(self, view: IView):
        if isinstance(view, LambdaViewBase):
            self._bind_lambda_view(view)
        else:
            raise Exception('view-queryresultchannel incompatible')

    def _bind_lambda_view(self, view: LambdaViewBase):
        view_function = view.microservice
        channel_table = self.channel.table

        view_function.add_environment(f'{self.channel_name}_SERVICE', 'AWS::DynamoDB::Table')
        view_function.add_environment(f'{self.channel_name}_TABLE_NAME', channel_table.table_name)
        channel_table.grant_read_write_data(view_function)
