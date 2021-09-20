
from domainpy_aws_cdk.view.base import IView, IQueryResultChannelHook
from domainpy_aws_cdk.view.aws_lambda import LambdaViewBase
from domainpy_aws_cdk.xcom.aws_dynamodb import DynamoDBTableChannel


class DynamoDBTableQueryResultChannelHook(IQueryResultChannelHook):

    def __init__(
        self,
        channel: DynamoDBTableChannel
    ) -> None:
        self.channel = channel

    def bind(self, view: IView):
        if isinstance(view, LambdaViewBase):
            self._bind_lambda_view(view)
        else:
            raise Exception('view-queryresultchannel incompatible')

    def _bind_lambda_view(self, view: LambdaViewBase):
        view_function = view.microservice
        channel_table = self.channel.table

        view_function.add_environment('QUERY_RESULT_SERVICE', 'AWS::DynamoDB::Table')
        view_function.add_environment('QUERY_RESULT_TABLE_NAME', channel_table.table_name)
        channel_table.grant_read_write_data(view_function)
